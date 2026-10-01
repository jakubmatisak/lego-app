<script setup lang="ts">
  /**
   * Karta jedného setu v Zbierke. Predaná karta je vizuálne odlíšená
   * a namiesto trhovej hodnoty ukazuje, za koľko sa predala.
   */
  import type { GroupedItem } from '@/api/types'
  import { computed } from 'vue'
  import { useI18n } from 'vue-i18n'
  import PhotoZoom from '@/components/PhotoZoom.vue'
  import SetImage from '@/components/SetImage.vue'
  import { useFilterStore } from '@/stores/filters'
  import { count, exactMoney, money, percent, shortDate } from '@/utils/format'
  import { imageSrc } from '@/utils/imageSrc'

  const props = defineProps<{
    row: GroupedItem
    sold?: boolean
    /** Režim výberu: klik kartu označí namiesto otvorenia detailu. */
    selectable?: boolean
    selected?: boolean
  }>()
  const emit = defineEmits<{ toggle: [num: string] }>()

  const { t } = useI18n()

  const meta = computed(() => {
    const parts: string[] = [props.row.catalog.catalog_num]
    if (props.row.catalog.theme) parts.push(props.row.catalog.theme)
    if (props.row.catalog.num_parts) {
      const n = props.row.catalog.num_parts
      parts.push(t('collection.partsPlural', n, { named: { count: count(n) } }))
    }
    return parts.join(' · ')
  })

  const locationLabel = computed(() => {
    const locations = props.row.locations
    if (locations.length === 0) return null
    if (locations.length === 1) return locations[0]
    return t('collection.twoPlaces', { count: locations.length })
  })

  const conditionLabel = computed(() => {
    const entries = Object.entries(props.row.conditions)
    if (entries.length === 0) return null
    if (entries.length === 1) return t(`condition.${entries[0][0]}`)
    return entries.map(([key, n]) => `${n}× ${t(`condition.${key}`).toLowerCase()}`).join(', ')
  })

  const profitPct = computed(() => props.row.unrealized_pct)

  /** Aspoň jeden kus nemá trhovú cenu, takže zisk by bol nezmyselný. */
  const filterStore = useFilterStore()

  /** Najviac dve kategórie, zvyšok ako „+n“, nech karta nepretečie. */
  const categoryChips = computed(() => {
    const all = (props.row.categories ?? [])
      .map(id => filterStore.categoryById.get(id))
      .filter(c => c !== undefined)
    return { shown: all.slice(0, 2), more: Math.max(0, all.length - 2) }
  })

  const priceUnknown = computed(() => (props.row.price_missing ?? 0) > 0)
  /**
   * Hodnota je odvodená z ceny pre druhý stav, lebo pre ten správny ju
   * zdroj nemá. Označíme ju, nech sa nevydáva za presnú.
   */
  const priceApprox = computed(() => (props.row.price_approx ?? 0) > 0)
</script>

<template>
  <v-card
    border
    class="set-card d-flex flex-column h-100"
    :class="{ 'set-card--sold': sold, 'set-card--selected': selected }"
    flat
    :to="selectable ? undefined : { name: 'set-detail', params: { num: row.catalog.catalog_num } }"
    @click="selectable && emit('toggle', row.catalog.catalog_num)"
  >
    <div class="position-relative">
      <v-icon
        v-if="selectable"
        class="set-card__check"
        :color="selected ? 'primary' : undefined"
        :icon="selected ? 'mdi-checkbox-marked' : 'mdi-checkbox-blank-outline'"
      />

      <SetImage :alt="row.catalog.name" rounded="0" :size="132" :src="imageSrc(row.catalog.image_url) ?? undefined" />

      <PhotoZoom
        v-if="row.catalog.image_url"
        :image-url="row.catalog.image_url"
        :name="row.catalog.name"
        :num="row.catalog.catalog_num"
      />

      <v-chip
        v-if="(sold ? row.sold_quantity : row.quantity) > 1"
        class="set-card__badge set-card__badge--left"
        color="primary"
        label
        size="small"
        variant="flat"
      >{{ t('collection.pieces', { count: sold ? row.sold_quantity : row.quantity }) }}</v-chip>

      <v-chip
        v-if="sold"
        class="set-card__badge set-card__badge--right"
        label
        prepend-icon="mdi-check"
        size="small"
        variant="flat"
      >{{ t('collection.status.sold') }}</v-chip>

      <v-chip
        v-else-if="row.catalog.is_retired"
        class="set-card__badge set-card__badge--right"
        color="secondary"
        label
        size="small"
        variant="flat"
      >{{ t('detail.retiredShort') }}</v-chip>
    </div>

    <div class="pa-3 d-flex flex-column ga-2 flex-grow-1">
      <div>
        <div class="text-body-large font-weight-medium text-truncate">{{ row.catalog.name }}</div>
        <div class="text-body-small text-medium-emphasis text-truncate">{{ meta }}</div>
      </div>

      <div class="d-flex flex-wrap ga-1">
        <v-chip
          v-for="category in categoryChips.shown"
          :key="category.id"
          label
          size="x-small"
          variant="outlined"
        >
          <span class="card-cat-dot me-1" :class="`bg-${category.color ?? 'grey'}`" />{{ category.name }}
        </v-chip>

        <v-chip v-if="categoryChips.more" label size="x-small" variant="outlined">+{{ categoryChips.more }}</v-chip>

        <v-chip v-if="conditionLabel" label size="x-small" variant="tonal">{{ conditionLabel }}</v-chip>

        <!-- Z kontroly úplnosti v detaile setu (bez náhradných dielikov). -->
        <v-chip
          v-if="!sold && (row.missing_parts ?? 0) > 0"
          color="warning"
          data-test="card-missing-parts"
          label
          prepend-icon="mdi-puzzle-remove-outline"
          size="x-small"
          variant="tonal"
        >{{ t('parts.missingPlural', row.missing_parts, { named: { count: row.missing_parts } }) }}</v-chip>

        <v-chip
          v-if="locationLabel"
          label
          prepend-icon="mdi-map-marker-outline"
          size="x-small"
          variant="tonal"
        >{{ locationLabel }}</v-chip>
      </div>

      <div class="d-flex align-end ga-2 mt-auto">
        <div class="d-flex flex-column">
          <span class="text-body-small text-medium-emphasis">{{ t('collection.purchased') }}</span>

          <span class="text-body-medium">
            {{ exactMoney(row.purchase_total) }}
            <v-icon
              v-if="row.purchase_auto"
              icon="mdi-auto-fix"
              size="x-small"
              :title="t('purchaseAuto.cardHint', { count: row.purchase_auto })"
            />
          </span>
        </div>

        <v-icon class="mb-1" color="medium-emphasis" icon="mdi-arrow-right" size="16" />

        <div class="d-flex flex-column">
          <span class="text-body-small text-medium-emphasis">
            {{ sold ? t('collection.soldFor') : t('collection.value') }}
          </span>
          <!-- Bez trhovej ceny nemá zmysel ukazovať hodnotu ani percento. -->
          <!-- Na úzkej karte sa to nesmie zlomiť do troch riadkov. Cenu doplníš v detaile. -->
          <span
            v-if="!sold && priceUnknown"
            class="text-body-medium text-medium-emphasis text-no-wrap"
          >{{ t('collection.unknownPrice') }}</span>

          <span
            v-else
            class="text-body-large font-weight-medium"
            :title="!sold && priceApprox ? t('collection.approxPriceHint') : undefined"
          >
            <span v-if="!sold && priceApprox" class="text-medium-emphasis">≈ </span>
            {{ exactMoney(sold ? row.sold_total : row.market_total) }}
          </span>

          <!-- Kedy bola cena stiahnutá; ručná cena a predaj čas nemajú. -->
          <span v-if="!sold && row.price_at" class="text-body-small text-medium-emphasis text-no-wrap">
            {{ t('collection.priceAt', { date: shortDate(row.price_at) }) }}
          </span>
        </div>

        <v-chip
          v-if="sold"
          class="ms-auto"
          :color="Number(row.realized) >= 0 ? 'positive' : 'negative'"
          label
          size="small"
          variant="tonal"
        >{{ money(row.realized, { sign: true, decimals: 0 }) }}</v-chip>

        <v-chip
          v-else-if="profitPct !== null && profitPct !== undefined"
          class="ms-auto"
          :color="profitPct >= 0 ? 'positive' : 'negative'"
          label
          size="small"
          variant="tonal"
        >{{ percent(profitPct, { decimals: 0 }) }}</v-chip>
      </div>
    </div>
  </v-card>
</template>

<style scoped>
  .set-card--selected {
    outline: 2px solid rgb(var(--v-theme-primary));
  }

  .set-card__check {
    position: absolute;
    right: 8px;
    bottom: 8px;
    z-index: 1;
    background: rgb(var(--v-theme-surface));
    border-radius: 4px;
  }

.set-card--sold {
  border-style: dashed !important;
  background: rgb(var(--v-theme-surface-variant));
}

.set-card--sold .text-body-large {
  color: rgb(var(--v-theme-on-surface-variant));
}

.set-card__badge {
  position: absolute;
  top: 8px;
}

.set-card__badge--left {
  left: 8px;
}

.set-card__badge--right {
  right: 8px;
}

.card-cat-dot {
  border-radius: 50%;
  display: inline-block;
  height: 7px;
  width: 7px;
}
</style>
