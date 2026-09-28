<script setup lang="ts">
  /**
   * Tri krivky v čase: viazaný kapitál, trhová hodnota a kumulatívny
   * výnos z predajov. Predaný kus ku dňu predaja vypadne z prvých dvoch
   * a objaví sa v tretej, takže sa nič nepočíta dvakrát.
   *
   * Os x je čas v milisekundách, nie kategórie: rozsah od–do je potom len
   * ``min`` a ``max`` osi a ťahanie aj priblíženie fungujú prirodzene.
   * Ťahanie posúva, Ctrl + koliesko (na telefóne dva prsty) približuje.
   * Obyčajné koliesko necháva stránke, inak by sa Prehľad nedal posúvať.
   */
  import type { TimelinePoint } from '@/api/types'
  import type { Chart } from 'chart.js'
  import {
    Chart as ChartJS,
    Filler,
    Legend,
    LinearScale,
    LineElement,
    PointElement,
    Tooltip,
  } from 'chart.js'
  import zoomPlugin from 'chartjs-plugin-zoom'
  import { computed } from 'vue'
  import { Line } from 'vue-chartjs'
  import { useI18n } from 'vue-i18n'
  import { useTheme } from 'vuetify'
  import { CHART_COLORS } from '@/plugins/vuetify'
  import { money, pricesHidden, toNumber } from '@/utils/format'

  ChartJS.register(LinearScale, PointElement, LineElement, Filler, Tooltip, Legend, zoomPlugin)

  const DAY = 86_400_000

  const props = defineProps<{
    points: TimelinePoint[]
    /** Viditeľný rozsah v ms. Bez neho celá história. */
    from?: number | null
    to?: number | null
  }>()
  const emit = defineEmits<{ range: [from: number, to: number] }>()

  const { t } = useI18n()
  const theme = useTheme()

  const gridColor = computed(() =>
    theme.current.value.dark ? 'rgba(255,255,255,0.09)' : 'rgba(0,0,0,0.08)',
  )
  const textColor = computed(() =>
    theme.current.value.dark ? '#A9A4A3' : '#5C5B5B',
  )

  const xs = computed(() => props.points.map(p => new Date(p.day).getTime()))
  const dataMin = computed(() => xs.value[0] ?? 0)
  const dataMax = computed(() => xs.value.at(-1) ?? 0)
  const shownMin = computed(() => Math.max(props.from ?? dataMin.value, dataMin.value))
  const shownMax = computed(() => Math.min(props.to ?? dataMax.value, dataMax.value))

  function series (pick: (p: TimelinePoint) => string | null): { x: number, y: number }[] {
    return props.points.map((p, i) => ({ x: xs.value[i] ?? 0, y: toNumber(pick(p)) ?? 0 }))
  }

  const chartData = computed(() => ({
    datasets: [
      {
        label: t('dashboard.legendValue'),
        data: series(p => p.market_value),
        borderColor: CHART_COLORS.value,
        backgroundColor: 'rgba(208, 16, 18, 0.10)',
        borderWidth: 2.6,
        fill: true,
        tension: 0.25,
        pointRadius: 0,
        pointHoverRadius: 5,
      },
      {
        label: t('dashboard.legendInvested'),
        data: series(p => p.invested),
        borderColor: CHART_COLORS.invested,
        borderDash: [5, 4],
        borderWidth: 2,
        fill: false,
        tension: 0.25,
        pointRadius: 0,
        pointHoverRadius: 5,
      },
      {
        label: t('dashboard.legendProceeds'),
        data: series(p => p.proceeds),
        borderColor: CHART_COLORS.proceeds,
        borderDash: [2, 3],
        borderWidth: 2,
        fill: false,
        tension: 0.25,
        pointRadius: 0,
        pointHoverRadius: 5,
      },
    ],
  }))

  const dayFormat = new Intl.DateTimeFormat('sk-SK', { day: 'numeric', month: 'numeric', year: 'numeric' })
  const shortDay = new Intl.DateTimeFormat('sk-SK', { day: 'numeric', month: 'numeric' })
  const monthFormat = new Intl.DateTimeFormat('sk-SK', { month: 'short', year: '2-digit' })

  /** Pri pár mesiacoch deň a mesiac, pri dlhšom rozsahu mesiac a rok. */
  const tickFormat = computed(() => (shownMax.value - shownMin.value < 120 * DAY ? shortDay : monthFormat))

  /** Po ťahaní alebo priblížení povie rodičovi, čo je vidno, aby sedeli polia od–do. */
  function report ({ chart }: { chart: Chart }): void {
    const scale = chart.scales.x
    if (scale) emit('range', Math.round(scale.min), Math.round(scale.max))
  }

  const chartOptions = computed(() => ({
    // Nový objekt pri skrytí cien: graf prekreslí osi aj popisy so sumami.
    hiddenPrices: pricesHidden.value,
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index' as const, intersect: false },
    plugins: {
      legend: {
        position: 'bottom' as const,
        align: 'start' as const,
        labels: {
          boxWidth: 12,
          boxHeight: 3,
          usePointStyle: false,
          color: textColor.value,
          font: { size: 11 },
        },
      },
      tooltip: {
        callbacks: {
          title: (items: { parsed: { x: number | null } }[]) =>
            items[0]?.parsed.x == null ? '' : dayFormat.format(new Date(items[0].parsed.x)),
          label: (ctx: { dataset: { label?: string }, parsed: { y: number | null } }) =>
            `${ctx.dataset.label}: ${money(ctx.parsed.y, { decimals: 0 })}`,
        },
      },
      zoom: {
        pan: { enabled: true, mode: 'x' as const, onPanComplete: report },
        zoom: {
          wheel: { enabled: true, modifierKey: 'ctrl' as const },
          pinch: { enabled: true },
          mode: 'x' as const,
          onZoomComplete: report,
        },
        // Mimo histórie sa posunúť nedá a pod týždeň sa nepribližuje.
        limits: { x: { min: dataMin.value, max: dataMax.value, minRange: 7 * DAY } },
      },
    },
    scales: {
      x: {
        type: 'linear' as const,
        min: shownMin.value,
        max: shownMax.value,
        grid: { display: false },
        ticks: {
          color: textColor.value,
          font: { size: 10 },
          maxTicksLimit: 7,
          callback: (value: string | number) => tickFormat.value.format(new Date(Number(value))),
        },
      },
      y: {
        beginAtZero: true,
        grid: { color: gridColor.value },
        border: { display: false },
        ticks: {
          color: textColor.value,
          font: { size: 10 },
          callback: (value: string | number) => money(value, { decimals: 0 }),
        },
      },
    },
  }))
</script>

<template>
  <div class="portfolio-chart">
    <Line :data="chartData" :options="chartOptions" />
  </div>
</template>

<style scoped>
.portfolio-chart {
  cursor: grab;
  height: 100%;
  min-height: 200px;
  position: relative;
}

.portfolio-chart:active {
  cursor: grabbing;
}
</style>
