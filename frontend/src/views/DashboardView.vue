<script setup lang="ts">
/**
 * Prehľad. Nerealizovaný a realizovaný zisk stoja vedľa seba ako dve
 * samostatné čísla a nikde sa nesčítavajú do jedného.
 */
  import type { Scope } from '@/utils/scope'
  import { computed, onMounted } from 'vue'
  import { useI18n } from 'vue-i18n'

  import BreakdownCard from '@/components/BreakdownCard.vue'
  import ForecastCard from '@/components/ForecastCard.vue'
  import PortfolioCard from '@/components/PortfolioCard.vue'
  import PriceMovers from '@/components/PriceMovers.vue'
  import SalesCard from '@/components/SalesCard.vue'
  import ScopePicker from '@/components/ScopePicker.vue'
  import SeriesProgress from '@/components/SeriesProgress.vue'
  import SetImage from '@/components/SetImage.vue'
  import StatTile from '@/components/StatTile.vue'
  import ThemeDonut from '@/components/ThemeDonut.vue'
  import UnlockCard from '@/components/UnlockCard.vue'
  import { useAuthStore } from '@/stores/auth'
  import { useCollectionStore } from '@/stores/collection'
  import { useFilterStore } from '@/stores/filters'
  import { useNotifyStore } from '@/stores/notify'
  import { useProfileStore } from '@/stores/preferences'
  import { count, exactMoney, money, percent } from '@/utils/format'
  import { imageSrc } from '@/utils/imageSrc'
  import { refreshScope, restoreScope } from '@/utils/scope'

  const { t } = useI18n()
  const collection = useCollectionStore()
  const hasSeries = computed(() => collection.series.length > 0)
  const auth = useAuthStore()
  const profile = useProfileStore()
  const filters = useFilterStore()
  const notify = useNotifyStore()

  const summary = computed(() => collection.dashboardSummary)
  // Prázdna je zbierka, nie rozsah: rozsah bez kusov ukáže nuly, nie „pridaj prvý set“.
  const isEmpty = computed(() => (collection.summary?.item_count ?? 0) === 0 && (collection.summary?.sold_count ?? 0) === 0)

  const discountHint = computed(() => {
    const s = summary.value
    if (!s || s.avg_discount_pct === null || s.avg_discount_pct === undefined) {
      return t('dashboard.noDiscountData')
    }
    return t('dashboard.avgDiscount', {
      value: percent(s.avg_discount_pct, { decimals: 0, sign: false }),
    })
  })

  /** Ročný výnos zbierky. Pri kusoch držaných kratšie než rok sa nepočíta. */
  const cagrHint = computed(() => {
    const s = summary.value
    if (!s || s.cagr_pct === null || s.cagr_pct === undefined) return t('insights.cagrTooShort')
    return t('insights.cagrHint', {
      value: percent(s.cagr_pct, { decimals: 1 }),
      count: s.cagr_sample,
    })
  })

  /** Bez zdroja cien a bez ručných cien nie je čo ukázať: dlaždice hodnoty odpadnú. */
  const showMarket = computed(() =>
    auth.can('brickeconomy.prices') || Number(summary.value?.market_value ?? 0) > 0,
  )

  /** Farba zisku. Keď cenu nemá ani jeden kus, zisk je null: pomlčka bez farby. */
  const unrealizedColor = computed(() => {
    const value = summary.value?.unrealized
    if (value === null || value === undefined) return null
    return Number(value) >= 0 ? 'positive' : 'negative'
  })

  /**
   * Podnadpis dlaždice Zbierka. Hlavné číslo sú sety sekcie Zbierka, figúrky
   * zo sérií a nerozbalené sáčky stoja tu, rovnako ako v ponuke a vo
   * Figúrkach; kusy a dieliky sú za všetko. Nulové počty vynechá.
   */
  const collectionHint = computed(() => {
    const s = summary.value
    if (!s) return ''
    const pieces = t('collection.piecesPlural', s.item_count, { named: { count: s.item_count } })
    return [
      s.series_figures ? t('dashboard.figuresPlural', s.series_figures, { named: { count: s.series_figures } }) : '',
      s.sealed_bag_count ? t('dashboard.bagsPlural', s.sealed_bag_count, { named: { count: s.sealed_bag_count } }) : '',
      t('dashboard.piecesAndParts', { pieces, parts: count(s.parts) }),
    ].filter(Boolean).join(' · ')
  })

  const valueHint = computed(() =>
    auth.hasPriceKey ? t('dashboard.priceSource') : t('dashboard.manualPrices'),
  )

  onMounted(async () => {
    // Rozsah si pamätá účet; načíta sa pred štatistikami, nech sa neťahajú dvakrát.
    await Promise.all([
      profile.load(),
      filters.views.length > 0 ? null : filters.loadViews(),
      filters.categories.length > 0 ? null : filters.loadCategories(),
    ])
    const saved = restoreScope(profile.get('dashboard')?.scope)
    // Pohľad alebo kategória sa mohli premenovať, zmeniť alebo zmazať.
    const next = refreshScope(saved, filters.views, filters.categories)
    if (saved && !next) notify.info(t('scope.removed', { label: saved.label }))
    if (JSON.stringify(next) !== JSON.stringify(saved)) {
      profile.save('dashboard', next ? { scope: next } : {})
    }
    // Rovnaký rozsah ako doteraz: nový objekt by karty prinútil načítať znova.
    if (JSON.stringify(next) !== JSON.stringify(collection.scope)) collection.scope = next
    collection.loadDashboard()
  })

  function setScope (next: Scope | null): void {
    collection.scope = next
    profile.save('dashboard', next ? { scope: next } : {})
    collection.loadDashboard()
  }
</script>

<template>
  <UnlockCard class="mb-4" />

  <div v-if="collection.loading && !summary" class="d-flex justify-center pa-12">
    <v-progress-circular color="primary" indeterminate />
  </div>

  <v-empty-state
    v-else-if="isEmpty"
    :action-text="t('collection.addSet')"
    icon="mdi-toy-brick-outline"
    :text="t('dashboard.emptyHint')"
    :title="t('dashboard.empty')"
    @click:action="$router.push({ name: 'add-set' })"
  />

  <div v-else-if="summary" class="d-flex flex-column ga-5">
    <ScopePicker :scope="collection.scope" @update="setScope" />

    <v-row dense>
      <v-col cols="12" lg="" md="4" sm="6">
        <StatTile
          :hint="discountHint"
          :label="t('dashboard.invested')"
          :value="money(summary.invested, { decimals: 0 })"
        />
      </v-col>

      <v-col
        v-if="showMarket"
        cols="12"
        lg=""
        md="4"
        sm="6"
      >
        <StatTile
          :hint="valueHint"
          :label="t('dashboard.marketValue')"
          :value="money(summary.market_value, { decimals: 0 })"
        />
      </v-col>

      <v-col
        v-if="showMarket"
        cols="12"
        lg=""
        md="4"
        sm="6"
      >
        <StatTile
          :chip="summary.unrealized_pct === null ? null : percent(summary.unrealized_pct)"
          :chip-color="unrealizedColor"
          :color="unrealizedColor"
          :hint="cagrHint"
          :label="t('dashboard.unrealized')"
          :value="money(summary.unrealized, { sign: true, decimals: 0 })"
        />
      </v-col>

      <v-col cols="12" lg="" md="6" sm="6">
        <StatTile
          color="positive"
          :hint="t('dashboard.soldSummary', {
            sold: t('collection.soldPlural', summary.sold_count, { named: { count: summary.sold_count } }),
            total: money(summary.sold_proceeds, { decimals: 0 }),
          })"
          :label="t('dashboard.realized')"
          :value="money(summary.realized, { sign: true, decimals: 0 })"
        />
      </v-col>

      <v-col cols="12" lg="" md="6" sm="6">
        <StatTile
          :hint="collectionHint"
          :label="t('dashboard.collection')"
          :value="t('collection.setsPlural', summary.collection_set_count, { named: { count: summary.collection_set_count } })"
        />
      </v-col>
    </v-row>

    <v-alert
      v-if="summary.price_missing > 0"
      density="comfortable"
      icon="mdi-help-circle-outline"
      variant="tonal"
    >
      {{ t('dashboard.priceMissingPlural', summary.price_missing, { named: { count: summary.price_missing } }) }}
    </v-alert>

    <v-row dense>
      <v-col v-if="showMarket" cols="12" lg="8">
        <PortfolioCard :weekly="collection.timeline" />
      </v-col>

      <v-col cols="12" :lg="showMarket ? 4 : 12">
        <v-card border class="pa-4 h-100" flat>
          <div class="text-h6 mb-3">{{ t('dashboard.themes') }}</div>
          <ThemeDonut :themes="summary.themes" />
        </v-card>
      </v-col>
    </v-row>

    <v-row dense>
      <v-col cols="12" :lg="showMarket ? 8 : 12">
        <BreakdownCard />
      </v-col>

      <v-col v-if="showMarket" cols="12" lg="4">
        <ForecastCard :summary="summary" />
      </v-col>
    </v-row>

    <!-- Tri rovnako vysoké stĺpce; bez sérií sa dva zvyšné rozdelia na polovicu. -->
    <v-row dense>
      <v-col v-if="showMarket" cols="12" :lg="hasSeries ? 4 : 6" md="6">
        <v-card border class="h-100" flat>
          <v-card-item>
            <div class="d-flex align-center">
              <v-card-title class="text-h6 pa-0">{{ t('dashboard.topProfit') }}</v-card-title>

              <v-btn
                class="ms-auto"
                size="small"
                :to="{ name: 'collection' }"
                variant="text"
              >{{ t('dashboard.wholeCollection') }}</v-btn>
            </div>
          </v-card-item>

          <!-- Kusy bez ceny server preskočí; bez jediného oceneného by karta ostala prázdna. -->
          <v-card-text v-if="summary.top_profit.length === 0" class="text-body-2 text-medium-emphasis pt-0">
            {{ t('dashboard.topProfitEmpty') }}
          </v-card-text>

          <v-list v-else density="comfortable" lines="two">
            <v-list-item
              v-for="row in summary.top_profit"
              :key="row.catalog_num"
              :to="{ name: 'set-detail', params: { num: row.catalog_num } }"
            >
              <template #prepend>
                <SetImage
                  class="me-3"
                  rounded="md"
                  :size="40"
                  :src="imageSrc(row.image_url) ?? undefined"
                  style="width: 40px"
                />
              </template>

              <v-list-item-title class="font-weight-medium">{{ row.name }}</v-list-item-title>

              <v-list-item-subtitle class="text-caption">
                {{ row.catalog_num }} · {{ row.theme }} · {{ t('collection.pieces', { count: row.quantity }) }}
              </v-list-item-subtitle>

              <template #append>
                <div class="text-end">
                  <div class="text-body-2 font-weight-medium">{{ exactMoney(row.market_value) }}</div>

                  <div
                    class="text-caption font-weight-medium"
                    :class="Number(row.profit) >= 0 ? 'text-positive' : 'text-negative'"
                  >
                    {{ money(row.profit, { sign: true, decimals: 0 }) }}
                    <span v-if="row.profit_pct !== null"> · {{ percent(row.profit_pct, { decimals: 0 }) }}</span>
                  </div>
                </div>
              </template>
            </v-list-item>
          </v-list>
        </v-card>
      </v-col>

      <v-col v-if="showMarket" cols="12" :lg="hasSeries ? 4 : 6" md="6">
        <PriceMovers :movers="collection.movers" @window="collection.loadMovers" />
      </v-col>

      <v-col v-if="hasSeries" cols="12" :lg="showMarket ? 4 : 12">
        <SeriesProgress :series="collection.series" />
      </v-col>
    </v-row>

    <SalesCard v-if="summary.sold_count > 0" />
  </div>
</template>
