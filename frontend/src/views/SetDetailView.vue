<script setup lang="ts">
  /**
   * Detail setu. Predaný kus zostáva v tabuľke aj po predaji, aby sa
   * nestratila jeho história a realizovaný zisk.
   *
   * Pri sérii (holé číslo) sú tu všetky jej kusy: figúrky, sáčky aj predané.
   * Zbierka figúrky zo sérií nemá, preto sa tu dajú aj hromadne upraviť
   * (krabica, zoznam, príznaky…) cez tú istú lištu s rozsahom `series`.
   */
  import type { CatalogDetail, PriceOverview, ValuedItem } from '@/api/types'
  import { computed, onMounted, ref, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useRoute } from 'vue-router'
  import { api, errorMessage } from '@/api/client'
  import BulkBar from '@/components/BulkBar.vue'
  import CategoryManager from '@/components/CategoryManager.vue'
  import CategoryMembership from '@/components/CategoryMembership.vue'
  import ConditionChips from '@/components/ConditionChips.vue'
  import KeyHint from '@/components/KeyHint.vue'
  import ListingDialog from '@/components/ListingDialog.vue'
  import PhotosDialog from '@/components/PhotosDialog.vue'
  import PieceDialog from '@/components/PieceDialog.vue'
  import PriceHistoryChart from '@/components/PriceHistoryChart.vue'
  import PurchaseDialog from '@/components/PurchaseDialog.vue'
  import SellDialog from '@/components/SellDialog.vue'
  import SetGallery from '@/components/SetGallery.vue'
  import SetImage from '@/components/SetImage.vue'
  import { createSelection } from '@/composables/useSelection'
  import { useAuthStore } from '@/stores/auth'
  import { useCollectionStore } from '@/stores/collection'
  import { useNotifyStore } from '@/stores/notify'
  import { usePriceStore } from '@/stores/prices'
  import { count, dateTime, exactMoney, money, percent, shortDate, toNumber } from '@/utils/format'
  import { imageSrc } from '@/utils/imageSrc'
  import { placeLabel } from '@/utils/place'
  import { isSeriesPage as isSeriesDetail } from '@/utils/series'

  const route = useRoute()
  const { t, locale } = useI18n()
  const notify = useNotifyStore()
  const collection = useCollectionStore()
  const auth = useAuthStore()
  const priceStore = usePriceStore()

  const num = computed(() => String(route.params.num))
  const catalog = ref<CatalogDetail | null>(null)
  /**
   * Nový aj rozbalený stav prídu zo zdroja jedným volaním a ukladajú sa oba,
   * preto ich karta ukazuje vedľa seba. Prepínač len vyberá, ku ktorému
   * stavu sa ukáže história a rozpätie.
   */
  const pricesN = ref<PriceOverview | null>(null)
  const pricesU = ref<PriceOverview | null>(null)
  const prices = computed(() => (priceCondition.value === 'N' ? pricesN.value : pricesU.value))
  const hasAnyPrice = computed(() => Boolean(pricesN.value?.current || pricesU.value?.current))
  const hasForecast = computed(() => {
    const c = catalog.value
    return Boolean(c?.forecast_2y_eur || c?.forecast_5y_eur || c?.growth_12m_pct != null)
  })
  /** Najčerstvejšia snímka z oboch stavov, pre riadok „aktualizované“. */
  const lastCaptured = computed(() => {
    const times = [pricesN.value?.current?.captured_at, pricesU.value?.current?.captured_at]
      .filter(Boolean)
    return times.toSorted().at(-1) ?? null
  })
  const providerEnabled = computed(() =>
    Boolean(pricesN.value?.provider_enabled || pricesU.value?.provider_enabled),
  )
  const loading = ref(true)
  const error = ref<string | null>(null)

  const priceCondition = ref<'N' | 'U'>('N')
  const sellTarget = ref<ValuedItem | null>(null)
  const sellOpen = ref(false)
  const editTarget = ref<ValuedItem | null>(null)
  const editOpen = ref(false)
  const photosTarget = ref<ValuedItem | null>(null)
  const photosOpen = ref(false)
  const listingTarget = ref<ValuedItem | null>(null)
  const listingOpen = ref(false)
  /** Počet fotiek na kus, nech ikona fotoaparátu ukáže, či už nejaké sú. */
  const photoCounts = ref<Record<number, number>>({})
  const managerOpen = ref(false)
  const membership = ref<InstanceType<typeof CategoryMembership> | null>(null)

  function openPhotos (item: ValuedItem): void {
    photosTarget.value = item
    photosOpen.value = true
  }

  function openListing (item: ValuedItem): void {
    listingTarget.value = item
    listingOpen.value = true
  }

  /** Po kúpe ďalšieho kusu sa obnoví zoznam aj súčty, cena sa nemení. */
  async function onPieceBought (): Promise<void> {
    await loadPieces()
  }

  function onPhotosChanged (itemId: number, count: number): void {
    photoCounts.value = { ...photoCounts.value, [itemId]: count }
  }

  /** Návod na lego.com. Adresa bez jazyka presmeruje na jazyk návštevníka. */
  const instructionsUrl = computed(() => {
    const c = catalog.value
    if (!c || c.kind !== 'set' || !/^\d/.test(c.catalog_num)) return null
    return `https://www.lego.com/service/buildinginstructions/${c.catalog_num.replace(/-\d+$/, '')}`
  })

  /**
   * Stránka setu na Brickset. Odtiaľ appka berie časť údajov a čiarové kódy,
   * tak sa na zdroj aj odkazuje. Séria (holé číslo) na Brickset stránku nemá.
   */
  const bricksetUrl = computed(() => {
    const c = catalog.value
    if (!c || !/^\d+-\d+$/.test(c.catalog_num)) return null
    return `https://brickset.com/sets/${c.catalog_num}`
  })

  /**
   * Rast od stiahnutia z predaja. Počíta sa len vtedy, keď história cien
   * siaha až k dátumu stiahnutia; zdroj posiela zhruba posledný rok, pri
   * dávno stiahnutých setoch sa teda neukáže. Dopočítavať by sa nemalo z čoho.
   */
  const sinceRetired = computed(() => {
    const retired = catalog.value?.retired_date
    const history = pricesN.value?.history ?? []
    const now = toNumber(pricesN.value?.current?.avg_price)
    if (!retired || history.length === 0 || now === null) return null
    const before = history.filter(p => p.captured_at.slice(0, 10) <= retired && p.avg_price)
    const then = toNumber(before.at(-1)?.avg_price)
    if (then === null || then <= 0) return null
    return ((now - then) / then) * 100
  })
  const locations = ref<string[]>([])

  function openEdit (item: ValuedItem): void {
    editTarget.value = item
    editOpen.value = true
  }

  /** `id` posiela dialóg: kus, pre ktorý sa ukladanie začalo, nie ten, čo je v ňom teraz. */
  async function savePiece (id: number, payload: Record<string, unknown>): Promise<void> {
    const { error: err } = await api.PATCH('/items/{item_id}', {
      params: { path: { item_id: id } },
      body: payload as never,
    })
    // Chyba ide do oznámenia; stránková chyba je len pre nenačítaný set.
    if (err) {
      notify.error(err, t('piece.saveFailed'))
    } else {
      notify.success(t('notice.pieceSaved'))
    }
    // Dialóg iného kusu, otvorený medzitým, ostane otvorený.
    if (editTarget.value?.id === id) editOpen.value = false
    await loadPieces()
    collection.refreshAll()
  }

  async function removePiece (id: number): Promise<void> {
    const { error: err } = await api.DELETE('/items/{item_id}', {
      params: { path: { item_id: id } },
    })
    if (err) {
      notify.error(err, t('piece.removeFailed'))
    } else {
      notify.success(t('notice.pieceDeleted'))
    }
    editOpen.value = false
    await loadPieces()
    collection.refreshAll()
  }
  const manualOpen = ref(false)
  const manualPrice = ref('')

  /**
   * Kusy si detail načítava sám so stavom „všetko“. Zoznam v Zbierke je
   * filtrovaný a po predaji by predaný kus z detailu zmizol aj s históriou.
   */
  const pieces = ref<ValuedItem[]>([])

  /** Nové v krabici je iné než postavené, nech to je vidieť na prvý pohľad. */
  function conditionColor (condition: string): string {
    return condition === 'new_sealed' ? 'primary' : 'surface-variant'
  }

  function conditionIcon (condition: string): string {
    switch (condition) {
      case 'new_sealed': { return 'mdi-package-variant-closed' }
      case 'opened_unbuilt': { return 'mdi-package-variant' }
      case 'built': { return 'mdi-castle' }
      default: { return 'mdi-dots-grid' }
    }
  }

  async function loadPieces (): Promise<void> {
    const { data } = await api.GET('/items', {
      params: { query: { status: 'all', sort: 'recent', ...collection.realQuery() } },
    })
    /*
     * Pri sérii sem patria aj kusy jej členov. Séria samotná žiadne kusy
     * nemá, takže bez toho by obrazovka série bola prázdna.
     */
    pieces.value = (data ?? []).filter(
      item => item.catalog_num === num.value || item.catalog.parent_num === num.value,
    )

    const photos = await api.GET('/photos', {})
    const counts: Record<number, number> = {}
    for (const photo of photos.data ?? []) counts[photo.item_id] = (counts[photo.item_id] ?? 0) + 1
    photoCounts.value = counts

    const known = await api.GET('/locations', {})
    locations.value = known.data ?? []
  }
  const owned = computed(() => pieces.value.filter(p => p.status === 'owned'))
  const sold = computed(() => pieces.value.filter(p => p.status === 'sold'))

  /** Aspoň jeden vlastnený kus nemá trhovú cenu. */
  const priceUnknown = computed(() =>
    owned.value.some(p => p.price_source === 'missing'),
  )

  const totals = computed(() => {
    const purchase = owned.value.reduce((s, p) => s + (toNumber(paid(p)) ?? 0), 0)
    const market = owned.value.reduce((s, p) => s + (toNumber(p.market_value) ?? 0), 0)
    const soldPurchase = sold.value.reduce((s, p) => s + (toNumber(paid(p)) ?? 0), 0)
    const soldProceeds = sold.value.reduce((s, p) => s + (toNumber(p.sold_price_eur) ?? 0), 0)
    return {
      purchase,
      market,
      unrealized: market - purchase,
      soldPurchase,
      soldProceeds,
      // Čistý zisk zo servera: po poplatkoch a poštovnom, pri prepínači v dnešných peniazoch.
      realized: sold.value.reduce((s, p) => s + (toNumber(p.realized) ?? 0), 0),
    }
  })

  /** Kúpna cena, pri prepínači „V dnešných peniazoch“ prepočítaná. */
  function paid (item: ValuedItem): string | null | undefined {
    return item.purchase_real_eur ?? item.purchase_price_eur
  }

  /** Hodnota kusu, alebo pomlčka, keď cenu nepoznáme. */
  function pieceValue (item: ValuedItem): string {
    if (item.status === 'sold') return exactMoney(item.sold_price_eur)
    if (item.price_source === 'missing') return '—'
    const prefix = item.price_source === 'market_approx' ? '≈ ' : ''
    return prefix + exactMoney(item.market_value)
  }

  function pieceProfit (item: ValuedItem): string {
    if (item.status === 'sold') return money(item.realized, { sign: true })
    return item.price_source === 'missing' ? '—' : money(item.unrealized, { sign: true })
  }

  function pieceProfitClass (item: ValuedItem): string {
    if (item.status !== 'sold' && item.price_source === 'missing') return 'text-medium-emphasis'
    const value = Number(item.status === 'sold' ? item.realized : item.unrealized)
    return value >= 0 ? 'text-positive' : 'text-negative'
  }

  const aboveRrp = computed(() => {
    const rrp = toNumber(catalog.value?.rrp_eur)
    const current = toNumber(prices.value?.current?.avg_price)
    if (!rrp || !current || rrp <= 0) return null
    return ((current - rrp) / rrp) * 100
  })

  const descriptionOpen = ref(false)
  /**
   * Galéria z Brickset sa pýta až po doplnení z Brickset: set bez čísla
   * Brickset by inak spustil druhé getSets súčasne s tým prvým.
   */
  const galleryReady = ref(false)
  const showGallery = computed(() =>
    galleryReady.value && auth.can('brickset.images') && /^\d+-\d+$/.test(catalog.value?.catalog_num ?? ''),
  )

  /**
   * Popis, štítky a hodnotenie z Brickset, ak ich set ešte nemá. Jedno
   * volanie a len raz; na stránku sa pri tom nečaká.
   */
  async function fillFromBrickset (): Promise<void> {
    const c = catalog.value
    if (!c || c.brickset_checked || !auth.can('brickset.on_detail') || !/^\d+-\d+$/.test(c.catalog_num)) return
    const { data } = await api.POST('/catalog/{num}/brickset', { params: { path: { num: c.catalog_num } } })
    if (data && catalog.value?.catalog_num === data.catalog_num) {
      catalog.value = { ...catalog.value, ...data }
    }
  }

  const ratingText = computed(() => {
    const rating = catalog.value?.bs_rating
    return rating ? rating.toLocaleString(locale.value === 'sk' ? 'sk-SK' : 'en-GB', { maximumFractionDigits: 1 }) : ''
  })

  async function load (): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const catalogRes = await api.GET('/catalog/{num}', { params: { path: { num: num.value } } })
      if (catalogRes.error || !catalogRes.data) {
        error.value = errorMessage(catalogRes.error, 'Set sa nenašiel')
        return
      }
      catalog.value = catalogRes.data
      await Promise.all([loadPrices(), loadPieces()])
      galleryReady.value = false
      fillFromBrickset().finally(() => {
        galleryReady.value = true
      })
    } finally {
      loading.value = false
    }
  }

  /** Obidva stavy z vlastného servera. Na zdroj cien sa tu nesiaha. */
  async function loadPrices (): Promise<void> {
    const [n, u] = await Promise.all(
      (['N', 'U'] as const).map(condition =>
        api.GET('/prices/{num}', {
          params: { path: { num: num.value }, query: { condition } },
        }),
      ),
    )
    pricesN.value = n.data ?? null
    pricesU.value = u.data ?? null
    // Keď vybraný stav cenu nemá a ten druhý áno, ukáž radšej ten druhý.
    if (!prices.value?.current) {
      if (pricesN.value?.current) priceCondition.value = 'N'
      else if (pricesU.value?.current) priceCondition.value = 'U'
    }
  }

  async function unsell (id: number): Promise<void> {
    await collection.unsellItem(id)
    await loadPieces()
  }

  /** Stránka série: kusy sú jej členovia, séria sama cenu nemá. Aj nezačatá. */
  const isSeriesPage = computed(() => isSeriesDetail(catalog.value, pieces.value))

  /** Hromadná úprava vlastnených kusov série; rozsah pre server je séria. */
  const selection = createSelection({ items: () => owned.value.map(p => p.id) })
  const seriesScope = computed(() => ({ series: [num.value] }))

  async function onBulkDone (): Promise<void> {
    await loadPieces()
    collection.refreshAll()
  }
  const refreshing = ref(false)
  const buyOpen = ref(false)
  const refreshNote = ref<string | null>(null)

  /** Priemerná kúpna cena vlastnených kusov tohto setu, pre čiaru v grafe. */
  const averagePurchase = computed(() => {
    const paid = pieces.value
      .filter(p => p.status === 'owned' && p.catalog_num === num.value)
      .map(p => toNumber(p.purchase_price_eur))
      .filter((v): v is number => v !== null)
    return paid.length === 0 ? null : paid.reduce((a, b) => a + b, 0) / paid.length
  })

  /**
   * Obnoví len tento set, pri sérii figúrky, ktoré z nej máš. Ide cez tie
   * isté poistky ako obnova všetkého: čerstvá cena sa znova neťahá.
   */
  async function refreshPrice (): Promise<void> {
    refreshing.value = true
    refreshNote.value = null
    await priceStore.refreshOne(num.value, async () => {
      await Promise.all([loadPrices(), loadPieces(), collection.refreshAll(), auth.loadKeys()])
      const s = priceStore.status
      if (!s) {
        refreshNote.value = null
      } else if (isSeriesPage.value) {
        refreshNote.value = t('detail.refreshNoteSeries', { updated: s.updated, left: s.calls_left })
      } else {
        refreshNote.value = s.updated > 0
          ? t('detail.refreshNoteOne', { left: s.calls_left })
          : t('detail.refreshNoteNone', { left: s.calls_left })
      }
      refreshing.value = false
    })
  }

  async function saveManualPrice (): Promise<void> {
    const value = toNumber(manualPrice.value)
    if (value === null || value <= 0) return
    const { data, error: err } = await api.PUT('/prices/{num}/manual', {
      params: { path: { num: num.value } },
      body: { price_eur: String(value), condition: priceCondition.value },
    })
    if (err) {
      notify.error(err, t('notice.saveFailed'))
      return
    }
    notify.success(t('notice.manualPriceSaved'))
    if (priceCondition.value === 'N') pricesN.value = data ?? null
    else pricesU.value = data ?? null
    manualOpen.value = false
    manualPrice.value = ''
    await collection.refreshAll()
    await loadPieces()
  }

  function openSell (item: ValuedItem): void {
    sellTarget.value = item
    sellOpen.value = true
  }

  async function confirmSell (payload: {
    sold_price_eur: string
    sold_date: string
    sold_via: string | null
    sold_fees_eur: string | null
    sold_shipping_eur: string | null
  }): Promise<void> {
    if (!sellTarget.value) return
    const ok = await collection.sellItem(sellTarget.value.id, payload)
    if (ok) {
      sellOpen.value = false
      sellTarget.value = null
      await loadPieces()
    }
  }

  watch(num, () => {
    selection.stop()
    load()
  })
  watch(() => collection.real, loadPieces)
  onMounted(load)
</script>

<template>
  <div v-if="loading" class="d-flex justify-center pa-12">
    <v-progress-circular color="primary" indeterminate />
  </div>

  <v-alert v-else-if="error" type="error" variant="tonal">{{ error }}</v-alert>

  <div v-else-if="catalog" class="d-flex flex-column ga-4">
    <v-btn
      class="align-self-start"
      prepend-icon="mdi-arrow-left"
      variant="text"
      @click="$router.back()"
    >{{ t('common.back') }}</v-btn>

    <v-card border class="pa-4" flat>
      <div class="d-flex ga-4 flex-wrap">
        <SetImage
          :alt="catalog.name"
          rounded="md"
          :size="156"
          :src="imageSrc(catalog.image_url) ?? undefined"
          style="width: 156px"
        />

        <div class="flex-grow-1" style="min-width: 280px">
          <div class="d-flex align-center ga-2 flex-wrap mb-2">
            <div class="text-headline-small">{{ catalog.name }}</div>
            <span class="text-body-medium text-medium-emphasis">{{ catalog.catalog_num }}</span>
            <v-chip v-if="catalog.theme" label size="small" variant="tonal">{{ catalog.theme }}</v-chip>
            <v-chip v-if="catalog.subtheme" label size="small" variant="tonal">{{ catalog.subtheme }}</v-chip>
            <v-chip v-if="catalog.year" label size="small" variant="tonal">{{ catalog.year }}</v-chip>

            <v-chip
              v-if="catalog.is_retired"
              color="secondary"
              label
              prepend-icon="mdi-clock-outline"
              size="small"
              variant="flat"
            >{{ catalog.retired_date
              ? t('detail.retiredOn', { date: shortDate(catalog.retired_date) })
              : catalog.retired_at ? t('detail.retired', { year: catalog.retired_at }) : t('detail.retiredShort') }}</v-chip>

            <v-chip
              v-if="sinceRetired !== null"
              :color="sinceRetired >= 0 ? 'positive' : 'negative'"
              label
              size="small"
              variant="tonal"
            >{{ t('detail.sinceRetired', { value: percent(sinceRetired, { decimals: 0 }) }) }}</v-chip>

            <v-btn
              v-if="instructionsUrl"
              class="ms-auto"
              :href="instructionsUrl"
              prepend-icon="mdi-book-open-page-variant-outline"
              rel="noopener"
              size="small"
              target="_blank"
              variant="text"
            >{{ t('detail.instructions') }}</v-btn>

            <v-btn
              v-if="bricksetUrl"
              :class="{ 'ms-auto': !instructionsUrl }"
              :href="bricksetUrl"
              prepend-icon="mdi-open-in-new"
              rel="noopener"
              size="small"
              target="_blank"
              variant="text"
            >Brickset</v-btn>

            <v-btn
              :class="instructionsUrl ? '' : 'ms-auto'"
              :href="`https://www.brickeconomy.com/search?q=${catalog.catalog_num}`"
              size="small"
              target="_blank"
              variant="text"
            >{{ t('detail.openBrickLink') }}</v-btn>
          </div>

          <!-- Vlastné kategórie setu. Pri sérii platia pre všetky jej figúrky. -->
          <CategoryMembership ref="membership" class="mb-3" :num="catalog.catalog_num" @manage="managerOpen = true" />

          <v-row dense>
            <v-col cols="6" md="2" sm="4">
              <div class="text-body-small text-medium-emphasis">{{ t('detail.parts') }}</div>
              <div class="text-title-large font-weight-medium">{{ count(catalog.num_parts) }}</div>
            </v-col>

            <v-col cols="6" md="2" sm="4">
              <div class="text-body-small text-medium-emphasis">{{ t('detail.minifigs') }}</div>
              <div class="text-title-large font-weight-medium">{{ count(catalog.num_minifigs) }}</div>
            </v-col>

            <v-col cols="6" md="2" sm="4">
              <div class="text-body-small text-medium-emphasis">{{ t('detail.rrp') }}</div>
              <div class="text-title-large font-weight-medium">{{ exactMoney(catalog.rrp_eur) }}</div>
            </v-col>

            <v-col cols="6" md="2" sm="4">
              <div class="text-body-small text-medium-emphasis">{{ t('detail.ownedPieces') }}</div>
              <div class="text-title-large font-weight-medium">{{ owned.length }}</div>
            </v-col>

            <v-col cols="6" md="2" sm="4">
              <div class="text-body-small text-medium-emphasis">{{ t('detail.unrealized') }}</div>

              <div
                class="text-title-large font-weight-medium"
                :class="priceUnknown
                  ? 'text-medium-emphasis'
                  : totals.unrealized >= 0 ? 'text-positive' : 'text-negative'"
              >{{ priceUnknown ? '—' : money(totals.unrealized, { sign: true, decimals: Math.abs(totals.unrealized) < 100 ? 2 : 0 }) }}</div>
            </v-col>

            <v-col cols="6" md="2" sm="4">
              <div class="text-body-small text-medium-emphasis">{{ t('detail.realized') }}</div>

              <div
                class="text-title-large font-weight-medium"
                :class="totals.realized >= 0 ? 'text-positive' : 'text-negative'"
              >{{ sold.length > 0 ? money(totals.realized, { sign: true, decimals: 0 }) : '—' }}</div>
            </v-col>
          </v-row>

          <!-- Z Brickset: hodnotenie, obľúbenosť, štítky a oficiálny popis od LEGO. -->
          <div
            v-if="catalog.bs_rating || catalog.bs_owned_by || catalog.tags?.length || catalog.description"
            class="mt-3 d-flex flex-column ga-2"
          >
            <div v-if="catalog.bs_rating || catalog.bs_owned_by" class="d-flex align-center flex-wrap ga-2 text-body-medium">
              <template v-if="catalog.bs_rating">
                <v-rating
                  active-color="amber"
                  color="amber"
                  density="compact"
                  half-increments
                  :model-value="catalog.bs_rating"
                  readonly
                  size="small"
                />

                <span class="font-weight-medium">{{ ratingText }}</span>

                <span class="text-medium-emphasis">
                  ({{ t('detail.ratingsPlural', catalog.bs_rating_count ?? 0, { named: { count: catalog.bs_rating_count ?? 0 } }) }})
                </span>
              </template>

              <span v-if="catalog.bs_owned_by" class="text-medium-emphasis">
                {{ t('detail.popularity', { owned: count(catalog.bs_owned_by), wanted: count(catalog.bs_wanted_by ?? 0) }) }}
              </span>
            </div>

            <div v-if="catalog.tags?.length" class="d-flex flex-wrap ga-1">
              <!-- Štítok vedie do Zbierky vyfiltrovanej podľa neho. -->
              <v-chip
                v-for="tag in catalog.tags"
                :key="tag"
                label
                prepend-icon="mdi-tag-outline"
                size="small"
                :to="{ name: 'collection', query: { tag } }"
                variant="tonal"
              >{{ tag }}</v-chip>
            </div>

            <div v-if="catalog.description">
              <div class="text-body-medium set-description" :class="{ 'set-description--clamped': !descriptionOpen }">
                {{ catalog.description }}
              </div>

              <v-btn
                v-if="catalog.description.length > 220"
                class="px-0"
                size="x-small"
                variant="text"
                @click="descriptionOpen = !descriptionOpen"
              >{{ descriptionOpen ? t('detail.descriptionLess') : t('detail.descriptionMore') }}</v-btn>
            </div>
          </div>

          <KeyHint
            v-if="!auth.hasBricksetKey"
            class="mt-3"
            service="brickset"
            :text="t('keyHint.bricksetDetail')"
          />

          <KeyHint
            v-if="!auth.can('rebrickable.set') && catalog.source !== 'manual'"
            class="mt-1"
            service="rebrickable"
            :text="t('keyHint.rebrickableDetail')"
          />

          <SetGallery
            v-if="showGallery"
            :key="catalog.catalog_num"
            class="mt-3"
            :name="catalog.name"
            :num="catalog.catalog_num"
          />

          <v-alert class="mt-3" density="compact" variant="tonal">
            <span class="text-body-small">
              {{ t('detail.metaSource', {
                sources: catalog.source,
                date: shortDate(catalog.fetched_at),
              }) }}
            </span>
          </v-alert>
        </div>
      </div>
    </v-card>

    <!-- Kusy a cena pod sebou: cena je potom široká a nízka, detail sa zmestí na obrazovku. -->
    <v-row dense>
      <v-col cols="12">
        <v-card border flat>
          <v-card-item>
            <div class="d-flex align-center ga-2 flex-wrap">
              <v-card-title class="text-title-large font-weight-medium pa-0">{{ t('detail.myPieces') }}</v-card-title>

              <span class="text-body-medium text-medium-emphasis">
                {{ t('detail.ownedPlural', owned.length, { named: { count: owned.length } }) }}
                ·
                {{ t('collection.soldPlural', sold.length, { named: { count: sold.length } }) }}
              </span>

              <!-- Zbierka figúrky zo sérií nemá, hromadná úprava je preto tu. -->
              <v-btn
                v-if="isSeriesPage && owned.length > 0 && !selection.active.value"
                class="ms-auto"
                prepend-icon="mdi-checkbox-multiple-outline"
                size="small"
                variant="text"
                @click="selection.active.value = true"
              >{{ t('bulk.select') }}</v-btn>

              <!-- Ďalší kus toho istého setu netreba hľadať, stačí doplniť kúpu.
                   Pri sérii treba vybrať figúrku, to je v sekcii Figúrky. -->
              <v-btn
                v-if="isSeriesPage"
                :class="owned.length > 0 && !selection.active.value ? '' : 'ms-auto'"
                prepend-icon="mdi-plus"
                size="small"
                :to="{ name: 'minifig-series', params: { num } }"
                variant="outlined"
              >{{ t('detail.addPiece') }}</v-btn>

              <v-btn
                v-else
                class="ms-auto"
                :disabled="!catalog"
                prepend-icon="mdi-plus"
                size="small"
                variant="outlined"
                @click="buyOpen = true"
              >{{ t('detail.addPiece') }}</v-btn>
            </div>
          </v-card-item>

          <v-divider />

          <!--
            Kusy aj súčty sú jedna mriežka. Stĺpce určuje len .pieces-grid,
            riadky ich preberajú (subgrid): sumy stoja pod sebou, nech má
            riadok štítkov koľkokoľvek, a súčet je presne pod nimi. Na úzkej
            obrazovke sú štítky nad sumami, sumy v troch rovnakých stĺpcoch.
          -->
          <div class="pieces">
            <div class="pieces-grid">
              <div
                v-for="item in pieces"
                :key="item.id"
                class="piece-row"
                :class="{ 'bg-surface-variant': item.status === 'sold' }"
              >
                <div class="piece-cell piece-cell--main">
                  <v-btn
                    v-if="selection.active.value && item.status === 'owned'"
                    :color="selection.hasItem(item.id) ? 'primary' : undefined"
                    :icon="selection.hasItem(item.id) ? 'mdi-checkbox-marked' : 'mdi-checkbox-blank-outline'"
                    size="small"
                    :title="t('bulk.select')"
                    variant="text"
                    @click="selection.toggleItem(item.id)"
                  />

                  <div class="piece-info">
                    <!--
                      Stav je hlavná informácia o kuse, preto stojí sám na
                      vlastnom riadku. Medzi ostatnými čipmi sa strácal.
                    -->
                    <div
                      v-if="item.catalog_num !== num"
                      class="text-body-medium font-weight-medium"
                    >
                      {{ item.catalog.name }}
                      <span class="text-body-small text-medium-emphasis">{{ item.catalog_num }}</span>
                    </div>

                    <div class="d-flex flex-wrap ga-2 align-center mb-1">
                      <v-chip
                        :color="item.status === 'sold' ? undefined : conditionColor(item.condition)"
                        label
                        :prepend-icon="conditionIcon(item.condition)"
                        size="small"
                        variant="flat"
                      >{{ t(`condition.${item.condition}`) }}</v-chip>

                      <v-chip
                        v-if="item.status === 'sold'"
                        label
                        prepend-icon="mdi-check"
                        size="small"
                        variant="tonal"
                      >{{ t('collection.status.sold') }}</v-chip>

                      <v-chip
                        v-if="item.unidentified"
                        color="secondary"
                        label
                        size="small"
                        variant="tonal"
                      >{{ t('detail.unidentified') }}</v-chip>
                    </div>

                    <div class="d-flex flex-wrap ga-1">
                      <v-chip
                        v-if="item.purpose"
                        color="primary"
                        label
                        prepend-icon="mdi-tag-outline"
                        size="small"
                        variant="outlined"
                      >{{ t(`purpose.${item.purpose}`) }}</v-chip>

                      <ConditionChips
                        :condition="null"
                        :flags="item.flags"
                        :location="placeLabel(item.location, item.box)"
                        :variant="item.price_variant"
                      />
                    </div>

                    <div class="text-body-small text-medium-emphasis mt-1">
                      <template v-if="item.status === 'sold'">
                        {{ shortDate(item.sold_date) }}
                        <span v-if="item.sold_via"> · {{ item.sold_via }}</span>
                      </template>

                      <template v-else>
                        {{ shortDate(item.purchase_date) }}
                        <span v-if="item.purchase_place"> · {{ item.purchase_place }}</span>
                      </template>
                    </div>
                  </div>
                </div>

                <!-- Popis nad sumou má každá bunka sama, na telefóne sa inak nedá čítať, čo je čo. -->
                <div class="piece-cell piece-cell--purchased piece-amount">
                  <div class="text-body-small text-medium-emphasis">{{ t('detail.columnPurchased') }}</div>

                  <div class="text-body-medium">
                    <v-icon
                      v-if="item.purchase_price_auto"
                      class="me-1"
                      icon="mdi-auto-fix"
                      size="x-small"
                      :title="t('purchaseAuto.title')"
                    />{{ exactMoney(paid(item)) }}
                  </div>

                  <div v-if="item.purchase_real_eur" class="text-body-small text-medium-emphasis">
                    {{ t('inflation.paid', { amount: exactMoney(item.purchase_price_eur) }) }}
                  </div>
                </div>

                <div class="piece-cell piece-cell--value piece-amount">
                  <div class="text-body-small text-medium-emphasis">
                    {{ item.status === 'sold' ? t('collection.soldFor') : t('detail.columnValue') }}
                  </div>

                  <div class="text-body-large font-weight-medium">{{ pieceValue(item) }}</div>
                </div>

                <div class="piece-cell piece-cell--profit piece-amount">
                  <div class="text-body-small text-medium-emphasis">{{ t('detail.columnProfit') }}</div>

                  <div class="text-body-medium font-weight-medium" :class="pieceProfitClass(item)">
                    {{ pieceProfit(item) }}
                  </div>

                  <!-- Pod rok držania server ročný výnos nepošle, riadok potom chýba. -->
                  <div
                    v-if="item.status === 'owned' && item.cagr_pct !== null && item.cagr_pct !== undefined"
                    class="text-body-small"
                    :class="item.cagr_pct >= 0 ? 'text-positive' : 'text-negative'"
                  >{{ t('detail.yearly', { value: percent(item.cagr_pct, { decimals: 1 }) }) }}</div>
                </div>

                <div class="piece-cell piece-cell--actions">
                  <v-btn
                    icon="mdi-pencil-outline"
                    size="small"
                    :title="t('piece.title')"
                    variant="text"
                    @click="openEdit(item)"
                  />

                  <!-- Počet vedľa ikony, nie odznak: tlačidlo orezáva, čo z neho trčí. -->
                  <v-btn
                    v-if="photoCounts[item.id]"
                    color="primary"
                    prepend-icon="mdi-camera"
                    size="small"
                    :title="t('detail.photos')"
                    variant="tonal"
                    @click="openPhotos(item)"
                  >{{ photoCounts[item.id] }}</v-btn>

                  <v-btn
                    v-else
                    icon="mdi-camera-outline"
                    size="small"
                    :title="t('detail.photos')"
                    variant="text"
                    @click="openPhotos(item)"
                  />

                  <v-btn
                    v-if="item.status === 'owned'"
                    icon="mdi-text-box-edit-outline"
                    size="small"
                    :title="t('detail.listing')"
                    variant="text"
                    @click="openListing(item)"
                  />

                  <v-btn
                    v-if="item.status === 'owned'"
                    size="small"
                    variant="outlined"
                    @click="openSell(item)"
                  >{{ t('detail.sell') }}</v-btn>

                  <v-btn
                    v-else
                    size="small"
                    variant="text"
                    @click="unsell(item.id)"
                  >{{ t('detail.unsell') }}</v-btn>
                </div>
              </div>

              <!-- Súčty majú tie isté bunky ako kus, akcie ostanú prázdne. -->
              <div class="piece-row piece-row--total text-body-medium">
                <div class="piece-cell piece-cell--main text-medium-emphasis">
                  {{ t('detail.totalOwned', { count: owned.length }) }}
                </div>

                <div class="piece-cell piece-cell--purchased piece-amount">{{ money(totals.purchase) }}</div>

                <div class="piece-cell piece-cell--value piece-amount font-weight-medium">
                  {{ priceUnknown ? '—' : money(totals.market) }}
                </div>

                <div
                  class="piece-cell piece-cell--profit piece-amount font-weight-medium"
                  :class="priceUnknown
                    ? 'text-medium-emphasis'
                    : totals.unrealized >= 0 ? 'text-positive' : 'text-negative'"
                >{{ priceUnknown ? '—' : money(totals.unrealized, { sign: true }) }}</div>

                <div class="piece-cell piece-cell--actions" />
              </div>

              <div v-if="sold.length > 0" class="piece-row piece-row--total text-body-medium">
                <div class="piece-cell piece-cell--main text-medium-emphasis">
                  {{ t('detail.totalSold', { count: sold.length }) }}
                </div>

                <div class="piece-cell piece-cell--purchased piece-amount">{{ money(totals.soldPurchase) }}</div>

                <div class="piece-cell piece-cell--value piece-amount font-weight-medium">
                  {{ money(totals.soldProceeds) }}
                </div>

                <div
                  class="piece-cell piece-cell--profit piece-amount font-weight-medium"
                  :class="totals.realized >= 0 ? 'text-positive' : 'text-negative'"
                >{{ money(totals.realized, { sign: true }) }}</div>

                <div class="piece-cell piece-cell--actions" />
              </div>
            </div>
          </div>

          <!-- Rozsah je séria bez obmedzenia Zbierky: figúrky aj sáčky, len vlastnené. -->
          <BulkBar
            v-if="isSeriesPage && selection.active.value"
            :query="seriesScope"
            :selection="selection"
            :total="owned.length"
            unit="pieces"
            @done="onBulkDone"
          />
        </v-card>
      </v-col>

      <v-col cols="12">
        <v-card border class="pa-4 d-flex flex-column ga-3" flat>
          <div class="d-flex align-center">
            <div class="text-title-large font-weight-medium">{{ t('detail.marketPrice') }}</div>

            <span class="ms-auto text-body-small text-medium-emphasis">
              {{ auth.hasPriceKey ? t('detail.priceSourceNote') : t('prices.providerOff') }}
            </span>
          </div>

          <KeyHint v-if="!auth.hasPriceKey" service="brickeconomy" :text="t('keyHint.priceDetail')" />

          <div class="price-body">
            <div class="d-flex flex-column ga-3">
              <template v-if="hasAnyPrice">
                <div class="d-flex ga-2">
                  <v-card
                    v-for="tile in ([
                      { key: 'N', label: t('detail.new'), data: pricesN },
                      { key: 'U', label: t('detail.used'), data: pricesU },
                    ] as const)"
                    :key="tile.key"
                    border
                    class="pa-3 flex-grow-1 price-tile"
                    :class="{ 'price-tile--active': priceCondition === tile.key }"
                    flat
                    @click="priceCondition = tile.key"
                  >
                    <div class="text-body-small text-medium-emphasis">{{ tile.label }}</div>

                    <div
                      v-if="tile.data?.current"
                      class="text-headline-small font-weight-medium"
                    >{{ exactMoney(tile.data.current.avg_price) }}</div>

                    <div v-else class="text-body-medium text-medium-emphasis mt-1">
                      {{ tile.key === 'U' ? t('detail.noUsedPrice') : t('detail.noNewPrice') }}
                    </div>
                  </v-card>
                </div>
              </template>

              <!--
            Odhad a rast prišli v tej istej odpovedi ako cena, zadarmo.
            Odhad sa týka nového setu, preto to tak aj píše.
          -->
              <v-card
                v-if="hasForecast"
                class="pa-3"
                color="surface-variant"
                flat
              >
                <div class="text-body-small text-medium-emphasis mb-1">{{ t('detail.forecastTitle') }}</div>

                <div class="d-flex ga-4 flex-wrap">
                  <div v-if="catalog?.forecast_2y_eur">
                    <div class="text-body-small text-medium-emphasis">{{ t('detail.forecast2y') }}</div>
                    <div class="text-body-large font-weight-medium">{{ exactMoney(catalog.forecast_2y_eur) }}</div>
                  </div>

                  <div v-if="catalog?.forecast_5y_eur">
                    <div class="text-body-small text-medium-emphasis">{{ t('detail.forecast5y') }}</div>
                    <div class="text-body-large font-weight-medium">{{ exactMoney(catalog.forecast_5y_eur) }}</div>
                  </div>

                  <div v-if="catalog?.growth_12m_pct !== null && catalog?.growth_12m_pct !== undefined">
                    <div class="text-body-small text-medium-emphasis">{{ t('detail.growth12m') }}</div>

                    <div
                      class="text-body-large font-weight-medium"
                      :class="catalog.growth_12m_pct >= 0 ? 'text-positive' : 'text-negative'"
                    >{{ percent(catalog.growth_12m_pct) }}</div>
                  </div>
                </div>
              </v-card>

              <template v-if="prices?.current">
                <div v-if="aboveRrp !== null" class="d-flex">
                  <v-chip
                    :color="aboveRrp >= 0 ? 'positive' : 'negative'"
                    size="small"
                    variant="tonal"
                  >
                    {{ aboveRrp >= 0
                      ? t('detail.aboveRrp', { value: percent(aboveRrp, { decimals: 0 }) })
                      : t('detail.belowRrp', { value: percent(Math.abs(aboveRrp), { decimals: 0, sign: false }) }) }}
                  </v-chip>
                </div>

                <div class="d-flex ga-2">
                  <v-card
                    v-for="delta in prices.deltas"
                    :key="delta.window_days"
                    class="pa-2 text-center flex-grow-1"
                    color="surface-variant"
                    flat
                  >
                    <div class="text-body-small text-medium-emphasis">
                      {{ delta.window_days === 365 ? t('detail.year') : `${delta.window_days} dní` }}
                    </div>

                    <div
                      class="text-body-medium font-weight-medium"
                      :class="delta.delta_pct === null ? '' : delta.delta_pct >= 0 ? 'text-positive' : 'text-negative'"
                    >{{ delta.delta_pct === null ? '—' : percent(delta.delta_pct) }}</div>
                  </v-card>
                </div>

                <v-card class="pa-3" color="surface-variant" flat>
                  <div class="d-flex ga-4 flex-wrap">
                    <div>
                      <div class="text-body-small text-medium-emphasis">{{ t('detail.lowest') }}</div>
                      <div class="text-body-large font-weight-medium">{{ exactMoney(prices.current.min_price) }}</div>
                    </div>

                    <div>
                      <div class="text-body-small text-medium-emphasis">{{ t('detail.highest') }}</div>
                      <div class="text-body-large font-weight-medium">{{ exactMoney(prices.current.max_price) }}</div>
                    </div>

                    <div v-if="prices.current.qty">
                      <div class="text-body-small text-medium-emphasis">{{ t('detail.sales') }}</div>
                      <div class="text-body-large font-weight-medium">{{ prices.current.qty }}</div>
                    </div>
                  </div>
                </v-card>
              </template>
            </div>

            <!-- Graf sa sám skryje, kým nemá aspoň dva rôzne dni; čísla potom zaberú celú šírku. -->
            <PriceHistoryChart
              v-if="!isSeriesPage"
              :new-points="pricesN?.history ?? []"
              :purchase="averagePurchase"
              :used-points="pricesU?.history ?? []"
            />
          </div>

          <template v-if="hasAnyPrice">
            <v-divider />

            <div class="d-flex align-center ga-2 flex-wrap">
              <span v-if="lastCaptured" class="text-body-small text-medium-emphasis">
                {{ t('detail.updatedAt', { time: dateTime(lastCaptured) }) }}
              </span>

              <v-spacer />

              <v-btn size="small" variant="text" @click="manualOpen = true">
                {{ t('detail.manualPrice') }}
              </v-btn>

              <v-btn
                v-if="providerEnabled"
                :loading="refreshing"
                prepend-icon="mdi-refresh"
                size="small"
                variant="outlined"
                @click="refreshPrice"
              >{{ isSeriesPage ? t('detail.refreshSeries') : t('detail.refreshPrices') }}</v-btn>
            </div>

            <div v-if="refreshNote" class="text-body-small text-medium-emphasis">{{ refreshNote }}</div>
          </template>

          <template v-else>
            <v-empty-state
              icon="mdi-currency-eur-off"
              :text="auth.hasPriceKey ? t('detail.noPriceRefreshHint') : t('detail.noPriceHint')"
              :title="t('detail.noPrice')"
            />

            <div class="d-flex justify-center ga-2 flex-wrap">
              <v-btn
                v-if="auth.can('brickeconomy.price_detail')"
                color="primary"
                :loading="refreshing"
                prepend-icon="mdi-refresh"
                variant="flat"
                @click="refreshPrice"
              >{{ isSeriesPage ? t('detail.refreshSeries') : t('detail.refreshPrices') }}</v-btn>

              <v-btn variant="outlined" @click="manualOpen = true">
                {{ t('detail.manualPrice') }}
              </v-btn>
            </div>

            <div v-if="refreshNote" class="text-body-small text-medium-emphasis text-center">
              {{ refreshNote }}
            </div>
          </template>
        </v-card>
      </v-col>
    </v-row>

    <SellDialog
      v-model="sellOpen"
      :item="sellTarget"
      @confirm="confirmSell"
    />

    <PurchaseDialog v-model="buyOpen" :catalog="catalog" @saved="onPieceBought" />

    <PhotosDialog v-model="photosOpen" :item="photosTarget" @changed="onPhotosChanged" />

    <CategoryManager v-model="managerOpen" @changed="membership?.reload()" />

    <ListingDialog
      v-model="listingOpen"
      :catalog="catalog"
      :item="listingTarget"
      :prices-new="pricesN"
      :prices-used="pricesU"
    />

    <!-- Kategórie z úpravy kusu patria setu: obnoví sa aj riadok kategórií hore. -->
    <PieceDialog
      v-model="editOpen"
      :item="editTarget"
      :locations="locations"
      @categories-changed="membership?.reload()"
      @remove="removePiece"
      @save="savePiece"
    />

    <v-dialog v-model="manualOpen" max-width="420">
      <v-card>
        <v-card-title>{{ t('prices.manualTitle') }}</v-card-title>

        <v-card-text>
          <v-text-field
            v-model="manualPrice"
            autofocus
            :hint="t('prices.manualHint')"
            :label="t('detail.average')"
            persistent-hint
            prefix="€"
            type="number"
          />
        </v-card-text>

        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="manualOpen = false">{{ t('common.cancel') }}</v-btn>

          <v-btn color="primary" variant="flat" @click="saveManualPrice">
            {{ t('prices.manualSave') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<style scoped>
.set-description {
  white-space: pre-line;
}

/* Popis od LEGO býva dlhý; v detaile stačia tri riadky, zvyšok na kliknutie. */
.set-description--clamped {
  -webkit-box-orient: vertical;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  overflow: hidden;
}

/*
 * Moje kusy: jedna mriežka pre kusy aj súčty. Šírky stĺpcov sú len tu,
 * riadok je subgrid a preberá ich. Stĺpec sumy má šírku najširšej bunky
 * zo všetkých riadkov, takže Kúpené, Hodnota a Zisk stoja pod sebou aj
 * pod súčtom, nech má riadok štítkov koľkokoľvek. Štítky sa zalomia vo
 * svojej bunke, sumy sa nepohnú.
 */
.pieces {
  container-type: inline-size;
}

.pieces-grid {
  column-gap: 16px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) repeat(3, minmax(6.5rem, max-content)) max-content;
}

/*
 * Bunky začínajú hore: popisy súm sú v jednom riadku a sumy v druhom,
 * aj keď má jedna bunka pod sumou ešte ročný výnos.
 */
.piece-row {
  align-items: start;
  border-bottom: thin solid rgba(var(--v-border-color), var(--v-border-opacity));
  display: grid;
  grid-column: 1 / -1;
  grid-template-columns: subgrid;
  padding: 12px;
  row-gap: 8px;
}

.piece-row--total {
  border-bottom: 0;
  padding-block: 2px;
  row-gap: 0;
}

.piece-row:not(.piece-row--total) + .piece-row--total {
  padding-top: 12px;
}

.piece-row--total:last-child {
  padding-bottom: 12px;
}

.piece-cell {
  min-width: 0;
}

.piece-cell--main {
  align-items: center;
  display: flex;
  gap: 12px;
}

.piece-info {
  flex: 1 1 auto;
  min-width: 0;
}

.piece-amount {
  font-variant-numeric: tabular-nums;
  text-align: end;
}

/* Úprava a fotky sú v každom riadku prvé, tak stoja pod sebou aj pri predanom kuse. */
.piece-cell--actions {
  align-items: center;
  align-self: center;
  display: flex;
  gap: 4px;
}

/*
 * Stredná karta (tablet, užšie okno): štítky aj popis súčtu na celú
 * šírku, pod nimi sumy a akcie v tých istých stĺpcoch ako na širokej.
 */
@container (max-width: 840px) {
  .piece-cell--main {
    grid-column: 1 / -1;
  }

  .piece-cell--purchased {
    grid-column: 2;
  }

  .piece-cell--value {
    grid-column: 3;
  }

  .piece-cell--profit {
    grid-column: 4;
  }

  .piece-cell--actions {
    grid-column: 5;
  }
}

/*
 * Úzka karta (telefón): štítky na celú šírku, pod nimi tri sumy
 * v rovnakých stĺpcoch a akcie vpravo. Súčet má popis nad sumami.
 */
@container (max-width: 640px) {
  .pieces-grid {
    column-gap: 4px;
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .piece-cell--main,
  .piece-cell--actions {
    grid-column: 1 / -1;
  }

  .piece-cell--purchased {
    grid-column: 1;
  }

  .piece-cell--value {
    grid-column: 2;
  }

  .piece-cell--profit {
    grid-column: 3;
  }

  .piece-cell--actions {
    justify-content: flex-end;
  }

  .piece-row--total .piece-cell--actions {
    display: none;
  }
}

/* Čísla a graf vedľa seba, kým je miesto; na úzkej obrazovke pod sebou. */
.price-body {
  align-items: start;
  display: grid;
  gap: 16px;
  grid-template-columns: repeat(auto-fit, minmax(min(360px, 100%), 1fr));
}

/* Dlaždica ceny je zároveň prepínač stavu pre históriu pod ňou. */
.price-tile {
  cursor: pointer;
}

.price-tile--active {
  border-color: rgb(var(--v-theme-primary)) !important;
  background: rgba(var(--v-theme-primary), 0.06);
}
</style>
