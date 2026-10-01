<script setup lang="ts">
  /**
   * Zoznam želaných setov s ich aktuálnou trhovou cenou.
   *
   * Radí a filtruje server (`GET /wishlist?sort=&dir=&q=&reached=…`),
   * rovnako ako Zbierka; predvolene najbližšie k cieľovej cene navrch.
   */
  import type { WishlistItem } from '@/api/types'
  import { useDebounceFn } from '@vueuse/core'
  import { computed, onMounted, reactive, ref, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { api, errorMessage } from '@/api/client'
  import CardGrid from '@/components/CardGrid.vue'
  import KeyHint from '@/components/KeyHint.vue'
  import LoadFailed from '@/components/LoadFailed.vue'
  import PageSkeleton from '@/components/PageSkeleton.vue'
  import PhotoZoom from '@/components/PhotoZoom.vue'
  import PurchaseDialog from '@/components/PurchaseDialog.vue'
  import SetImage from '@/components/SetImage.vue'
  import SortHeader from '@/components/SortHeader.vue'
  import { useOwnedHint } from '@/composables/useOwnedHint'
  import { usePageLoad } from '@/composables/usePageLoad'
  import { useAuthStore } from '@/stores/auth'
  import { useCollectionStore } from '@/stores/collection'
  import { useNotifyStore } from '@/stores/notify'
  import { useProfileStore } from '@/stores/preferences'
  import { count, exactMoney, percent, shortDate, toNumber } from '@/utils/format'
  import { imageSrc } from '@/utils/imageSrc'
  import { priceValue } from '@/utils/priceEdit'
  import { headerDir, nextSort } from '@/utils/tableSort'
  import { hasWishFilter, wishlistQuery } from '@/utils/wishlistQuery'

  const { t } = useI18n()
  const auth = useAuthStore()
  const notify = useNotifyStore()
  const collection = useCollectionStore()

  const items = ref<WishlistItem[]>([])
  const error = ref<string | null>(null)
  const addOpen = ref(false)
  const newNumber = ref('')
  const targetPrice = ref('')
  const saving = ref(false)
  /** Set z hlavy, ktorý už mám v zbierke alebo v Chcem: pod číslom to povie. */
  const { hint: ownedHint } = useOwnedHint(newNumber, () => items.value.map(item => item.catalog_num))
  const buying = ref<WishlistItem | null>(null)
  const buyOpen = ref(false)

  type WishSort = 'distance' | 'market' | 'target' | 'name' | 'theme' | 'added'
  const SORTS: WishSort[] = ['distance', 'market', 'target', 'name', 'theme', 'added']
  const DEFAULT_DIR: Record<WishSort, 'asc' | 'desc'> = {
    distance: 'asc', market: 'desc', target: 'desc', name: 'asc', theme: 'asc', added: 'desc',
  }
  const view = reactive({
    q: '' as string | null,
    sort: 'distance' as WishSort,
    dir: null as 'asc' | 'desc' | null,
    reached: false,
    retired: false,
    noPrice: false,
    themes: [] as string[],
  })
  /** Karty alebo tabuľka, ako v Zbierke; voľba sa pamätá pri účte (`preferences.wishlist`). */
  const profile = useProfileStore()
  const tableView = ref(false)
  function setView (table: boolean): void {
    tableView.value = table
    profile.save('wishlist', table ? { view: 'table' } : {})
  }
  profile.load().then(() => {
    tableView.value = profile.get('wishlist')?.view === 'table'
  }).catch(() => {
    // Bez nastavení ostanú karty.
  })

  /** Voľby filtra Séria s počtom setov podľa ostatných filtrov (server). */
  const themeOptions = ref<Array<{ value: string, count: number }>>([])
  const themeName = (value: string): string => value === '__none__' ? t('wishlist.noTheme') : value
  /** Čip Séria: bez výberu len „Séria“, s jednou „Séria: Marvel“, s viacerými počet. */
  const themeLabel = computed(() => {
    if (view.themes.length === 0) return t('wishlist.filterTheme')
    if (view.themes.length === 1) return `${t('wishlist.filterTheme')}: ${themeName(view.themes[0]!)}`
    return `${t('wishlist.filterTheme')} · ${view.themes.length}`
  })

  function toggleTheme (value: string): void {
    view.themes = view.themes.includes(value)
      ? view.themes.filter(theme => theme !== value)
      : [...view.themes, value]
  }
  const effectiveDir = (): 'asc' | 'desc' => view.dir ?? DEFAULT_DIR[view.sort]

  /** Stĺpce tabuľky a ich zoradenie; fotka a akcie neradia. */
  const COLUMNS: Array<{ sort: WishSort, title: string, end?: boolean }> = [
    { sort: 'name', title: 'wishlist.colSet' },
    { sort: 'theme', title: 'wishlist.filterTheme' },
    { sort: 'market', title: 'wishlist.marketNow', end: true },
    { sort: 'target', title: 'wishlist.target', end: true },
    { sort: 'distance', title: 'wishlist.distance', end: true },
  ]
  const defaultDir = (key: WishSort): 'asc' | 'desc' => DEFAULT_DIR[key]

  /** Klik na hlavičku mení to isté zoradenie ako výber nad kartami. */
  function sortBy (key: WishSort): void {
    const next = nextSort(key, { sort: view.sort, dir: view.dir }, defaultDir)
    // Kľúč najprv: watch pri zmene kľúča smer vynuluje.
    view.sort = next.sort
    view.dir = next.dir
  }

  function flipDir (): void {
    const next = effectiveDir() === 'asc' ? 'desc' : 'asc'
    view.dir = next === DEFAULT_DIR[view.sort] ? null : next
  }

  watch(() => view.sort, () => {
    view.dir = null
  }, { flush: 'sync' })

  /** Úprava cieľovej ceny a poznámky. */
  const editing = ref<WishlistItem | null>(null)
  const editOpen = ref(false)
  const editTarget = ref<string | null>('')
  const editNote = ref<string | null>('')

  function openEdit (item: WishlistItem): void {
    editing.value = item
    editTarget.value = item.target_price_eur ? String(toNumber(item.target_price_eur)) : ''
    editNote.value = item.note ?? ''
    editOpen.value = true
  }

  async function saveEdit (): Promise<void> {
    if (!editing.value) return
    saving.value = true
    // Pole je clearable: tlačidlo X nastaví null, nie prázdny reťazec.
    const { error: err } = await api.PATCH('/wishlist/{item_id}', {
      params: { path: { item_id: editing.value.id } },
      body: { target_price_eur: priceValue(editTarget.value), note: (editNote.value ?? '').trim() || null },
    }).finally(() => {
      saving.value = false
    })
    if (err) {
      notify.error(err, t('notice.saveFailed'))
      return
    }
    notify.success(t('wishlist.edited', { name: editing.value.catalog.name }))
    editOpen.value = false
    await page.run()
  }

  function openBuy (item: WishlistItem): void {
    buying.value = item
    buyOpen.value = true
  }

  async function load (): Promise<boolean> {
    const query = wishlistQuery(view) as never
    const [list, themes] = await Promise.all([
      api.GET('/wishlist', { params: { query } }),
      api.GET('/wishlist/themes', { params: { query } }),
    ])
    if (list.error || !list.data) return false
    items.value = list.data
    themeOptions.value = themes.data ?? []
    return true
  }

  /**
   * Prvé načítanie kostra, zmena filtra a Obnoviť stránku nad starými
   * kartami (usePageLoad). „Zatiaľ nič nechceš“ až po odpovedi servera.
   */
  const page = usePageLoad(load)
  const reload = useDebounceFn(() => page.run(), 250)
  watch(() => ({ ...view }), reload, { deep: true })

  /** Súhrn obnovuje zmena z tejto stránky, ktorá zoznam načíta sama. */
  let ownChange = false

  // Chcem mení aj kúpa (PurchaseDialog obnoví súhrn), pridanie kusu inde
  // alebo Späť v oznámení; počet v súhrne (ponuka) sa po nich obnoví
  // a prezradí to. Synchrónne, aby zmena z tejto stránky (`ownChange`)
  // zoznam nenačítala druhý raz.
  watch(() => collection.summary?.wishlist_count, (now, before) => {
    if (!ownChange && before !== undefined && now !== before) reload()
  }, { flush: 'sync' })

  /**
   * Pridanie či odobratie tu: zoznam sa načíta hneď a súhrn s ním, aby
   * odznak Chcem v ponuke ukázal nový počet.
   */
  async function afterChange (): Promise<void> {
    ownChange = true
    const summary = collection.loadDashboard().finally(() => {
      ownChange = false
    })
    await Promise.all([page.run(), summary])
  }

  /**
   * Kúpa z Chcem: súhrn obnoví dialóg a zoznam načíta watch nad počtom
   * (server kúpený set z Chcem vždy vyradí). Len bez súhrnu, keď watch
   * zmenu nespozná, sa zoznam načíta tu.
   */
  /**
   * Po kúpe: keď set ostal v Chcem, počet sa nezmenil a zoznam by sa sám
   * nenačítal; karta má hneď ukázať „V zbierke“. Inak ho načíta zmena počtu.
   */
  function afterPurchase (keptInWishlist?: boolean): void {
    if (keptInWishlist || !collection.summary) void page.run()
  }

  const filtered = (): boolean => hasWishFilter(view)

  async function add (): Promise<void> {
    if (!newNumber.value.trim()) return
    saving.value = true
    error.value = null
    const { error: err } = await api.POST('/wishlist', {
      body: {
        catalog_num: newNumber.value.trim(),
        target_price_eur: targetPrice.value ? String(Number(targetPrice.value)) : null,
        note: null,
      },
    })
    saving.value = false
    if (err) {
      error.value = errorMessage(err, 'Set sa nepodarilo pridať')
      return
    }
    notify.success(t('notice.wishAdded', { name: newNumber.value.trim() }))
    addOpen.value = false
    newNumber.value = ''
    targetPrice.value = ''
    await afterChange()
  }

  async function remove (item: WishlistItem): Promise<void> {
    const { error: err } = await api.DELETE('/wishlist/{item_id}', { params: { path: { item_id: item.id } } })
    if (err) {
      notify.error(err, t('notice.wishFailed'))
      return
    }
    notify.success(t('notice.wishRemoved', { name: item.catalog.name }))
    await afterChange()
  }

  onMounted(() => page.run())
</script>

<template>
  <div class="d-flex flex-column ga-4">
    <KeyHint v-if="!auth.hasPriceKey" service="brickeconomy" :text="t('keyHint.wishlist')" />

    <div class="d-flex align-center flex-wrap ga-2">
      <v-text-field
        v-model="view.q"
        clearable
        density="compact"
        hide-details
        :placeholder="t('wishlist.search')"
        prepend-inner-icon="mdi-magnify"
        style="min-width: 220px; max-width: 360px"
        variant="outlined"
      />

      <v-select
        v-model="view.sort"
        density="compact"
        hide-details
        :items="SORTS.map(value => ({ value, title: t(`wishlist.sort.${value}`) }))"
        :label="t('collection.sortBy')"
        style="max-width: 240px"
        variant="outlined"
      />

      <v-btn-toggle
        density="comfortable"
        mandatory
        :model-value="tableView ? 'table' : 'cards'"
        variant="outlined"
        @update:model-value="value => setView(value === 'table')"
      >
        <v-btn icon="mdi-view-module-outline" :title="t('collection.viewCards')" value="cards" />
        <v-btn data-test="wish-table" icon="mdi-table-large" :title="t('collection.viewTable')" value="table" />
      </v-btn-toggle>

      <v-btn
        :icon="effectiveDir() === 'asc' ? 'mdi-sort-ascending' : 'mdi-sort-descending'"
        :title="t(effectiveDir() === 'asc' ? 'collection.sortAsc' : 'collection.sortDesc')"
        variant="text"
        @click="flipDir"
      />

      <v-spacer />

      <v-btn color="primary" prepend-icon="mdi-plus" @click="addOpen = true">
        {{ t('wishlist.add') }}
      </v-btn>
    </div>

    <div class="d-flex flex-wrap ga-2">
      <v-chip
        :color="view.reached ? 'primary' : undefined"
        :prepend-icon="view.reached ? 'mdi-check' : undefined"
        :variant="view.reached ? 'tonal' : 'outlined'"
        @click="view.reached = !view.reached"
      >{{ t('wishlist.filterReached') }}</v-chip>

      <v-chip
        :color="view.retired ? 'primary' : undefined"
        :prepend-icon="view.retired ? 'mdi-check' : undefined"
        :variant="view.retired ? 'tonal' : 'outlined'"
        @click="view.retired = !view.retired"
      >{{ t('wishlist.filterRetired') }}</v-chip>

      <v-chip
        :color="view.noPrice ? 'primary' : undefined"
        :prepend-icon="view.noPrice ? 'mdi-check' : undefined"
        :variant="view.noPrice ? 'tonal' : 'outlined'"
        @click="view.noPrice = !view.noPrice"
      >{{ t('wishlist.filterNoPrice') }}</v-chip>

      <!-- Séria ako ostatné čipy; zoznam sérií s počtom setov podľa ostatných filtrov. -->
      <v-menu :close-on-content-click="false" location="bottom start">
        <template #activator="{ props: menuProps }">
          <v-chip
            v-bind="menuProps"
            append-icon="mdi-menu-down"
            :color="view.themes.length > 0 ? 'primary' : undefined"
            data-test="theme-filter"
            :prepend-icon="view.themes.length > 0 ? 'mdi-check' : undefined"
            :variant="view.themes.length > 0 ? 'tonal' : 'outlined'"
          >{{ themeLabel }}</v-chip>
        </template>

        <v-list density="compact" max-height="360" min-width="240">
          <v-list-item
            v-if="view.themes.length > 0"
            prepend-icon="mdi-close"
            :title="t('wishlist.themeClear')"
            @click="view.themes = []"
          />

          <v-list-item
            v-for="option in themeOptions"
            :key="option.value"
            :title="themeName(option.value)"
            @click="toggleTheme(option.value)"
          >
            <template #prepend>
              <v-checkbox-btn :model-value="view.themes.includes(option.value)" tabindex="-1" />
            </template>

            <template #append>
              <span class="text-body-small text-medium-emphasis">{{ option.count }}</span>
            </template>
          </v-list-item>
        </v-list>
      </v-menu>
    </div>

    <v-alert
      v-if="error"
      closable
      type="error"
      variant="tonal"
      @click:close="error = null"
    >
      {{ error }}
    </v-alert>

    <!-- Kým server neodpovedal, kostra; prázdny stav až po odpovedi. -->
    <PageSkeleton v-if="page.initial" kind="cards" />

    <LoadFailed v-else-if="page.error" :loading="page.loading" @retry="page.run()" />

    <v-empty-state
      v-else-if="items.length === 0 && filtered()"
      icon="mdi-magnify"
      :title="t('wishlist.nothingMatches')"
    />

    <v-empty-state
      v-else-if="items.length === 0"
      icon="mdi-heart-outline"
      :text="t('wishlist.emptyHint')"
      :title="t('wishlist.empty')"
    />

    <v-card v-else-if="tableView" border class="wish-table" flat>
      <v-table density="comfortable" hover>
        <thead>
          <tr>
            <th class="wish-table__photo" />

            <th v-for="column in COLUMNS" :key="column.sort" :class="{ 'text-end': column.end }">
              <SortHeader
                :dir="headerDir(column.sort, { sort: view.sort, dir: view.dir }, defaultDir)"
                :title="t(column.title)"
                @sort="sortBy(column.sort)"
              />
            </th>

            <th />
          </tr>
        </thead>

        <tbody>
          <tr v-for="item in items" :key="item.id">
            <td class="wish-table__photo">
              <SetImage :alt="item.catalog.name" rounded="sm" :size="64" :src="imageSrc(item.catalog.image_url) ?? undefined" />
            </td>

            <td>
              <RouterLink class="wish-table__name" :to="{ name: 'set-detail', params: { num: item.catalog_num } }">
                {{ item.catalog.name }}
              </RouterLink>

              <div class="d-flex align-center flex-wrap ga-2 text-body-small text-medium-emphasis">
                {{ item.catalog.catalog_num }}
                <v-chip
                  v-if="item.target_reached"
                  color="positive"
                  label
                  size="x-small"
                  variant="flat"
                >{{ t('wishlist.reached') }}</v-chip>

                <v-chip
                  v-if="item.owned_count > 0"
                  color="primary"
                  label
                  size="x-small"
                  variant="tonal"
                >{{ t('wishlist.owned', { count: t('collection.pieces', { count: item.owned_count }) }) }}</v-chip>
              </div>
            </td>

            <td class="text-body-medium">{{ item.catalog.theme || '—' }}</td>

            <td class="text-end text-no-wrap" :class="{ 'text-positive': item.target_reached }">
              {{ item.market_price ? exactMoney(item.market_price) : '—' }}
              <div v-if="item.market_price && item.price_at" class="text-body-small text-medium-emphasis">
                {{ t('collection.priceAt', { date: shortDate(item.price_at) }) }}
              </div>
            </td>

            <td class="text-end text-no-wrap">
              <template v-if="item.target_price_eur">{{ exactMoney(item.target_price_eur) }}</template>

              <v-btn
                v-else
                class="px-0"
                size="small"
                variant="text"
                @click="openEdit(item)"
              >{{ t('wishlist.setTarget') }}</v-btn>
            </td>

            <td class="text-end text-no-wrap">
              <span
                v-if="item.distance_pct !== null && item.distance_pct !== undefined"
                class="font-weight-bold"
                :class="item.distance_pct <= 0 ? 'text-positive' : 'text-negative'"
              >{{ percent(item.distance_pct, { decimals: 0 }) }}</span>

              <template v-else>—</template>
            </td>

            <td class="text-end text-no-wrap">
              <v-btn
                color="primary"
                prepend-icon="mdi-cart-check"
                size="small"
                variant="flat"
                @click="openBuy(item)"
              >{{ t('purchase.bought') }}</v-btn>

              <v-btn
                icon="mdi-pencil-outline"
                size="small"
                :title="t('wishlist.edit')"
                variant="text"
                @click="openEdit(item)"
              />

              <v-btn
                color="negative"
                icon="mdi-delete-outline"
                size="small"
                variant="text"
                @click="remove(item)"
              />
            </td>
          </tr>
        </tbody>
      </v-table>
    </v-card>

    <CardGrid v-else>
      <v-card
        v-for="item in items"
        :key="item.id"
        border
        class="h-100 d-flex flex-column"
        flat
      >
        <div class="position-relative">
          <SetImage :alt="item.catalog.name" rounded="0" :size="132" :src="imageSrc(item.catalog.image_url) ?? undefined" />

          <PhotoZoom
            v-if="item.catalog.image_url"
            :image-url="item.catalog.image_url"
            :name="item.catalog.name"
            :num="item.catalog.catalog_num"
          />

          <!-- Cena klesla na cieľ: to je dôvod, prečo tu set vôbec je. -->
          <v-chip
            v-if="item.target_reached"
            class="wish-reached"
            color="positive"
            label
            prepend-icon="mdi-bell-ring-outline"
            size="small"
            variant="flat"
          >{{ t('wishlist.reached') }}</v-chip>
        </div>

        <div class="pa-3 d-flex flex-column ga-1 flex-grow-1">
          <div class="text-body-large font-weight-medium text-truncate">{{ item.catalog.name }}</div>

          <div class="text-body-small text-medium-emphasis">
            {{ item.catalog.catalog_num }}
            <span v-if="item.catalog.theme"> · {{ item.catalog.theme }}</span>

            <span v-if="item.catalog.num_parts">
              · {{ t('collection.partsPlural', item.catalog.num_parts, { named: { count: count(item.catalog.num_parts) } }) }}
            </span>
          </div>

          <v-chip
            v-if="item.owned_count > 0"
            class="align-self-start"
            color="primary"
            label
            prepend-icon="mdi-check-circle-outline"
            size="small"
            variant="tonal"
          >{{ t('wishlist.owned', { count: t('collection.pieces', { count: item.owned_count }) }) }}</v-chip>

          <div class="d-flex ga-4 mt-1">
            <div v-if="item.market_price">
              <div class="text-body-small text-medium-emphasis">{{ t('wishlist.marketNow') }}</div>

              <div
                class="text-body-medium font-weight-medium"
                :class="{ 'text-positive': item.target_reached }"
              >{{ exactMoney(item.market_price) }}</div>

              <div v-if="item.price_at" class="text-body-small text-medium-emphasis text-no-wrap">
                {{ t('collection.priceAt', { date: shortDate(item.price_at) }) }}
              </div>
            </div>

            <div v-if="item.target_price_eur">
              <div class="text-body-small text-medium-emphasis">{{ t('wishlist.target') }}</div>
              <div class="text-body-medium">{{ exactMoney(item.target_price_eur) }}</div>
            </div>

            <div v-else>
              <div class="text-body-small text-medium-emphasis">{{ t('wishlist.target') }}</div>
              <v-btn class="px-0" size="small" variant="text" @click="openEdit(item)">{{ t('wishlist.setTarget') }}</v-btn>
            </div>

            <div v-if="item.distance_pct !== null && item.distance_pct !== undefined">
              <div class="text-body-small text-medium-emphasis">{{ t('wishlist.distance') }}</div>

              <!-- Nad cieľom červené, na cieli a pod ním zelené. -->
              <div class="text-body-medium font-weight-bold" :class="item.distance_pct <= 0 ? 'text-positive' : 'text-negative'">
                {{ percent(item.distance_pct, { decimals: 0 }) }}
              </div>
            </div>
          </div>

          <div class="d-flex align-center flex-wrap ga-1 mt-auto pt-2">
            <!-- Hlavná akcia: kúpené sa pridá bez hľadania čísla a z Chcem zmizne. -->
            <v-btn
              color="primary"
              prepend-icon="mdi-cart-check"
              size="small"
              variant="flat"
              @click="openBuy(item)"
            >{{ t('purchase.bought') }}</v-btn>

            <v-btn
              size="small"
              :to="{ name: 'set-detail', params: { num: item.catalog_num } }"
              variant="text"
            >{{ t('wishlist.currentPrice') }}</v-btn>

            <!-- Úprava a zmazanie spolu vpravo; lámu sa len ako celok. -->
            <div class="d-flex flex-nowrap ms-auto">
              <v-btn
                icon="mdi-pencil-outline"
                size="small"
                :title="t('wishlist.edit')"
                variant="text"
                @click="openEdit(item)"
              />

              <v-btn
                color="negative"
                icon="mdi-delete-outline"
                size="small"
                variant="text"
                @click="remove(item)"
              />
            </div>
          </div>
        </div>
      </v-card>
    </CardGrid>

    <v-dialog v-model="editOpen" max-width="420">
      <v-card v-if="editing" :subtitle="editing.catalog_num" :title="editing.catalog.name">
        <v-card-text class="d-flex flex-column ga-3">
          <v-text-field
            v-model="editTarget"
            autofocus
            clearable
            :hint="t('wishlist.targetHint')"
            inputmode="decimal"
            :label="t('wishlist.target')"
            persistent-hint
            suffix="€"
            @keyup.enter="saveEdit"
          />

          <v-textarea v-model="editNote" auto-grow :label="t('wishlist.note')" rows="2" />
        </v-card-text>

        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="editOpen = false">{{ t('common.cancel') }}</v-btn>
          <v-btn color="primary" :loading="saving" variant="flat" @click="saveEdit">{{ t('common.save') }}</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="addOpen" max-width="420">
      <v-card>
        <v-card-title>{{ t('wishlist.add') }}</v-card-title>

        <v-card-text class="d-flex flex-column ga-3">
          <!-- Riadok pod poľom má miesto vždy (details), upozornenie dialóg neposunie. -->
          <v-text-field
            v-model="newNumber"
            autofocus
            :label="t('add.setNumber')"
            :messages="ownedHint ? [ownedHint] : []"
          >
            <template #message="{ message }">
              <span class="owned-hint d-inline-flex align-center ga-1">
                <v-icon icon="mdi-alert-circle-outline" size="small" />{{ message }}
              </span>
            </template>
          </v-text-field>

          <v-text-field v-model="targetPrice" :label="t('wishlist.targetPrice')" prefix="€" type="number" />
        </v-card-text>

        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="addOpen = false">{{ t('common.cancel') }}</v-btn>

          <v-btn color="primary" :loading="saving" variant="flat" @click="add">
            {{ t('wishlist.add') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <PurchaseDialog
      v-model="buyOpen"
      :catalog="buying?.catalog ?? null"
      :wishlist-id="buying?.id ?? null"
      @saved="afterPurchase"
    />
  </div>
</template>

<style scoped>
.wish-reached {
  left: 8px;
  position: absolute;
  top: 8px;
}

.owned-hint {
  color: rgb(var(--v-theme-warning));
}

/* Tabuľka Chcem: na telefóne sa posúva do strany, stránka nie. */
.wish-table {
  overflow-x: auto;
}

.wish-table__photo {
  width: 104px;
  padding-top: 6px !important;
  padding-bottom: 6px !important;
}

.wish-table__name {
  color: inherit;
  font-weight: 500;
  text-decoration: none;
}

.wish-table__name:hover {
  text-decoration: underline;
}
</style>
