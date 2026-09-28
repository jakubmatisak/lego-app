<script setup lang="ts">
  /**
   * Limity cudzích služieb a história volaní: koľko ešte dnes zostáva
   * a čo appka volala, kedy a prečo.
   *
   * Dni sa rátajú podľa UTC, tak ako limity služieb. Brickset dáva vlastnú
   * štatistiku, tá ráta aj volania mimo tejto appky.
   */
  import { computed, ref, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { api, errorMessage } from '@/api/client'
  import { dateTime } from '@/utils/format'

  interface ProviderUsage {
    provider: string
    enabled: boolean
    used: number
    limit: number | null
  }

  interface ApiCall {
    id: number
    at: string
    provider: string
    action: string
    subject: string | null
    purpose: string
    ok: boolean
    status: number | null
    counted: boolean
  }

  const open = defineModel<boolean>({ required: true })

  const { t, te } = useI18n()
  const providers = ref<ProviderUsage[]>([])
  const calls = ref<ApiCall[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const only = ref<string | null>(null)

  const NAMES: Record<string, string> = {
    brickeconomy: 'BrickEconomy',
    brickset: 'Brickset',
    eurostat: 'Eurostat',
    rebrickable: 'Rebrickable',
    upcitemdb: 'UPCitemdb',
  }

  const shown = computed(() => (only.value ? calls.value.filter(c => c.provider === only.value) : calls.value))

  function purposeLabel (purpose: string): string {
    // Nové záznamy nesú schopnosť, staré ešte pôvodný účel.
    const capability = `capabilities.${purpose}.title`
    if (te(capability)) return t(capability)
    const key = `usage.purpose.${purpose}`
    return te(key) ? t(key) : purpose
  }

  function remaining (p: ProviderUsage): number | null {
    return p.limit === null ? null : Math.max(0, p.limit - p.used)
  }

  function barColor (p: ProviderUsage): string {
    const left = remaining(p)
    if (left === null || p.limit === null) return 'primary'
    if (left === 0) return 'negative'
    return left / p.limit < 0.2 ? 'warning' : 'positive'
  }

  async function load (): Promise<void> {
    loading.value = true
    error.value = null
    const { data, error: err } = await api.GET('/usage', {})
    loading.value = false
    if (err || !data) {
      error.value = errorMessage(err, t('usage.loadFailed'))
      return
    }
    providers.value = data.providers
    calls.value = data.calls
  }

  watch(open, isOpen => {
    if (isOpen) load()
  })
</script>

<template>
  <v-dialog v-model="open" max-width="820" scrollable>
    <v-card>
      <v-card-title class="d-flex align-center">
        {{ t('usage.title') }}
        <v-spacer />

        <v-btn
          icon="mdi-refresh"
          :loading="loading"
          size="small"
          variant="text"
          @click="load"
        />
      </v-card-title>

      <v-card-text class="d-flex flex-column ga-4">
        <v-alert v-if="error" type="error" variant="tonal">{{ error }}</v-alert>

        <!-- Dnešné limity -->
        <div class="usage-grid">
          <v-card
            v-for="p in providers"
            :key="p.provider"
            border
            class="pa-3"
            :class="{ 'usage-card--off': !p.enabled }"
            flat
            @click="only = only === p.provider ? null : p.provider"
          >
            <div class="d-flex align-center">
              <span class="text-subtitle-2">{{ NAMES[p.provider] ?? p.provider }}</span>
              <v-spacer />
              <v-icon v-if="only === p.provider" color="primary" icon="mdi-filter" size="small" />
            </div>

            <template v-if="!p.enabled">
              <div class="text-caption text-medium-emphasis mt-1">{{ t('usage.noKey') }}</div>
            </template>

            <template v-else-if="p.limit !== null">
              <div class="text-h6">{{ remaining(p) }} <span class="text-body-2 text-medium-emphasis">/ {{ p.limit }}</span></div>
              <div class="text-caption text-medium-emphasis">{{ t('usage.leftToday', { used: p.used }) }}</div>

              <v-progress-linear
                class="mt-2"
                :color="barColor(p)"
                height="6"
                :model-value="(p.used / p.limit) * 100"
                rounded
              />
            </template>

            <template v-else>
              <div class="text-h6">{{ p.used }}</div>
              <div class="text-caption text-medium-emphasis">{{ t('usage.noDailyLimit') }}</div>
            </template>
          </v-card>
        </div>

        <!-- História volaní -->
        <div class="d-flex align-center">
          <span class="text-subtitle-1">{{ t('usage.history') }}</span>

          <v-chip
            v-if="only"
            class="ms-2"
            closable
            label
            size="small"
            @click:close="only = null"
          >{{ NAMES[only] ?? only }}</v-chip>
        </div>

        <div v-if="shown.length === 0" class="text-body-2 text-medium-emphasis">{{ t('usage.empty') }}</div>

        <v-table v-else density="compact">
          <thead>
            <tr>
              <th>{{ t('usage.colWhen') }}</th>
              <th>{{ t('usage.colService') }}</th>
              <th>{{ t('usage.colWhat') }}</th>
              <th>{{ t('usage.colWhy') }}</th>
              <th />
            </tr>
          </thead>

          <tbody>
            <tr v-for="c in shown" :key="c.id">
              <td class="text-no-wrap">{{ dateTime(c.at) }}</td>

              <td class="text-no-wrap">
                {{ NAMES[c.provider] ?? c.provider }}
                <span v-if="!c.counted" class="text-caption text-medium-emphasis" :title="t('usage.notCounted')">*</span>
              </td>

              <td>
                <span class="text-caption text-medium-emphasis">{{ c.action }}</span>
                <span v-if="c.subject"> · {{ c.subject }}</span>
              </td>

              <td>{{ purposeLabel(c.purpose) }}</td>

              <td>
                <v-icon
                  :color="c.ok ? 'positive' : 'negative'"
                  :icon="c.ok ? 'mdi-check-circle-outline' : 'mdi-alert-circle-outline'"
                  size="small"
                  :title="c.status ? String(c.status) : undefined"
                />
              </td>
            </tr>
          </tbody>
        </v-table>

        <div class="text-caption text-medium-emphasis">{{ t('usage.note') }}</div>
      </v-card-text>

      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="open = false">{{ t('common.close') }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<style scoped>
.usage-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
}

.usage-card--off {
  opacity: 0.6;
}
</style>
