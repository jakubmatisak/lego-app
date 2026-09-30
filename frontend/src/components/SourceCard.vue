<script setup lang="ts">
  /**
   * Jedna služba v Nastaveniach → Dáta: kľúč, čo odomkne, prepínače volaní
   * a pri službách s limitom rezerva.
   *
   * Prepínač je jedno volanie, nie jeden údaj: pod ním je riadok „prinesie:“
   * s tým, čo to isté volanie donesie naraz. Vypnúť len hodnotenie by nič
   * neušetrilo, volanie by odišlo aj tak.
   */
  import type { Source } from '@/api/types'
  import { computed, ref } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useAuthStore } from '@/stores/auth'
  import { useNotifyStore } from '@/stores/notify'
  import { usePriceStore } from '@/stores/prices'

  const props = defineProps<{ source: Source }>()
  const emit = defineEmits<{
    'toggle': [cap: string, enabled: boolean]
    'reserve': [provider: string, value: number]
    'batch': [value: number]
    'auto-purchase': [on: boolean]
    'key-changed': []
  }>()

  const { t, te, tm, rt } = useI18n()
  const notify = useNotifyStore()
  const auth = useAuthStore()
  const prices = usePriceStore()

  const keyDraft = ref('')
  const showKey = ref(false)
  const savingKey = ref(false)

  const p = computed(() => props.source.provider)
  const unlocks = computed(() => (tm(`sources.${p.value}.unlocks`) as unknown[]).map(m => rt(m as never)))
  const usage = computed(() => {
    const s = props.source
    if (s.limit === null || s.limit === undefined) return null
    return t('sources.usage', { used: s.used_today ?? 0, limit: s.limit })
  })

  function brings (cap: string): string | null {
    const key = `capabilities.${cap}.brings`
    return te(key) ? t(key) : null
  }

  async function saveKey (): Promise<void> {
    const value = keyDraft.value.trim()
    if (!value) return
    savingKey.value = true
    const ok = await auth.saveKeys({ [p.value]: value })
    savingKey.value = false
    if (ok) {
      notify.success(t('notice.keySaved'))
      keyDraft.value = ''
      emit('key-changed')
    } else {
      notify.error(auth.error, t('notice.saveFailed'))
    }
  }

  async function clearKey (): Promise<void> {
    if (await auth.saveKeys({ [p.value]: '' })) {
      notify.success(t('notice.keyRemoved'))
      emit('key-changed')
    } else {
      notify.error(auth.error, t('notice.saveFailed'))
    }
  }

  function asInt (raw: unknown): number | null {
    const value = Number(String(raw ?? '').trim())
    return Number.isInteger(value) && value >= 0 ? value : null
  }
</script>

<template>
  <v-card border class="pa-4" :class="{ 'source--off': !source.available }" flat>
    <!-- Hlavička -->
    <div class="d-flex align-center flex-wrap ga-2">
      <span class="text-title-large font-weight-medium">{{ t(`sources.${source.provider}.name`) }}</span>

      <v-chip :color="source.paid ? 'secondary' : 'positive'" label size="x-small" variant="tonal">
        {{ source.paid ? t('sources.paid') : t('sources.free') }}
      </v-chip>

      <v-chip v-if="source.key" :color="source.key.is_set ? 'positive' : undefined" size="x-small" variant="tonal">
        {{ source.key.is_set ? source.key.hint : t('sources.noKey') }}
      </v-chip>

      <v-spacer />
      <span v-if="usage && source.available" class="text-body-small text-medium-emphasis">{{ usage }}</span>
    </div>

    <div class="text-body-medium text-medium-emphasis mt-1">{{ t(`sources.${source.provider}.about`) }}</div>

    <v-alert
      v-if="source.provider === 'brickeconomy' || source.provider === 'brickset'"
      class="mt-2"
      density="compact"
      type="info"
      variant="tonal"
    >
      <span class="text-body-small">{{ t('sources.ownDataOnly') }}</span>
      <span v-if="source.provider === 'brickeconomy'" class="text-body-small"> {{ t('sources.personalLicense') }}</span>
    </v-alert>

    <!-- Kľúč -->
    <div v-if="source.key" class="mt-3">
      <v-text-field
        v-model="keyDraft"
        autocomplete="off"
        density="comfortable"
        hide-details
        :label="t('sources.key')"
        :placeholder="source.key.is_set ? t('settings.keyKeep') : t('settings.keyEmpty')"
        :type="showKey ? 'text' : 'password'"
        variant="outlined"
        @keyup.enter="saveKey"
      >
        <template #append-inner>
          <v-btn
            density="comfortable"
            :icon="showKey ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
            size="small"
            variant="text"
            @click="showKey = !showKey"
          />
        </template>
      </v-text-field>

      <div class="d-flex align-center flex-wrap ga-2 mt-2">
        <v-btn
          color="primary"
          :disabled="!keyDraft.trim()"
          :loading="savingKey"
          size="small"
          variant="flat"
          @click="saveKey"
        >{{ t('settings.keysSave') }}</v-btn>

        <v-btn
          v-if="source.key.is_set"
          prepend-icon="mdi-delete-outline"
          size="small"
          variant="text"
          @click="clearKey"
        >
          {{ t('settings.keyClear') }}
        </v-btn>

        <v-spacer />

        <v-btn :href="t(`sources.${source.provider}.keyUrl`)" size="small" target="_blank" variant="text">
          {{ t('settings.keyWhere') }}
        </v-btn>
      </div>
    </div>

    <!-- Čo odomkne -->
    <div class="mt-3">
      <div class="text-body-small text-medium-emphasis">
        {{ source.available ? t('sources.unlocks') : t('sources.wouldUnlock') }}
      </div>

      <ul class="unlocks text-body-medium">
        <li v-for="line in unlocks" :key="line">{{ line }}</li>
      </ul>
    </div>

    <!-- Prepínače volaní -->
    <template v-if="source.available">
      <v-divider class="my-3" />
      <div class="text-title-small mb-1">{{ t('sources.calls') }}</div>

      <div v-for="cap in source.capabilities" :key="cap.key" class="cap-row">
        <v-switch
          color="primary"
          density="compact"
          :disabled="cap.required"
          hide-details
          :model-value="cap.enabled"
          @update:model-value="value => emit('toggle', cap.key, Boolean(value))"
        >
          <template #label>
            <span class="text-body-medium">{{ t(`capabilities.${cap.key}.title`) }}</span>

            <v-chip
              v-if="cap.required"
              class="ms-2"
              label
              size="x-small"
              variant="tonal"
            >{{ t('sources.required') }}</v-chip>

            <v-chip
              v-else-if="cap.counted"
              class="ms-2"
              label
              size="x-small"
              variant="tonal"
            >{{ t('sources.counted') }}</v-chip>

            <v-chip
              v-if="cap.background"
              class="ms-1"
              label
              size="x-small"
              variant="tonal"
            >{{ t('sources.background') }}</v-chip>
          </template>
        </v-switch>

        <div class="cap-hint text-body-small text-medium-emphasis">
          {{ t(`capabilities.${cap.key}.hint`) }}
          <template v-if="brings(cap.key)"><br>{{ t('sources.brings', { what: brings(cap.key) }) }}</template>
        </div>
      </div>

      <!-- Rezerva a dávka -->
      <div v-if="source.reserve !== null || source.price_batch !== null" class="d-flex flex-wrap ga-3 mt-3">
        <v-text-field
          v-if="source.reserve !== null"
          density="compact"
          :hint="t('sources.reserveHint')"
          inputmode="numeric"
          :label="t('sources.reserve')"
          :model-value="source.reserve"
          persistent-hint
          style="max-width: 260px"
          variant="outlined"
          @change="(e: Event) => { const v = asInt((e.target as HTMLInputElement).value); if (v !== null) emit('reserve', source.provider, v) }"
        />

        <v-text-field
          v-if="source.price_batch !== null"
          density="compact"
          :hint="t('sources.batchHint')"
          inputmode="numeric"
          :label="t('sources.batch')"
          :model-value="source.price_batch"
          persistent-hint
          style="max-width: 260px"
          variant="outlined"
          @change="(e: Event) => { const v = asInt((e.target as HTMLInputElement).value); if (v !== null && v > 0) emit('batch', v) }"
        />
      </div>

      <!-- Doplnenie kúpnej ceny z odporúčanej pri obnove cien -->
      <div v-if="source.auto_purchase_price !== null && source.auto_purchase_price !== undefined" class="cap-row mt-3">
        <v-switch
          color="primary"
          density="compact"
          hide-details
          :label="t('sources.autoPurchase')"
          :model-value="source.auto_purchase_price"
          @update:model-value="value => emit('auto-purchase', Boolean(value))"
        />

        <div class="cap-hint text-body-small text-medium-emphasis">{{ t('sources.autoPurchaseHint') }}</div>
      </div>

      <!-- Obnova cien patrí ku kľúču cien -->
      <div v-if="source.provider === 'brickeconomy' && auth.can('brickeconomy.prices')" class="mt-3">
        <v-btn
          :disabled="prices.quotaExhausted"
          :loading="prices.running"
          prepend-icon="mdi-refresh"
          size="small"
          variant="outlined"
          @click="prices.refreshEverything()"
        >{{ t('prices.refreshAll') }}</v-btn>
      </div>
    </template>
  </v-card>
</template>

<style scoped>
.source--off {
  opacity: 0.75;
}

.unlocks {
  margin: 4px 0 0;
  padding-left: 20px;
}

.cap-row + .cap-row {
  margin-top: 6px;
}

.cap-hint {
  padding-left: 52px;
  margin-top: -4px;
}
</style>
