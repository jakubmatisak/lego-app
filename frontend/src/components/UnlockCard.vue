<script setup lang="ts">
  /**
   * Prehľad: čo by appka vedela navyše s kľúčmi, ktoré účet ešte nemá.
   *
   * Bez kľúča appka údaje zo služby neukáže (a niektoré sekcie skryje), takže
   * by sa človek o nich inak nedozvedel. Zoznam je z tých istých textov ako
   * karty v Nastaveniach → Dáta. Dá sa skryť; skrytie si pamätá účet a platí
   * pre služby, ktoré v tej chvíli chýbali.
   */
  import { computed, onMounted } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useAuthStore } from '@/stores/auth'
  import { useProfileStore } from '@/stores/preferences'

  const { t, tm, rt } = useI18n()
  const auth = useAuthStore()
  const profile = useProfileStore()

  const SERVICES = [
    { provider: 'rebrickable', label: 'Rebrickable', on: () => auth.can('rebrickable.set') },
    { provider: 'brickset', label: 'Brickset', on: () => auth.hasBricksetKey },
    { provider: 'brickeconomy', label: 'BrickEconomy', on: () => auth.hasPriceKey },
    { provider: 'upcitemdb', label: 'UPCitemdb', on: () => auth.can('upcitemdb.barcode') },
    { provider: 'eurostat', label: 'Eurostat', on: () => auth.can('eurostat.inflation') },
  ]

  const hidden = computed(() => {
    const raw = (profile.get('unlock') as { hidden?: unknown } | undefined)?.hidden
    return Array.isArray(raw) ? raw.map(String) : []
  })

  const missing = computed(() =>
    SERVICES
      .filter(s => !s.on() && !hidden.value.includes(s.provider))
      .map(s => ({
        ...s,
        unlocks: (tm(`sources.${s.provider}.unlocks`) as unknown[]).map(m => rt(m as never)),
      })),
  )

  function hide (): void {
    profile.save('unlock', { hidden: [...hidden.value, ...missing.value.map(s => s.provider)] })
  }

  onMounted(() => {
    profile.load()
  })
</script>

<template>
  <v-card v-if="auth.keys && missing.length > 0" border class="pa-4" flat>
    <div class="d-flex align-center ga-2 mb-2">
      <v-icon color="primary" icon="mdi-key-plus" />
      <div class="text-body-large font-weight-medium">{{ t('unlock.title') }}</div>
      <v-spacer />
      <v-btn size="small" variant="text" @click="hide">{{ t('unlock.hide') }}</v-btn>
    </div>

    <div class="text-body-medium text-medium-emphasis mb-3">{{ t('unlock.intro') }}</div>

    <div class="d-flex flex-column ga-2">
      <div v-for="s in missing" :key="s.provider" class="unlock-row">
        <div class="text-body-medium font-weight-medium">{{ s.label }}</div>
        <div class="text-body-medium text-medium-emphasis">{{ s.unlocks.join(' · ') }}</div>
      </div>
    </div>

    <v-btn
      class="mt-3"
      color="primary"
      prepend-icon="mdi-cog-outline"
      :to="{ name: 'settings', query: { tab: 'data' } }"
      variant="tonal"
    >{{ t('unlock.connect') }}</v-btn>
  </v-card>
</template>

<style scoped>
  .unlock-row {
    display: grid;
    grid-template-columns: 120px 1fr;
    gap: 8px;
  }

  @media (max-width: 600px) {
    .unlock-row {
      grid-template-columns: 1fr;
      gap: 0;
    }
  }
</style>
