<script setup lang="ts">
  /**
   * Vývoj trhovej ceny jedného setu: nový a použitý kus a k tomu kúpna cena.
   *
   * História prichádza s každou obnovou ceny zadarmo (`price_events_*`),
   * graf teda nestojí žiadne volanie navyše. Body nového a použitého kusu
   * majú rôzne dátumy, preto je os x číselná (čas v ms), nie kategórie:
   * rozostupy tak zodpovedajú času a netreba knižnicu na dátumy.
   */
  import type { PricePoint } from '@/api/types'
  import {
    Chart as ChartJS,
    Legend,
    LinearScale,
    LineElement,
    PointElement,
    Tooltip,
  } from 'chart.js'
  import { computed } from 'vue'
  import { Line } from 'vue-chartjs'
  import { useI18n } from 'vue-i18n'
  import { useTheme } from 'vuetify'
  import { CHART_COLORS } from '@/plugins/vuetify'
  import { amount, displayCurrency, pricesHidden, toDisplay, toNumber } from '@/utils/format'

  ChartJS.register(LinearScale, PointElement, LineElement, Tooltip, Legend)

  const props = defineProps<{
    newPoints: PricePoint[]
    usedPoints: PricePoint[]
    /** Priemerná kúpna cena vlastnených kusov, ak ju poznáme. */
    purchase: number | null
  }>()

  const { t } = useI18n()
  const theme = useTheme()

  const gridColor = computed(() =>
    theme.current.value.dark ? 'rgba(255,255,255,0.09)' : 'rgba(0,0,0,0.08)',
  )
  const textColor = computed(() =>
    theme.current.value.dark ? '#A9A4A3' : '#5C5B5B',
  )

  /**
   * Jeden bod na deň, posledný z neho. Aktuálna cena sa ukladá pri každej
   * obnove, takže tri obnovy za deň by inak spravili tri body nad sebou.
   */
  function series (points: PricePoint[]): { x: number, y: number }[] {
    const byDay = new Map<string, { x: number, y: number }>()
    for (const p of points) {
      const y = toNumber(p.avg_price)
      if (y === null || y <= 0) continue
      const x = new Date(p.captured_at).getTime()
      const day = p.captured_at.slice(0, 10)
      const seen = byDay.get(day)
      // Body v mene zobrazenia, aby osi mali okrúhle sumy v nej.
      if (!seen || seen.x < x) byDay.set(day, { x, y: toDisplay(y) })
    }
    return [...byDay.values()].toSorted((a, b) => a.x - b.x)
  }

  const newSeries = computed(() => series(props.newPoints))
  const usedSeries = computed(() => series(props.usedPoints))

  /** Graf má zmysel od dvoch rôznych dní v aspoň jednej krivke. */
  const hasData = computed(() => newSeries.value.length > 1 || usedSeries.value.length > 1)

  const span = computed(() => {
    const xs = [...newSeries.value, ...usedSeries.value].map(p => p.x)
    return { min: Math.min(...xs), max: Math.max(...xs) }
  })

  const dayFormat = new Intl.DateTimeFormat('sk-SK', { day: 'numeric', month: 'numeric', year: 'numeric' })
  const monthFormat = new Intl.DateTimeFormat('sk-SK', { month: 'short', year: 'numeric' })
  const shortDayFormat = new Intl.DateTimeFormat('sk-SK', { day: 'numeric', month: 'numeric' })
  /** Pri pár týždňoch deň a mesiac, pri dlhšej histórii mesiac a rok. */
  const tickFormat = computed(() =>
    span.value.max - span.value.min < 120 * 86_400_000 ? shortDayFormat : monthFormat,
  )

  /**
   * Pri lacnej figúrke sa cena hýbe o centy a celé eurá by na osi dali
   * desaťkrát „4 €“. Desatinné miesta len vtedy, keď je rozpätie malé.
   */
  const yDecimals = computed(() => {
    const ys = [...newSeries.value, ...usedSeries.value].map(p => p.y)
    if (props.purchase !== null) ys.push(toDisplay(props.purchase))
    return ys.length > 0 && Math.max(...ys) - Math.min(...ys) < 10 ? 2 : 0
  })

  const chartData = computed(() => {
    const datasets = []
    if (newSeries.value.length > 0) {
      datasets.push({
        label: t('detail.historyNew'),
        data: newSeries.value,
        borderColor: CHART_COLORS.value,
        backgroundColor: CHART_COLORS.value,
        borderWidth: 2.4,
        tension: 0.2,
        pointRadius: 2.5,
        pointHoverRadius: 5,
      })
    }
    if (usedSeries.value.length > 0) {
      datasets.push({
        label: t('detail.historyUsed'),
        data: usedSeries.value,
        borderColor: CHART_COLORS.themes[2],
        backgroundColor: CHART_COLORS.themes[2],
        borderWidth: 2.4,
        tension: 0.2,
        pointRadius: 2.5,
        pointHoverRadius: 5,
      })
    }
    if (props.purchase !== null) {
      datasets.push({
        label: t('detail.historyPurchase'),
        data: [
          { x: span.value.min, y: toDisplay(props.purchase) },
          { x: span.value.max, y: toDisplay(props.purchase) },
        ],
        borderColor: CHART_COLORS.invested,
        backgroundColor: CHART_COLORS.invested,
        borderDash: [5, 4],
        borderWidth: 1.6,
        pointRadius: 0,
        pointHoverRadius: 0,
      })
    }
    return { datasets }
  })

  const chartOptions = computed(() => ({
    // Nový objekt pri skrytí cien: graf prekreslí osi aj popisy so sumami.
    hiddenPrices: pricesHidden.value,
    // Aj pri zmene meny zobrazenia: body sú prepočítané, osi v novej mene.
    displayCurrency: displayCurrency.value.code,
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'nearest' as const, intersect: false },
    plugins: {
      legend: {
        position: 'bottom' as const,
        align: 'start' as const,
        labels: { boxWidth: 12, boxHeight: 3, color: textColor.value, font: { size: 11 } },
      },
      tooltip: {
        callbacks: {
          title: (items: { parsed: { x: number | null } }[]) =>
            items[0]?.parsed.x == null ? '' : dayFormat.format(new Date(items[0].parsed.x)),
          label: (ctx: { dataset: { label?: string }, parsed: { y: number | null } }) =>
            `${ctx.dataset.label}: ${amount(ctx.parsed.y)}`,
        },
      },
    },
    scales: {
      x: {
        type: 'linear' as const,
        min: span.value.min,
        max: span.value.max,
        grid: { display: false },
        ticks: {
          color: textColor.value,
          font: { size: 10 },
          maxTicksLimit: 6,
          callback: (value: string | number) => tickFormat.value.format(new Date(Number(value))),
        },
      },
      y: {
        grid: { color: gridColor.value },
        border: { display: false },
        ticks: {
          color: textColor.value,
          font: { size: 10 },
          callback: (value: string | number) => amount(value, { decimals: yDecimals.value }),
        },
      },
    },
  }))
</script>

<template>
  <div v-if="hasData">
    <div class="text-body-small text-medium-emphasis mb-1">{{ t('detail.historyTitle') }}</div>

    <div class="price-history">
      <Line :data="chartData" :options="chartOptions" />
    </div>
  </div>
</template>

<style scoped>
.price-history {
  height: 220px;
  position: relative;
}
</style>
