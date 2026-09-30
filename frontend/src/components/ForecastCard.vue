<script setup lang="ts">
/**
 * Odhad hodnoty kusov v krabici o 2 a 5 rokov.
 *
 * Porovnáva sa s dnešnou hodnotou tých istých kusov, nie celej zbierky,
 * inak by rast vyzeral menší, než je. Postavené kusy odhad nemajú.
 */
  import type { Summary } from '@/api/types'
  import { computed } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { money, percent, toNumber } from '@/utils/format'

  const props = defineProps<{ summary: Summary }>()
  const { t } = useI18n()

  const base = computed(() => toNumber(props.summary.forecast_base))

  function growth (value: string | null | undefined): number | null {
    const target = toNumber(value)
    if (target === null || base.value === null || base.value <= 0) return null
    return ((target - base.value) / base.value) * 100
  }

  const rows = computed(() => [
    { label: t('insights.forecast2y'), value: props.summary.forecast_2y, pct: growth(props.summary.forecast_2y) },
    { label: t('insights.forecast5y'), value: props.summary.forecast_5y, pct: growth(props.summary.forecast_5y) },
  ])
</script>

<template>
  <v-card border class="pa-4 h-100 d-flex flex-column ga-3" flat>
    <div class="text-title-large font-weight-medium">{{ t('insights.forecastTitle') }}</div>

    <template v-if="summary.forecast_sample > 0">
      <div>
        <div class="text-body-small text-medium-emphasis">{{ t('insights.forecastToday') }}</div>
        <div class="text-headline-small font-weight-medium">{{ money(summary.forecast_base, { decimals: 0 }) }}</div>
      </div>

      <div class="d-flex ga-4">
        <div v-for="row in rows" :key="row.label" class="flex-grow-1">
          <div class="text-body-small text-medium-emphasis">{{ row.label }}</div>
          <div class="text-title-large font-weight-medium">{{ money(row.value, { decimals: 0 }) }}</div>

          <div
            v-if="row.pct !== null"
            class="text-body-small font-weight-medium"
            :class="row.pct >= 0 ? 'text-positive' : 'text-negative'"
          >{{ percent(row.pct, { decimals: 0 }) }}</div>
        </div>
      </div>

      <div class="text-body-small text-medium-emphasis mt-auto">
        {{ t('insights.forecastNote', { sample: summary.forecast_sample, sealed: summary.forecast_sealed }) }}
      </div>
    </template>

    <div v-else class="text-body-medium text-medium-emphasis">{{ t('insights.forecastEmpty') }}</div>
  </v-card>
</template>
