<script setup lang="ts">
  import type { CmfSeries, CmfSync } from '@/api/types'
  import type { SeriesColumn, SeriesSort, StateFilter } from '@/utils/seriesList'
  /**
   * Figúrky: všetky zberateľské série a koľko z každej mám.
   *
   * Zoznam pochádza z Rebrickable a sťahuje sa na pozadí. Otvorenie stránky
   * raz za týždeň samo skontroluje, či nevyšla nová séria; kým sťahovanie
   * beží, stránka sa každé dve sekundy pozrie na stav a potom sa obnoví.
   *
   * Filter a zoradenie sú v adrese stránky, takže návrat z detailu série
   * vráti presne ten istý pohľad.
   *
   * Zberateľské minifigúrky sú hlavná kategória. Blind-box série iných radov
   * (Mighty Machines, Super Mario, VIDIYO…) majú každá svoju kategóriu,
   * aby sa nemiešali medzi minifigúrky.
   */
  import type { LocationQueryValue } from 'vue-router'
  import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useRoute, useRouter } from 'vue-router'
  import { api, errorMessage } from '@/api/client'
  import CardGrid from '@/components/CardGrid.vue'
  import LoadFailed from '@/components/LoadFailed.vue'
  import PageSkeleton from '@/components/PageSkeleton.vue'
  import SeriesBar from '@/components/SeriesBar.vue'
  import SetImage from '@/components/SetImage.vue'
  import SortHeader from '@/components/SortHeader.vue'
  import { useMinifigsView } from '@/composables/useMinifigsView'
  import { usePageLoad } from '@/composables/usePageLoad'
  import { imageSrc } from '@/utils/imageSrc'
  import {
    compareSeries,
    matchesState,
    MENU_SERIES_SORTS,
    SERIES_SORTS,
    seriesHeaderDir,
    seriesSortFromHeader,
    seriesState,
  } from '@/utils/seriesList'

  type Filter = StateFilter
  type Kind = 'all' | 'numbered' | 'themed'
  type Sort = SeriesSort

  /** Kategória zberateľských minifigúrok, rovnako ako na serveri. */
  const MINIFIGS = 'minifigs'
  const FILTERS: Set<Filter> = new Set(['all', 'collecting', 'almost', 'complete', 'untouched'])
  const KINDS: Kind[] = ['all', 'numbered', 'themed']
  const SORTS: readonly Sort[] = SERIES_SORTS
  /** Stĺpce tabuľky, ktoré radia; fotka nie. */
  const COLUMNS: Array<{ key: SeriesColumn, title: string, class?: string }> = [
    { key: 'name', title: 'minifigs.colSeries' },
    { key: 'year', title: 'minifigs.colYear' },
    { key: 'owned', title: 'minifigs.colOwned', class: 'text-end' },
    { key: 'missing', title: 'minifigs.colMissing', class: 'text-end' },
    { key: 'progress', title: 'minifigs.colProgress', class: 'minifigs-table__progress' },
  ]
  /** Číslovaná séria („Series 28 Minifigures“), ostatné sú tematické (Disney, Marvel…). */
  const NUMBERED = /^series \d+/i

  const { t, locale } = useI18n()
  const route = useRoute()
  const router = useRouter()

  const series = ref<CmfSeries[]>([])
  const sync = ref<CmfSync | null>(null)
  /** Chyba sťahovania sérií; chybu načítania zoznamu ukáže LoadFailed. */
  const error = ref<string | null>(null)
  const filter = ref<Filter>('all')
  const search = ref('')
  const kind = ref<Kind>('all')
  /** Kategória: `minifigs`, alebo názov radu (napríklad „Technic – Mighty Machines“). */
  const category = ref(MINIFIGS)
  const years = ref<number[]>([])
  const sort = ref<Sort>('leastMissing')
  let poll: ReturnType<typeof setTimeout> | null = null
  /** Karty alebo tabuľka, voľba pri účte (`preferences.minifigs.list`). */
  const { tableView, setView } = useMinifigsView('list')

  async function load (): Promise<boolean> {
    const { data, error: err } = await api.GET('/minifigs/series', {})
    if (err || !data) return false
    series.value = data.series
    sync.value = data.sync
    watchSync()
    return true
  }

  /** Prvé načítanie kostra, ďalšie (po sťahovaní, Obnoviť stránku) nad starými kartami. */
  const page = usePageLoad(load)

  /** Kým sťahovanie beží, pýtať sa na stav; po dobehnutí načítať zoznam znova. */
  function watchSync (): void {
    if (poll !== null || !sync.value?.running) return
    poll = setTimeout(async () => {
      poll = null
      const { data } = await api.GET('/minifigs/sync', {})
      if (!data) return
      const finished = sync.value?.running && !data.running
      sync.value = data
      if (finished) await page.run()
      else watchSync()
    }, 2000)
  }

  async function startSync (): Promise<void> {
    const { data, error: err } = await api.POST('/minifigs/sync', { params: { query: {} } })
    if (err || !data) {
      error.value = errorMessage(err, t('minifigs.syncFailed'))
      return
    }
    sync.value = { ...data, running: true }
    watchSync()
  }

  const state = seriesState

  function kindOf (row: CmfSeries): Kind {
    return NUMBERED.test(row.name) ? 'numbered' : 'themed'
  }

  /** Roky, v ktorých nejaká séria vyšla, od najnovšieho. */
  const yearOptions = computed(() =>
    [...new Set(inCategory.value.map(r => r.year).filter((y): y is number => y !== null))].toSorted((a, b) => b - a),
  )

  /** Kategórie s počtom sérií; minifigúrky prvé, ostatné podľa abecedy. */
  const categories = computed(() => {
    const count = new Map<string, number>()
    for (const row of series.value) count.set(row.category, (count.get(row.category) ?? 0) + 1)
    if (!count.has(MINIFIGS)) count.set(MINIFIGS, 0)
    return [...count.entries()]
      .map(([value, n]) => ({ value, n, title: value === MINIFIGS ? t('minifigs.categoryMinifigs') : value }))
      .toSorted((a, b) => (a.value === MINIFIGS ? -1 : (b.value === MINIFIGS ? 1 : a.title.localeCompare(b.title))))
  })

  const isMinifigs = computed(() => category.value === MINIFIGS)
  const inCategory = computed(() => series.value.filter(row => row.category === category.value))

  const kindItems = computed(() => KINDS.map(value => ({ value, title: t(`minifigs.kind.${value}`) })))
  /**
   * Výber nad kartami má len hlavné zoradenia. Kľúč z hlavičky tabuľky
   * (mám, chýba, kompletnosť) sa doň pridá, len kým platí.
   */
  const sortItems = computed(() => {
    const keys: Sort[] = [...MENU_SERIES_SORTS]
    if (!keys.includes(sort.value)) keys.push(sort.value)
    return keys.map(value => ({ value, title: t(`minifigs.sort.${value}`) }))
  })

  /** Séria prejde hľadaním, typom a rokom. Stav (zbieram, kompletné) sa rieši zvlášť. */
  const matching = computed(() => {
    const needle = search.value.trim().toLowerCase()
    return inCategory.value
      .filter(row => !needle || row.name.toLowerCase().includes(needle) || row.series_num?.includes(needle))
      // Číslované/tematické platí len pre minifigúrky, iné rady to nemajú.
      .filter(row => !isMinifigs.value || kind.value === 'all' || kindOf(row) === kind.value)
      .filter(row => years.value.length === 0 || (row.year !== null && years.value.includes(row.year)))
  })

  /** Počty pri čipoch rátajú s hľadaním, typom a rokom, ako v paneli filtrov Zbierky. */
  const counts = computed(() => {
    const out: Record<Filter, number> = { all: 0, collecting: 0, almost: 0, complete: 0, untouched: 0 }
    for (const key of FILTERS) out[key] = matching.value.filter(row => matchesState(row, key)).length
    return out
  })

  const figures = computed(() => inCategory.value.reduce((sum, row) => sum + row.owned, 0))

  const collator = computed(() => new Intl.Collator(locale.value === 'sk' ? 'sk' : 'en', { numeric: true }))

  function compare (a: CmfSeries, b: CmfSeries): number {
    return compareSeries(a, b, sort.value, collator.value)
  }

  const shown = computed(() =>
    matching.value
      .filter(row => matchesState(row, filter.value))
      .toSorted(compare),
  )

  const hasFilters = computed(() =>
    search.value.trim() !== '' || kind.value !== 'all' || years.value.length > 0 || filter.value !== 'all',
  )

  function clearFilters (): void {
    search.value = ''
    kind.value = 'all'
    years.value = []
    filter.value = 'all'
  }

  // --- adresa stránky -------------------------------------------------------

  function first (value: LocationQueryValue | LocationQueryValue[] | undefined): string | null {
    const v = Array.isArray(value) ? value[0] : value
    return typeof v === 'string' && v !== '' ? v : null
  }

  function readRoute (): void {
    const q = route.query
    search.value = first(q.q) ?? ''
    const k = first(q.kind)
    kind.value = KINDS.includes(k as Kind) ? k as Kind : 'all'
    const f = first(q.state)
    filter.value = FILTERS.has(f as Filter) ? f as Filter : 'all'
    const so = first(q.sort)
    sort.value = SORTS.includes(so as Sort) ? so as Sort : 'leastMissing'
    category.value = first(q.cat) ?? MINIFIGS
    const rawYears = Array.isArray(q.year) ? q.year : (q.year ? [q.year] : [])
    years.value = rawYears.map(Number).filter(n => Number.isInteger(n))
  }

  /** Iná kategória má iné roky a typy; filtre z predošlej by nemuseli sedieť. */
  function selectCategory (value: string): void {
    if (value === category.value) return
    category.value = value
    kind.value = 'all'
    years.value = []
    filter.value = 'all'
  }

  watch([search, kind, years, filter, sort, category], () => {
    router.replace({
      query: {
        ...(category.value === MINIFIGS ? {} : { cat: category.value }),
        ...(search.value.trim() ? { q: search.value.trim() } : {}),
        ...(kind.value === 'all' ? {} : { kind: kind.value }),
        ...(filter.value === 'all' ? {} : { state: filter.value }),
        ...(sort.value === 'leastMissing' ? {} : { sort: sort.value }),
        ...(years.value.length > 0 ? { year: years.value.map(String) } : {}),
      },
    })
  }, { deep: true })

  const syncLabel = computed(() => {
    const s = sync.value
    if (!s?.running) return ''
    return s.total > 0 ? t('minifigs.syncProgress', { done: s.done, total: s.total }) : t('minifigs.syncStarting')
  })

  onMounted(() => {
    readRoute()
    page.run()
  })
  onBeforeUnmount(() => {
    if (poll !== null) clearTimeout(poll)
  })
</script>

<template>
  <div class="d-flex flex-column ga-4">
    <div class="d-flex align-center flex-wrap ga-2">
      <span v-if="page.loaded" class="text-body-medium text-medium-emphasis">
        {{ t(isMinifigs ? 'minifigs.summary' : 'minifigs.summaryOther', { figures, collecting: counts.collecting, complete: counts.complete }) }}
      </span>

      <v-spacer />

      <v-btn
        v-if="sync?.provider_enabled && !sync.switched_off"
        :disabled="sync.running"
        prepend-icon="mdi-cloud-download-outline"
        size="small"
        variant="outlined"
        @click="startSync"
      >{{ t('minifigs.syncCheck') }}</v-btn>
    </div>

    <v-alert
      v-if="error"
      closable
      type="error"
      variant="tonal"
      @click:close="error = null"
    >{{ error }}</v-alert>

    <v-alert
      v-if="sync && !sync.provider_enabled"
      icon="mdi-key-outline"
      type="info"
      variant="tonal"
    >
      {{ t('minifigs.needsKey') }}
      <template #append>
        <v-btn size="small" :to="{ name: 'settings', query: { tab: 'data' } }" variant="text">
          {{ t('nav.settings') }}
        </v-btn>
      </template>
    </v-alert>

    <!-- Sťahovanie sérií vypnuté: ukážu sa len série, ktoré už appka pozná. -->
    <v-alert
      v-if="sync?.provider_enabled && sync.switched_off"
      density="compact"
      icon="mdi-cloud-off-outline"
      type="info"
      variant="tonal"
    >
      {{ t('minifigs.syncSwitchedOff') }}
      <template #append>
        <v-btn size="small" :to="{ name: 'settings', query: { tab: 'data' } }" variant="text">
          {{ t('nav.settings') }}
        </v-btn>
      </template>
    </v-alert>

    <v-alert
      v-if="sync?.provider_enabled && !sync.switched_off && !sync.running && (sync.error || sync.failed)"
      type="warning"
      variant="tonal"
    >
      {{ sync.error ?? t('minifigs.syncPartial', { failed: sync.failed }) }}
      <template #append>
        <v-btn size="small" variant="text" @click="startSync">{{ t('minifigs.syncRetry') }}</v-btn>
      </template>
    </v-alert>

    <v-card v-if="sync?.running" class="pa-3" color="surface-variant" flat>
      <div class="text-body-medium mb-2">{{ syncLabel }}</div>

      <v-progress-linear
        color="primary"
        :indeterminate="sync.total === 0"
        :model-value="sync.total ? (sync.done / sync.total) * 100 : 0"
        rounded
      />
    </v-card>

    <!-- Kategórie: minifigúrky zvlášť, každý iný rad blind-box sérií zvlášť. -->
    <v-tabs
      v-if="categories.length > 1"
      color="primary"
      density="comfortable"
      :model-value="category"
      show-arrows
      @update:model-value="value => selectCategory(String(value))"
    >
      <v-tab v-for="item in categories" :key="item.value" :value="item.value">
        {{ item.title }}
        <v-chip class="ms-2" label size="x-small" variant="tonal">{{ item.n }}</v-chip>
      </v-tab>
    </v-tabs>

    <div class="d-flex align-center flex-wrap ga-3">
      <v-text-field
        v-model="search"
        class="mf-control mf-control--search"
        clearable
        density="comfortable"
        hide-details
        :label="t('minifigs.search')"
        prepend-inner-icon="mdi-magnify"
        @click:clear="search = ''"
      />

      <v-select
        v-if="isMinifigs"
        v-model="kind"
        class="mf-control"
        density="comfortable"
        hide-details
        item-title="title"
        item-value="value"
        :items="kindItems"
        :label="t('minifigs.kindLabel')"
      />

      <v-select
        v-model="years"
        chips
        class="mf-control mf-control--years"
        clearable
        closable-chips
        density="comfortable"
        hide-details
        :items="yearOptions"
        :label="t('minifigs.yearLabel')"
        multiple
      />

      <v-select
        v-model="sort"
        class="mf-control"
        density="comfortable"
        hide-details
        item-title="title"
        item-value="value"
        :items="sortItems"
        :label="t('collection.sortBy')"
        prepend-inner-icon="mdi-sort"
      />

      <v-btn-toggle
        density="comfortable"
        mandatory
        :model-value="tableView ? 'table' : 'cards'"
        variant="outlined"
        @update:model-value="value => setView(value === 'table')"
      >
        <v-btn icon="mdi-view-module-outline" :title="t('collection.viewCards')" value="cards" />
        <v-btn icon="mdi-view-headline" :title="t('collection.viewTable')" value="table" />
      </v-btn-toggle>
    </div>

    <div class="d-flex align-center flex-wrap ga-2">
      <v-chip-group v-model="filter" mandatory selected-class="text-primary">
        <v-chip v-for="key in FILTERS" :key="key" :value="key" variant="outlined">
          {{ t(`minifigs.filter.${key}`) }} · {{ counts[key] }}
        </v-chip>
      </v-chip-group>

      <v-btn v-if="hasFilters" size="small" variant="text" @click="clearFilters">{{ t('filters.clear') }}</v-btn>
    </div>

    <!-- Kým server neodpovedal, kostra; „Zatiaľ žiadne série“ až po odpovedi. -->
    <PageSkeleton v-if="page.initial" kind="cards" />

    <LoadFailed
      v-else-if="page.error"
      :loading="page.loading"
      :message="t('minifigs.loadFailed')"
      @retry="page.run()"
    />

    <v-empty-state
      v-else-if="shown.length === 0"
      icon="mdi-account-multiple-outline"
      :text="series.length === 0 ? t('minifigs.emptyHint') : t('minifigs.noMatchHint')"
      :title="series.length === 0 ? t('minifigs.empty') : t('minifigs.noMatch')"
    />

    <v-card v-else-if="tableView" border class="minifigs-table" flat>
      <v-table density="comfortable" hover>
        <thead>
          <tr>
            <th class="minifigs-table__photo" />

            <th v-for="column in COLUMNS" :key="column.key" :class="column.class">
              <SortHeader
                :dir="seriesHeaderDir(column.key, sort)"
                :title="t(column.title)"
                @sort="sort = seriesSortFromHeader(column.key, sort)"
              />
            </th>
          </tr>
        </thead>

        <tbody>
          <tr
            v-for="row in shown"
            :key="row.series_num ?? `theme-${row.theme_id}`"
            :class="{ 'series-card--untouched': state(row) === 'untouched' }"
          >
            <td class="minifigs-table__photo">
              <SetImage
                :alt="row.name"
                class="series-card__image"
                rounded="sm"
                :size="64"
                :src="imageSrc(row.image_url) ?? undefined"
              />
            </td>

            <td>
              <RouterLink
                v-if="row.series_num"
                class="minifigs-table__name"
                :to="{ name: 'minifig-series', params: { num: row.series_num } }"
              >{{ row.name }}</RouterLink>

              <span v-else class="minifigs-table__name text-medium-emphasis">{{ row.name }}</span>

              <div class="d-flex align-center flex-wrap ga-1 text-body-small text-medium-emphasis">
                <template v-if="row.series_num">{{ row.series_num }}</template>

                <v-chip v-if="row.duplicates" label size="x-small" variant="tonal">
                  {{ t('minifigs.duplicatesPlural', row.duplicates, { named: { count: row.duplicates } }) }}
                </v-chip>

                <v-chip v-if="row.sealed_bags" label size="x-small" variant="tonal">
                  {{ t('minifigs.bagsPlural', row.sealed_bags, { named: { count: row.sealed_bags } }) }}
                </v-chip>
              </div>
            </td>

            <td class="text-body-medium">{{ row.year ?? '—' }}</td>

            <template v-if="row.total > 0">
              <td class="text-end text-no-wrap">{{ t('dashboard.seriesOf', { owned: row.owned, total: row.total }) }}</td>

              <td class="text-end text-no-wrap">
                <v-chip
                  v-if="state(row) === 'complete'"
                  color="positive"
                  label
                  prepend-icon="mdi-check"
                  size="x-small"
                  variant="tonal"
                >{{ t('dashboard.seriesDone') }}</v-chip>

                <template v-else>{{ Math.max(row.total - row.owned, 0) }}</template>
              </td>

              <td class="minifigs-table__progress">
                <SeriesBar :owned="row.owned" :total="row.total" />
              </td>
            </template>

            <td v-else class="text-body-small text-medium-emphasis" colspan="3">{{ t('minifigs.notSynced') }}</td>
          </tr>
        </tbody>
      </v-table>
    </v-card>

    <CardGrid v-else>
      <v-card
        v-for="row in shown"
        :key="row.series_num ?? `theme-${row.theme_id}`"
        border
        class="h-100 d-flex flex-column"
        :class="{ 'series-card--untouched': state(row) === 'untouched' }"
        :disabled="!row.series_num"
        flat
        :to="row.series_num ? { name: 'minifig-series', params: { num: row.series_num } } : undefined"
      >
        <SetImage
          :alt="row.name"
          class="series-card__image"
          rounded="0"
          :size="132"
          :src="imageSrc(row.image_url) ?? undefined"
        />

        <div class="pa-3 d-flex flex-column ga-1 flex-grow-1">
          <div class="text-body-large font-weight-medium text-truncate">{{ row.name }}</div>

          <div class="text-body-small text-medium-emphasis">
            <template v-if="row.series_num">{{ row.series_num }}</template>
            <span v-if="row.year"> · {{ row.year }}</span>
          </div>

          <template v-if="row.total > 0">
            <div class="d-flex align-center mt-2">
              <span class="text-body-medium">{{ t('dashboard.seriesOf', { owned: row.owned, total: row.total }) }}</span>
              <v-spacer />

              <v-chip
                v-if="state(row) === 'complete'"
                color="positive"
                label
                prepend-icon="mdi-check"
                size="x-small"
                variant="tonal"
              >{{ t('dashboard.seriesDone') }}</v-chip>
            </div>

            <SeriesBar :owned="row.owned" :total="row.total" />

            <div class="d-flex flex-wrap ga-1 mt-1">
              <v-chip v-if="row.duplicates" label size="x-small" variant="tonal">
                {{ t('minifigs.duplicatesPlural', row.duplicates, { named: { count: row.duplicates } }) }}
              </v-chip>

              <v-chip v-if="row.sealed_bags" label size="x-small" variant="tonal">
                {{ t('minifigs.bagsPlural', row.sealed_bags, { named: { count: row.sealed_bags } }) }}
              </v-chip>
            </div>
          </template>

          <div v-else class="text-body-small text-medium-emphasis mt-2">{{ t('minifigs.notSynced') }}</div>
        </div>
      </v-card>
    </CardGrid>
  </div>
</template>

<style scoped>
.mf-control {
  flex: 1 1 180px;
  max-width: 240px;
}

.mf-control--search {
  flex-basis: 220px;
  max-width: 320px;
}

.mf-control--years {
  max-width: 320px;
}

@media (max-width: 600px) {
  .mf-control,
  .mf-control--search,
  .mf-control--years {
    max-width: none;
  }
}

/* Tabuľka Figúrok: riadky ako v Chcem a Zbierke, na telefóne sa posúva do strany. */
.minifigs-table {
  overflow-x: auto;
}

.minifigs-table__photo {
  width: 104px;
  padding-top: 6px !important;
  padding-bottom: 6px !important;
}

.minifigs-table__name {
  color: inherit;
  font-weight: 500;
  text-decoration: none;
}

a.minifigs-table__name:hover {
  text-decoration: underline;
}

.minifigs-table__progress {
  min-width: 120px;
  width: 20%;
}

/* Séria, z ktorej nič nemám, je v zozname, ale nekričí. */
.series-card--untouched .series-card__image {
  filter: grayscale(0.5);
  opacity: 0.7;
}
</style>
