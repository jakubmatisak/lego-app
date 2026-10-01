<script setup lang="ts">
  /**
   * Zbierka s panelom filtrov.
   *
   * Filter sa zapisuje do adresy stránky s rovnakými menami, aké berie API,
   * takže sa dá uložiť ako záložka a tlačidlo Späť vráti aj filter.
   *
   * Posledný stav (filtre, vlastnené/predané, zoskupenie, zoradenie) si
   * pamätá účet. Otvorenie Zbierky z ponuky ho vráti; odkaz s vlastným
   * filtrom (uložený pohľad, štítok z detailu setu) má prednosť.
   *
   * Zbierka sú len sety. Figúrky zo sérií majú sekciu Figúrky a sem nechodia
   * ani v počtoch (`sets_only` v `filterQuery`); Prehľad a export ich počítajú.
   */
  import type { ValuedItem } from '@/api/types'
  import type { SortKey } from '@/stores/collection'
  import type { LocationQueryRaw } from 'vue-router'
  import { useDebounceFn } from '@vueuse/core'
  import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useRoute, useRouter } from 'vue-router'
  import { useDisplay } from 'vuetify'
  import { api } from '@/api/client'
  import ActiveFilters from '@/components/ActiveFilters.vue'
  import BulkBar from '@/components/BulkBar.vue'
  import CardGrid from '@/components/CardGrid.vue'
  import CategoryManager from '@/components/CategoryManager.vue'
  import CollectionTable from '@/components/CollectionTable.vue'
  import ConditionChips from '@/components/ConditionChips.vue'
  import ExportCsvButton from '@/components/ExportCsvButton.vue'
  import FiguresElsewhere from '@/components/FiguresElsewhere.vue'
  import FilterPanel from '@/components/FilterPanel.vue'
  import LoadFailed from '@/components/LoadFailed.vue'
  import PageSkeleton from '@/components/PageSkeleton.vue'
  import SelectionTotals from '@/components/SelectionTotals.vue'
  import SetCard from '@/components/SetCard.vue'
  import { usePageLoad } from '@/composables/usePageLoad'
  import { createSelection } from '@/composables/useSelection'
  import { useAuthStore } from '@/stores/auth'
  import { defaultDir, groupingFrom, MENU_SORT_KEYS, SORT_KEYS, useCollectionStore } from '@/stores/collection'
  import { hasStaleKeys, useFilterStore } from '@/stores/filters'
  import { useProfileStore } from '@/stores/preferences'
  import { exactMoney, money, shortDate } from '@/utils/format'
  import { placeLabel } from '@/utils/place'
  import { figuresRoute } from '@/utils/series'

  const { t } = useI18n()
  const route = useRoute()
  const router = useRouter()
  const display = useDisplay()
  const collection = useCollectionStore()
  const filterStore = useFilterStore()
  const profile = useProfileStore()
  const auth = useAuthStore()

  const SORTS = new Set<string>(SORT_KEYS)
  const DEFAULT_SORT = 'profit'

  /** Panel vľavo od strednej šírky, na telefóne sa vysúva zdola. */
  const wide = computed(() => display.mdAndUp.value)
  const sheetOpen = ref(false)
  /** Panel filtrov na širokej obrazovke sa dá schovať; karty potom zaberú celú šírku. */
  const panelOpen = ref(true)
  const managerOpen = ref(false)

  /**
   * Výber nad kartami má len hlavné zoradenia. Kľúč z hlavičky tabuľky
   * (číslo, téma, stav…) sa doň pridá, len kým platí, nech výber ukáže,
   * podľa čoho sa radí.
   */
  const sortOptions = computed(() => {
    const keys: SortKey[] = [...MENU_SORT_KEYS]
    if (!keys.includes(collection.sort)) keys.push(collection.sort)
    return keys.map(value => ({ value, title: t(`collection.sort.${value}`) }))
  })

  /** Smer, ktorý práve platí: otočený, alebo predvolený pre kľúč. */
  const effectiveDir = computed(() => collection.sortDir ?? defaultDir(collection.sort))

  function flipDir (): void {
    const next = effectiveDir.value === 'asc' ? 'desc' : 'asc'
    // Predvolený smer sa nepamätá, nech adresa ostane krátka.
    collection.sortDir = next === defaultDir(collection.sort) ? null : next
  }
  /** Kusy, karty a počty panela; chybu načítania kusov hlási store sám. */
  async function reloadData (): Promise<boolean> {
    await Promise.all([
      collection.loadItems(),
      collection.loadGrouped(),
      filterStore.loadFacets(collection.statusFilter),
    ])
    return collection.error === null
  }

  /**
   * Prvé načítanie ukáže kostru, zmena filtra a Obnoviť stránku nechajú
   * staré karty na obrazovke (usePageLoad). Prázdny stav až po odpovedi.
   */
  const page = usePageLoad(reloadData, { notify: false })
  const reload = useDebounceFn(() => page.run(), 250)
  /** Kostra v tvare zobrazenia: tabuľka, riadky kusov alebo karty setov. */
  const skeletonKind = computed(() => {
    if (tableView.value) return 'table'
    return collection.grouping === 'item' ? 'rows' : 'cards'
  })

  /** Adresa pre súčasný filter a zobrazenie; predvolené hodnoty sa vynechajú. */
  function routeQuery (): LocationQueryRaw {
    return {
      ...filterStore.toRoute(),
      ...(collection.statusFilter === 'owned' ? {} : { status: collection.statusFilter }),
      ...(collection.grouping === 'set' ? {} : { group: collection.grouping }),
      ...(collection.sort === DEFAULT_SORT ? {} : { sort: collection.sort }),
      ...(collection.sortDir === null ? {} : { dir: collection.sortDir }),
    }
  }

  /** Filter a zobrazenie do adresy, bez nového záznamu v histórii za každý klik. */
  function syncRoute (): void {
    const query = routeQuery()
    router.replace({ query })
    saveProfile(query)
  }

  /**
   * Filter aj schovaný panel si pamätá účet. Predvolený stav sa neukladá:
   * prázdne nastavenie znamená „nič zvláštne“.
   */
  function saveProfile (query: Record<string, unknown>): void {
    profile.save('collection', {
      ...(Object.keys(query).length > 0 ? { query } : {}),
      ...(panelOpen.value ? {} : { panelHidden: true }),
      ...(tableView.value ? { view: 'table' } : {}),
    })
  }

  /** Tlačidlo Filtre: na širokej obrazovke schová/ukáže panel, na telefóne ho vysunie. */
  function toggleFilters (): void {
    if (!wide.value) {
      sheetOpen.value = true
      return
    }
    panelOpen.value = !panelOpen.value
    saveProfile({ ...route.query })
  }

  /** Všetko je tak, ako po prvom otvorení: nie je čo resetovať. */
  const isDefault = computed(() =>
    filterStore.activeCount === 0
    && collection.statusFilter === 'owned'
    && collection.grouping === 'set'
    && collection.sort === DEFAULT_SORT
    && collection.sortDir === null,
  )

  function resetAll (): void {
    filterStore.clear()
    collection.statusFilter = 'owned'
    collection.grouping = 'set'
    collection.sort = DEFAULT_SORT
    collection.sortDir = null
  }

  function readRoute (): void {
    filterStore.fromRoute(route.query)
    const status = route.query.status
    collection.statusFilter = status === 'sold' || status === 'all' ? status : 'owned'
    collection.grouping = groupingFrom(route.query.group) ?? 'set'
    const sort = route.query.sort
    collection.sort = SORTS.has(sort as string) ? sort as SortKey : DEFAULT_SORT
    const dir = route.query.dir
    collection.sortDir = dir === 'asc' || dir === 'desc' ? dir : null
  }

  /** Bez filtra v adrese (príchod z ponuky) sa vráti posledný stav účtu. */
  async function restoreSaved (): Promise<void> {
    await profile.load()
    panelOpen.value = profile.get('collection')?.panelHidden !== true
    tableView.value = profile.get('collection')?.view === 'table'
    if (Object.keys(route.query).length > 0) return
    const saved = profile.get('collection')?.query
    if (saved && typeof saved === 'object' && Object.keys(saved).length > 0) {
      await router.replace({ query: saved as Record<string, string | string[]> })
    }
  }

  watch(
    () => [
      JSON.stringify(filterStore.filters),
      collection.statusFilter,
      collection.sort,
      collection.sortDir,
      collection.grouping,
    ],
    () => {
      syncRoute()
      reload()
    },
  )

  // Iný filter alebo zoskupenie = iný výsledok; výber by ukazoval na niečo iné.
  watch(
    () => [JSON.stringify(filterStore.filters), collection.statusFilter, collection.grouping],
    () => {
      // Predané sa hromadne nemenia: výber sa tam vypne celý, aj s lištou.
      if (collection.statusFilter === 'sold') selection.stop()
      else selection.clear()
    },
  )

  function onView (group: string | null): void {
    const grouping = groupingFrom(group)
    if (grouping) collection.grouping = grouping
  }

  const showSold = computed(() => collection.statusFilter === 'sold')
  /** Karty alebo tabuľka; pamätá sa pri účte, nie v adrese. */
  const tableView = ref(false)
  function setView (table: boolean): void {
    tableView.value = table
    saveProfile({ ...route.query })
  }
  /** Výber na hromadnú úpravu; zmena filtra ho vyčistí. */
  const selection = createSelection({
    items: () => (collection.grouping === 'item' ? collection.items.map(i => i.id) : []),
    groups: () => (collection.grouping === 'item' ? [] : collection.grouped.map(r => r.catalog.catalog_num)),
  })

  /** Koľko kariet filter ukáže, pre tlačidlo pod panelom na telefóne. */
  const resultCount = computed(() => filterStore.facets?.total ?? 0)

  /** Počty sekcie Zbierka, bez figúrok zo sérií (tie počíta Prehľad a Figúrky). */
  const summaryLine = computed(() => {
    const s = collection.summary
    if (!s) return ''
    return t('collection.summaryLine', {
      sets: t('collection.setsPlural', s.collection_set_count, { named: { count: s.collection_set_count } }),
      items: t('collection.piecesPlural', s.collection_item_count, { named: { count: s.collection_item_count } }),
      sold: s.collection_sold_count,
    })
  })

  const isEmpty = computed(() =>
    collection.grouping === 'item' ? collection.items.length === 0 : collection.grouped.length === 0,
  )

  /** Figúrky zo sérií, ktoré by filter či hľadanie našlo, ale sú vo Figúrkach. */
  const hiddenFigures = computed(() => filterStore.facets?.hidden_figures ?? 0)

  /**
   * Riadok o figúrkach nad výsledkom len pri hľadaní, ktoré ich trafilo:
   * inak by sa zdalo, že appka hľadanú figúrku nepozná. Rovnako pri filtri
   * umiestnenia či krabice: na otázku „čo je v krabici 3“ patria aj figúrky,
   * ktoré tam ležia. Iný bežný filter (stav, téma…), ktorý niečo ukazuje,
   * nehlási nič; prázdny výsledok to povie v prázdnom stave. Počty musia
   * patriť tomuto hľadaniu a miestu, nie filtru spred zmeny, inak by chvíľu
   * svietil cudzí počet.
   *
   * `pending`: hľadanie sa spresňuje („shrek“ → „shrek 2“) alebo sa mení
   * miesto a predošlé tiež trafilo figúrky. Riadok drží miesto bez starého
   * počtu, kým neprídu nové počty; inak by pri každej pauze v písaní zmizol
   * a vrátil sa a výsledky pod ním by poskočili. Bez hľadania a miesta nie
   * je čo držať.
   */
  const figuresLine = computed<'shown' | 'pending' | null>(() => {
    const search = filterStore.facetsSearch
    const places = filterStore.facetsPlaces
    if (isEmpty.value || hiddenFigures.value <= 0 || (search === '' && places === '')) return null
    const typed = filterStore.filters.q.trim()
    const chosen = filterStore.placeKey()
    if (search === typed && places === chosen) return 'shown'
    return typed === '' && chosen === '' ? null : 'pending'
  })

  /** Hodnota kusu. Bez známej ceny pomlčka, nie nula. */
  function pieceValue (item: ValuedItem): string {
    if (item.status === 'sold') return exactMoney(item.sold_price_eur)
    if (item.price_source === 'missing') return '—'
    const prefix = item.price_source === 'market_approx' ? '≈ ' : ''
    return prefix + exactMoney(item.market_value)
  }

  function pieceProfit (item: ValuedItem): string {
    if (item.status === 'sold') return money(item.realized, { sign: true })
    return item.price_source === 'missing' ? '' : money(item.unrealized, { sign: true })
  }

  function pieceProfitClass (item: ValuedItem): string {
    if (item.status !== 'sold' && item.price_source === 'missing') return 'text-medium-emphasis'
    const value = Number(item.status === 'sold' ? item.realized : item.unrealized)
    return value >= 0 ? 'text-positive' : 'text-negative'
  }

  async function onCategoriesChanged (): Promise<void> {
    await page.run()
  }

  /**
   * Popis, štítky a hodnotenie z Brickset pre staršie sety, na pozadí.
   * Keď dobehne, načítajú sa počty, aby sa ukázal filter podľa štítkov.
   */
  let backfillTimer: ReturnType<typeof setTimeout> | null = null
  async function backfillBrickset (wasRunning = false): Promise<void> {
    if (!auth.can('brickset.backfill')) return
    const { data } = await api.POST('/catalog/brickset/backfill', {})
    if (data?.running) {
      backfillTimer = setTimeout(() => backfillBrickset(true), 4000)
    } else if (wasRunning) {
      filterStore.loadFacets(collection.statusFilter)
    }
  }
  onBeforeUnmount(() => {
    if (backfillTimer) clearTimeout(backfillTimer)
  })

  onMounted(async () => {
    // Starý odkaz (záložka, história) s filtrom figúrok zo sérií, napríklad
    // „chýbajúce figúrky série“, vedie tam, kde figúrky teraz sú. Len adresa;
    // uložený stav účtu sa pri príchode z ponuky len vyčistí.
    const elsewhere = figuresRoute(route.query)
    if (elsewhere) {
      await router.replace(elsewhere)
      return
    }
    backfillBrickset()
    await restoreSaved()
    readRoute()
    // Starý filter figúrok či zoskupenie podľa série sa zahodilo; adresa
    // a uložený stav účtu to majú zabudnúť tiež.
    if (hasStaleKeys(route.query, routeQuery())) syncRoute()
    await Promise.all([filterStore.loadCategories(), filterStore.loadViews()])
    await page.run()
    collection.loadLocations()
    if (!collection.summary) collection.loadDashboard()
  })
</script>

<template>
  <div
    class="collection-layout"
    :class="{ 'collection-layout--wide': wide, 'collection-layout--no-panel': wide && !panelOpen }"
  >
    <!-- Panel filtrov vpravo, na širokej obrazovke na očiach, kým ho nikto neschová. -->
    <aside v-if="wide && panelOpen" class="collection-aside">
      <v-card border class="collection-aside__card" flat>
        <div class="d-flex align-center px-3 pt-3 pb-1">
          <span class="text-body-large font-weight-medium">{{ t('filters.title') }}</span>
          <v-spacer />

          <v-btn
            v-if="filterStore.activeCount > 0"
            size="small"
            variant="text"
            @click="filterStore.clear()"
          >{{ t('filters.clear') }}</v-btn>

          <v-btn
            density="comfortable"
            icon="mdi-chevron-double-right"
            size="small"
            :title="t('filters.hidePanel')"
            variant="text"
            @click="toggleFilters"
          />
        </div>

        <FilterPanel @manage="managerOpen = true" />
      </v-card>
    </aside>

    <div class="d-flex flex-column ga-4 collection-main">
      <div class="d-flex align-center flex-wrap ga-2">
        <span class="text-body-medium text-medium-emphasis">{{ summaryLine }}</span>
        <v-spacer />

        <!-- Filter si účet pamätá, takže návrat k celej zbierke musí byť po ruke. -->
        <v-btn
          v-if="!isDefault"
          color="primary"
          prepend-icon="mdi-filter-remove-outline"
          size="small"
          variant="tonal"
          @click="resetAll"
        >{{ t('filters.resetAll') }}</v-btn>

        <ExportCsvButton size="small" variant="outlined" />

        <v-btn
          color="primary"
          prepend-icon="mdi-plus"
          size="small"
          :to="{ name: 'add-set' }"
          variant="flat"
        >{{ t('collection.addSet') }}</v-btn>
      </div>

      <!-- Hľadanie vľavo cez celú šírku, zoradenie a Filtre vpravo pri paneli. -->
      <div class="d-flex ga-3 flex-wrap align-center">
        <v-text-field
          v-model="filterStore.filters.q"
          class="search-field"
          clearable
          density="comfortable"
          hide-details
          :label="t('collection.search')"
          prepend-inner-icon="mdi-magnify"
          @click:clear="filterStore.filters.q = ''"
        />

        <v-select
          v-model="collection.sort"
          class="sort-field"
          density="comfortable"
          hide-details
          item-title="title"
          item-value="value"
          :items="sortOptions"
          :label="t('collection.sortBy')"
        />

        <v-btn
          class="sort-dir"
          :icon="effectiveDir === 'asc' ? 'mdi-sort-ascending' : 'mdi-sort-descending'"
          :title="effectiveDir === 'asc' ? t('collection.sortAsc') : t('collection.sortDesc')"
          variant="text"
          @click="flipDir"
        />

        <!-- 48 px ako polia vedľa neho (hustota comfortable). -->
        <v-btn
          :active="wide && panelOpen"
          height="48"
          prepend-icon="mdi-tune-variant"
          :title="wide ? (panelOpen ? t('filters.hidePanel') : t('filters.showPanel')) : undefined"
          variant="outlined"
          @click="toggleFilters"
        >
          {{ t('filters.button') }}
          <v-badge
            v-if="filterStore.activeCount > 0"
            class="ms-2"
            color="primary"
            :content="filterStore.activeCount"
            inline
          />
        </v-btn>
      </div>

      <div class="d-flex ga-2 flex-wrap align-center">
        <v-btn-toggle
          v-model="collection.statusFilter"
          density="comfortable"
          mandatory
          variant="outlined"
        >
          <v-btn v-for="status in (['owned', 'sold', 'all'] as const)" :key="status" :value="status">
            {{ t(`collection.status.${status}`) }}
          </v-btn>
        </v-btn-toggle>

        <v-spacer />

        <v-btn-toggle
          density="comfortable"
          mandatory
          :model-value="tableView ? 'table' : 'cards'"
          variant="outlined"
          @update:model-value="value => setView(value === 'table')"
        >
          <!-- Pri jednotlivých kusoch sú „karty“ zoznam pod sebou, ikona to musí povedať. -->
          <v-btn
            :icon="collection.grouping === 'item' ? 'mdi-view-agenda-outline' : 'mdi-view-module-outline'"
            :title="t(collection.grouping === 'item' ? 'collection.viewList' : 'collection.viewCards')"
            value="cards"
          />

          <v-btn icon="mdi-view-headline" :title="t('collection.viewTable')" value="table" />
        </v-btn-toggle>

        <v-btn-toggle
          v-model="collection.grouping"
          density="comfortable"
          mandatory
          variant="outlined"
        >
          <v-btn value="set">
            {{ t('collection.groupBy.set') }}
            <v-tooltip activator="parent" location="bottom" :text="t('collection.groupBy.setHint')" />
          </v-btn>

          <v-btn value="item">
            {{ t('collection.groupBy.item') }}
            <v-tooltip activator="parent" location="bottom" :text="t('collection.groupBy.itemHint')" />
          </v-btn>
        </v-btn-toggle>
      </div>

      <ActiveFilters :group="collection.grouping" @view="onView" />

      <!-- Súčty toho, čo filter ukazuje, aj s reálnym ziskom po inflácii. -->
      <SelectionTotals :totals="filterStore.facets?.totals" />

      <!-- Hľadanie trafilo aj figúrky zo sérií, tie sú vo Figúrkach. -->
      <FiguresElsewhere v-if="figuresLine" :count="hiddenFigures" :pending="figuresLine === 'pending'" />

      <!-- Hromadná úprava: len vlastnené kusy. -->
      <div v-if="collection.statusFilter !== 'sold'" class="d-flex">
        <v-btn
          v-if="!selection.active.value"
          prepend-icon="mdi-checkbox-multiple-outline"
          size="small"
          variant="text"
          @click="selection.active.value = true"
        >{{ t('bulk.select') }}</v-btn>
      </div>

      <!-- Na širokej obrazovke sa posúva len táto časť, filtre a ovládanie stoja. -->
      <div class="collection-results" :class="{ 'collection-results--table': tableView && wide }">
        <!-- Kým server neodpovedal, kostra; prázdny stav až po odpovedi. -->
        <PageSkeleton v-if="page.initial" :kind="skeletonKind" />

        <LoadFailed v-else-if="page.error" :loading="page.loading" @retry="page.run()" />

        <v-empty-state
          v-else-if="isEmpty"
          icon="mdi-magnify"
          :text="t('collection.emptyHint')"
          :title="t('collection.empty')"
        >
          <!-- Nič medzi setmi, ale filter by trafil figúrky zo sérií. -->
          <template v-if="hiddenFigures > 0" #default>
            <FiguresElsewhere class="justify-center" :count="hiddenFigures" />
          </template>
        </v-empty-state>

        <CollectionTable v-else-if="tableView" :fill="wide" :selection="selection" :sold="showSold" />

        <CardGrid v-else-if="collection.grouping !== 'item'">
          <SetCard
            v-for="row in collection.grouped"
            :key="row.catalog.catalog_num"
            :row="row"
            :selectable="selection.active.value"
            :selected="selection.active.value && selection.hasGroup(row.catalog.catalog_num)"
            :sold="showSold"
            @toggle="num => selection.toggleGroup(num)"
          />
        </CardGrid>

        <v-card v-else border flat>
          <v-list lines="two">
            <v-list-item
              v-for="item in collection.items"
              :key="item.id"
              :active="selection.active.value && selection.hasItem(item.id)"
              :to="selection.active.value ? undefined : { name: 'set-detail', params: { num: item.catalog_num } }"
              @click="selection.active.value && selection.toggleItem(item.id)"
            >
              <template v-if="selection.active.value" #prepend>
                <v-icon
                  class="me-2"
                  :color="selection.hasItem(item.id) ? 'primary' : undefined"
                  :icon="selection.hasItem(item.id) ? 'mdi-checkbox-marked' : 'mdi-checkbox-blank-outline'"
                />
              </template>

              <v-list-item-title class="font-weight-medium">{{ item.catalog.name }}</v-list-item-title>

              <v-list-item-subtitle>
                <ConditionChips
                  :condition="item.condition"
                  :flags="item.flags"
                  :location="placeLabel(item.location, item.box)"
                  size="x-small"
                />
              </v-list-item-subtitle>

              <template #append>
                <div class="text-end">
                  <div class="text-body-medium font-weight-medium">
                    {{ pieceValue(item) }}
                  </div>

                  <div class="text-body-small" :class="pieceProfitClass(item)">
                    {{ pieceProfit(item) }}
                  </div>

                  <div v-if="item.status !== 'sold' && item.price_at" class="text-body-small text-medium-emphasis">
                    {{ t('collection.priceAt', { date: shortDate(item.price_at) }) }}
                  </div>
                </div>
              </template>
            </v-list-item>
          </v-list>
        </v-card>

        <BulkBar
          v-if="selection.active.value"
          :selection="selection"
          :total="collection.grouping === 'item' ? collection.items.length : collection.grouped.length"
          :unit="collection.grouping === 'item' ? 'pieces' : 'sets'"
          @done="page.run()"
        />
      </div>
    </div>

    <!-- Na telefóne sa panel vysunie zdola. -->
    <v-bottom-sheet v-if="!wide" v-model="sheetOpen" scrollable>
      <v-card>
        <v-card-title class="d-flex align-center">
          {{ t('filters.title') }}
          <v-spacer />

          <v-btn
            v-if="filterStore.activeCount > 0"
            size="small"
            variant="text"
            @click="filterStore.clear()"
          >{{ t('filters.clear') }}</v-btn>
        </v-card-title>

        <v-card-text class="pa-0" style="max-height: 70vh">
          <FilterPanel @manage="managerOpen = true" />
        </v-card-text>

        <v-card-actions>
          <v-btn block color="primary" variant="flat" @click="sheetOpen = false">
            {{ t('filters.done') }} · {{ t('collection.piecesPlural', resultCount, { named: { count: resultCount } }) }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-bottom-sheet>

    <CategoryManager v-model="managerOpen" @changed="onCategoriesChanged" />

  </div>
</template>

<style scoped>
/*
 * Široká obrazovka: celá stránka presne na výšku okna (bez lišty 64 px
 * a okrajov 2 × 16 px). Panel filtrov aj výsledky sa posúvajú každý sám,
 * stránka ako celok nikdy.
 */
.collection-layout--wide {
  display: grid;
  gap: 16px;
  /* Karty vľavo, panel filtrov vpravo. */
  grid-template-columns: minmax(0, 1fr) 330px;
  grid-template-rows: minmax(0, 1fr);
  height: calc(100dvh - 64px - 32px);
}

.collection-layout--wide .collection-aside {
  grid-column: 2;
  grid-row: 1;
}

.search-field {
  flex: 1 1 220px;
  min-width: 220px;
}

.sort-field {
  flex: 0 0 180px;
}

/* Schovaný panel: karty na celú šírku, výška okna ostáva. */
.collection-layout--no-panel {
  grid-template-columns: minmax(0, 1fr);
}

.collection-layout--wide .collection-aside {
  min-height: 0;
}

.collection-layout--wide .collection-aside__card {
  max-height: 100%;
  overflow-y: auto;
}

.collection-main {
  min-width: 0;
}

.collection-layout--wide .collection-main {
  min-height: 0;
}

/*
 * Do výšky rastú len výsledky, riadky nad nimi majú svoju výšku. Vuetify
 * dáva niektorým komponentom `flex: 1 1` (v-alert, v-banner) a v stĺpci
 * s výškou okna by si s výsledkami rozdelili voľné miesto napoly: upozornenie
 * o figúrkach tak kedysi zabralo pol obrazovky.
 */
.collection-layout--wide .collection-main > :not(.collection-results) {
  flex: 0 0 auto;
}

.collection-layout--wide .collection-results {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding-bottom: 16px;
}

/*
 * Tabuľka sa posúva sama, výsledky okolo nej nie: inak by boli dva
 * posuvníky nad sebou. Tabuľka vyplní zvyšok výšky, lišta výberu pod ňou.
 */
.collection-results--table {
  display: flex;
  flex-direction: column;
  overflow-y: hidden !important;
  padding-bottom: 0 !important;
}

</style>
