<script setup lang="ts">
  /**
   * Zoznam želaných setov s ich aktuálnou trhovou cenou.
   *
   * Radí a filtruje server (`GET /wishlist?sort=&dir=&q=&reached=…`),
   * rovnako ako Zbierka; predvolene najbližšie k cieľovej cene navrch.
   */
  import type { WishlistItem } from '@/api/types'
  import { useDebounceFn } from '@vueuse/core'
  import { onMounted, reactive, ref, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { api, errorMessage } from '@/api/client'
  import CardGrid from '@/components/CardGrid.vue'
  import KeyHint from '@/components/KeyHint.vue'
  import PurchaseDialog from '@/components/PurchaseDialog.vue'
  import SetImage from '@/components/SetImage.vue'
  import { useAuthStore } from '@/stores/auth'
  import { useCollectionStore } from '@/stores/collection'
  import { useNotifyStore } from '@/stores/notify'
  import { count, exactMoney, percent, toNumber } from '@/utils/format'
  import { imageSrc } from '@/utils/imageSrc'
  import { priceValue } from '@/utils/priceEdit'
  import { hasWishFilter, wishlistQuery } from '@/utils/wishlistQuery'

  const { t } = useI18n()
  const auth = useAuthStore()
  const notify = useNotifyStore()
  const collection = useCollectionStore()

  const items = ref<WishlistItem[]>([])
  const loading = ref(true)
  const error = ref<string | null>(null)
  const addOpen = ref(false)
  const newNumber = ref('')
  const targetPrice = ref('')
  const saving = ref(false)
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
  })
  const effectiveDir = (): 'asc' | 'desc' => view.dir ?? DEFAULT_DIR[view.sort]

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
    await load()
  }

  function openBuy (item: WishlistItem): void {
    buying.value = item
    buyOpen.value = true
  }

  async function load (): Promise<void> {
    loading.value = true
    const { data } = await api.GET('/wishlist', { params: { query: wishlistQuery(view) as never } })
    items.value = data ?? []
    loading.value = false
  }

  const reload = useDebounceFn(load, 250)
  watch(() => ({ ...view }), reload, { deep: true })
  // Chcem mení aj pridanie kusu inde alebo Späť v oznámení; počet v súhrne
  // (ponuka) sa po nich obnoví a prezradí to.
  watch(() => collection.summary?.wishlist_count, (now, before) => {
    if (before !== undefined && now !== before) reload()
  })

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
    await load()
  }

  async function remove (item: WishlistItem): Promise<void> {
    const { error: err } = await api.DELETE('/wishlist/{item_id}', { params: { path: { item_id: item.id } } })
    if (err) {
      notify.error(err, t('notice.wishFailed'))
      return
    }
    notify.success(t('notice.wishRemoved', { name: item.catalog.name }))
    await load()
  }

  onMounted(load)
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

    <v-progress-linear v-if="loading" color="primary" indeterminate />

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
            <span v-if="item.catalog.num_parts"> · {{ count(item.catalog.num_parts) }} dielikov</span>
          </div>

          <div class="d-flex ga-4 mt-1">
            <div v-if="item.market_price">
              <div class="text-body-small text-medium-emphasis">{{ t('wishlist.marketNow') }}</div>

              <div
                class="text-body-medium font-weight-medium"
                :class="{ 'text-positive': item.target_reached }"
              >{{ exactMoney(item.market_price) }}</div>
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
          <v-text-field v-model="newNumber" autofocus :label="t('add.setNumber')" />
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
      @saved="load"
    />
  </div>
</template>

<style scoped>
.wish-reached {
  left: 8px;
  position: absolute;
  top: 8px;
}
</style>
