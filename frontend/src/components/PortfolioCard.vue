<script setup lang="ts">
  import type { TimelinePoint } from '@/api/types'
  /**
   * Hodnota portfólia s výberom obdobia.
   *
   * Rýchle voľby (mesiac až všetko), vlastné od–do a ťahanie v grafe sú
   * jeden a ten istý rozsah. Pre krátke obdobie sa dotiahnu denné body,
   * inak stačia týždenné zo Zbierky; denné sa pýtajú raz a potom sa držia.
   * Zvolené obdobie si pamätá prehliadač, je to pohodlie jedného diváka.
   */
  import { computed, ref, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { api } from '@/api/client'
  import DateField from '@/components/DateField.vue'
  import PortfolioChart from '@/components/PortfolioChart.vue'
  import { onPageReload } from '@/composables/usePageLoad'
  import { useCollectionStore } from '@/stores/collection'

  type Preset = '1m' | '3m' | '6m' | '1y' | 'ytd' | 'all' | 'custom'

  const props = defineProps<{ weekly: TimelinePoint[] }>()

  const { t } = useI18n()

  const DAY = 86_400_000
  const DAILY_UP_TO = 186 * DAY
  const STORAGE_KEY = 'moje-kocky.portfolio-range'
  const PRESETS: Set<Exclude<Preset, 'custom'>> = new Set(['1m', '3m', '6m', '1y', 'ytd', 'all'])

  function loadPreset (): Preset {
    try {
      const saved = localStorage.getItem(STORAGE_KEY)
      return PRESETS.has(saved as Exclude<Preset, 'custom'>) ? saved as Preset : '1y'
    } catch {
      return '1y'
    }
  }

  const preset = ref<Preset>(loadPreset())
  const from = ref<number | null>(null)
  const to = ref<number | null>(null)
  const daily = ref<TimelinePoint[] | null>(null)
  const loadingDaily = ref(false)

  function startOfDay (ms: number): number {
    const d = new Date(ms)
    d.setHours(0, 0, 0, 0)
    return d.getTime()
  }

  /** Rozsah pre rýchlu voľbu, počítaný od dnes. */
  function presetRange (value: Exclude<Preset, 'custom'>): [number | null, number | null] {
    const now = Date.now()
    const back = (months: number): number => {
      const d = new Date(now)
      d.setMonth(d.getMonth() - months)
      return startOfDay(d.getTime())
    }
    switch (value) {
      case '1m': { return [back(1), now] }
      case '3m': { return [back(3), now] }
      case '6m': { return [back(6), now] }
      case '1y': { return [back(12), now] }
      case 'ytd': { return [new Date(new Date(now).getFullYear(), 0, 1).getTime(), now] }
      default: { return [null, null] }
    }
  }

  function applyPreset (value: Preset): void {
    if (value === 'custom') return
    const [start, end] = presetRange(value)
    from.value = start
    to.value = end
    try {
      localStorage.setItem(STORAGE_KEY, value)
    } catch {
      // Súkromné okno alebo zablokované úložisko: len si to nezapamätáme.
    }
  }

  // Opätovné kliknutie na zvolenú voľbu by ju zrušilo; vtedy ostane, čo bolo.
  watch(preset, (value, previous) => {
    if (value === null || value === undefined) {
      preset.value = previous ?? 'all'
      return
    }
    applyPreset(value)
  }, { immediate: true })

  /**
   * Dĺžka toho, čo je naozaj vidno. „Rok“ pri dvojmesačnej histórii sú
   * dva mesiace, a tie si zaslúžia denné body.
   */
  const span = computed(() => {
    const first = props.weekly[0]
    const historyStart = first ? new Date(first.day).getTime() : Date.now()
    const start = Math.max(from.value ?? historyStart, historyStart)
    return (to.value ?? Date.now()) - start
  })

  const collection = useCollectionStore()

  const useDaily = computed(() => span.value <= DAILY_UP_TO)

  watch(useDaily, async needDaily => {
    if (!needDaily || daily.value !== null || loadingDaily.value) return
    loadingDaily.value = true
    const { data } = await api.GET('/stats/timeline', {
      params: { query: { step: 'day', ...collection.statsQuery() } },
    })
    daily.value = data ?? []
    loadingDaily.value = false
  }, { immediate: true })

  /** Denný rad znova, ak už bol stiahnutý; týždenný prichádza s Prehľadom. */
  async function reloadDaily (): Promise<void> {
    if (daily.value === null) return
    const { data } = await api.GET('/stats/timeline', {
      params: { query: { step: 'day', ...collection.statsQuery() } },
    })
    daily.value = data ?? []
  }

  // Prepínač dnešných peňazí: denný rad sa musí stiahnuť znova.
  watch(() => [collection.real, collection.scope], reloadDaily)
  // Tlačidlo Obnoviť stránku v hornej lište.
  onPageReload(reloadDaily)

  const points = computed(() => (useDaily.value && daily.value ? daily.value : props.weekly))

  // --- polia od–do --------------------------------------------------------

  function toInput (ms: number | null): string {
    if (ms === null) return ''
    const d = new Date(ms)
    const pad = (n: number): string => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
  }

  const fromInput = computed(() => toInput(from.value))
  const toInputValue = computed(() => toInput(to.value))

  function setEdge (edge: 'from' | 'to', raw: string): void {
    const ms = raw ? new Date(`${raw}T00:00:00`).getTime() : null
    if (ms !== null && Number.isNaN(ms)) return
    if (edge === 'from') from.value = ms
    else to.value = ms === null ? null : ms + DAY - 1
    preset.value = 'custom'
  }

  /** Ťahanie alebo priblíženie v grafe je tiež vlastné obdobie. */
  function onRange (start: number, end: number): void {
    from.value = start
    to.value = end
    preset.value = 'custom'
  }

  function showAll (): void {
    preset.value = 'all'
    applyPreset('all')
  }
</script>

<template>
  <v-card border class="pa-4 h-100 d-flex flex-column" flat>
    <div class="d-flex align-start ga-3 flex-wrap mb-2">
      <div>
        <div class="text-title-large font-weight-medium">{{ t('dashboard.chartTitle') }}</div>
        <div class="text-body-small text-medium-emphasis">{{ t('dashboard.chartHint') }}</div>
      </div>

      <v-spacer />

      <v-btn-toggle
        v-model="preset"
        density="compact"
        divided
        variant="outlined"
      >
        <v-btn v-for="value in PRESETS" :key="value" size="small" :value="value">
          {{ t(`dashboard.range.${value}`) }}
        </v-btn>
      </v-btn-toggle>
    </div>

    <div class="d-flex align-center flex-wrap ga-2 mb-2">
      <DateField
        class="range-field"
        density="compact"
        hide-details
        :label="t('filters.from')"
        :model-value="fromInput"
        @update:model-value="setEdge('from', String($event ?? ''))"
      />

      <DateField
        class="range-field"
        density="compact"
        hide-details
        :label="t('filters.to')"
        :model-value="toInputValue"
        @update:model-value="setEdge('to', String($event ?? ''))"
      />

      <v-btn
        v-if="preset !== 'all'"
        prepend-icon="mdi-arrow-expand-horizontal"
        size="small"
        variant="text"
        @click="showAll"
      >{{ t('dashboard.range.showAll') }}</v-btn>

      <v-progress-circular
        v-if="loadingDaily"
        color="primary"
        indeterminate
        size="18"
        width="2"
      />
    </div>

    <div class="flex-grow-1" style="min-height: 260px">
      <PortfolioChart :from="from" :points="points" :to="to" @range="onRange" />
    </div>
  </v-card>
</template>

<style scoped>
.range-field {
  flex: 0 1 170px;
}
</style>
