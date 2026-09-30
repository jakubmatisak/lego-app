<script setup lang="ts">
  /** Rozdelenie zbierky podľa tém. Počíta sa počet setov, nie kusov. */
  import type { Summary } from '@/api/types'
  import { ArcElement, Chart as ChartJS, Legend, Tooltip } from 'chart.js'
  import { computed } from 'vue'
  import { Doughnut } from 'vue-chartjs'
  import { useI18n } from 'vue-i18n'
  import { CHART_COLORS } from '@/plugins/vuetify'
  import { percent } from '@/utils/format'

  ChartJS.register(ArcElement, Tooltip, Legend)

  const props = defineProps<{ themes: Summary['themes'] }>()
  const { t } = useI18n()

  const top = computed(() => props.themes.slice(0, 6))

  const chartData = computed(() => ({
    labels: top.value.map(t => t.theme),
    datasets: [
      {
        data: top.value.map(t => t.count),
        backgroundColor: CHART_COLORS.themes,
        borderWidth: 0,
        hoverOffset: 4,
      },
    ],
  }))

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    cutout: '62%',
    plugins: { legend: { display: false } },
  }

  const total = computed(() => top.value.reduce((sum, t) => sum + t.count, 0))
</script>

<template>
  <div class="d-flex align-center ga-4 flex-wrap">
    <div class="theme-donut">
      <Doughnut :data="chartData" :options="chartOptions" />

      <div class="theme-donut__center text-center">
        <div class="text-title-large font-weight-medium">{{ total }}</div>
        <div class="text-body-small text-medium-emphasis">{{ t('dashboard.donutSetsPlural', total) }}</div>
      </div>
    </div>

    <div class="d-flex flex-column ga-2 flex-grow-1 theme-donut__legend">
      <div
        v-for="(slice, index) in top"
        :key="slice.theme"
        class="d-flex align-center ga-2 text-body-medium"
      >
        <span
          class="theme-donut__swatch"
          :style="{ background: CHART_COLORS.themes[index % CHART_COLORS.themes.length] }"
        />

        <span class="text-truncate">{{ slice.theme }}</span>
        <span class="ms-auto text-medium-emphasis">{{ percent(slice.pct, { decimals: 0, sign: false }) }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.theme-donut {
  position: relative;
  width: 124px;
  height: 124px;
  flex-shrink: 0;
}

.theme-donut__center {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}

.theme-donut__swatch {
  width: 10px;
  height: 10px;
  border-radius: 3px;
  flex-shrink: 0;
}

.theme-donut__legend {
  min-width: 150px;
}
</style>
