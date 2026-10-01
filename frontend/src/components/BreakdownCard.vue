<script setup lang="ts">
/**
 * Výkonnosť vlastnených kusov podľa témy, podtémy alebo zoznamu.
 * Počíta sa z uložených cien, zdroj cien sa tu nevolá. Skupina, v ktorej
 * cenu nemá ani jeden kus, príde s hodnotou null a ukáže pomlčku, nie 0 €.
 * Radí sa klikom na hlavičku, na klientovi; prázdna hodnota (skupina bez
 * ceny, zisk pri chýbajúcej cene, bez témy) je na konci v oboch smeroch.
 */
  import type { BreakdownRow } from '@/api/types'
  import type { SortDir, SortState, SortValue } from '@/utils/tableSort'
  import { computed, onMounted, ref, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { api } from '@/api/client'
  import SortHeader from '@/components/SortHeader.vue'
  import { onPageReload } from '@/composables/usePageLoad'
  import { useCollectionStore } from '@/stores/collection'
  import { money, percent, toNumber } from '@/utils/format'
  import { headerDir, nextSort, sortRows } from '@/utils/tableSort'

  type By = 'theme' | 'subtheme' | 'purpose'

  const { t } = useI18n()
  const by = ref<By>('theme')
  const rows = ref<BreakdownRow[]>([])
  const loading = ref(false)
  const collection = useCollectionStore()

  async function load (): Promise<void> {
    loading.value = true
    const { data } = await api.GET('/stats/breakdown', {
      params: { query: { by: by.value, ...collection.statsQuery() } },
    })
    rows.value = data ?? []
    loading.value = false
  }

  watch(() => [collection.real, collection.scope], load)

  function label (row: BreakdownRow): string {
    if (by.value === 'purpose') {
      return row.key ? t(`purpose.${row.key}`) : t('purpose.none')
    }
    return row.label
  }

  type Column = 'label' | 'pieces' | 'invested' | 'value' | 'profit' | 'yearly'

  /** Hodnota stĺpca na zoradenie; null = pomlčka v bunke, ide na koniec. */
  const VALUES: Record<Column, (row: BreakdownRow) => SortValue> = {
    // Skupina bez témy či zoznamu je na konci aj pri názve.
    label: row => (row.key === null ? null : label(row)),
    pieces: row => row.pieces,
    invested: row => toNumber(row.invested),
    value: row => toNumber(row.market_value),
    // Bez ceny časti kusov by zisk vyšiel voči nule, bunka má pomlčku.
    profit: row => (row.price_missing > 0 ? null : toNumber(row.unrealized)),
    yearly: row => row.cagr_pct,
  }
  const COLUMNS: Column[] = ['label', 'pieces', 'invested', 'value', 'profit', 'yearly']
  const TITLES: Record<Exclude<Column, 'label'>, string> = {
    pieces: 'insights.colPieces',
    invested: 'insights.colInvested',
    value: 'insights.colValue',
    profit: 'insights.colProfit',
    yearly: 'insights.colYearly',
  }
  const BY_TITLES: Record<By, string> = { theme: 'insights.byTheme', subtheme: 'insights.bySubtheme', purpose: 'insights.byPurpose' }
  function title (column: Column): string {
    return t(column === 'label' ? BY_TITLES[by.value] : TITLES[column])
  }

  const defaultDir = (column: Column): SortDir => (column === 'label' ? 'asc' : 'desc')
  /** Predvolene podľa hodnoty, ako posiela server. Pamätá sa len kým je stránka otvorená. */
  const order = ref<SortState<Column>>({ sort: 'value', dir: null })
  const sorted = computed(() =>
    sortRows(rows.value, VALUES[order.value.sort], order.value.dir ?? defaultDir(order.value.sort)),
  )

  /** Podtémy prichádzajú až s obnovou cien, dovtedy sú skoro všetky prázdne. */
  const subthemesMissing = computed(() =>
    by.value === 'subtheme' && rows.value.some(r => r.key === null),
  )

  function profitClass (row: BreakdownRow): string {
    if (row.price_missing > 0) return 'text-medium-emphasis'
    return Number(row.unrealized) >= 0 ? 'text-positive' : 'text-negative'
  }

  watch(by, load)
  onMounted(load)
  // Tlačidlo Obnoviť stránku v hornej lište.
  onPageReload(load)
</script>

<template>
  <v-card border class="h-100" flat>
    <v-card-item>
      <div class="d-flex align-center ga-3 flex-wrap">
        <v-card-title class="text-title-large font-weight-medium pa-0">{{ t('insights.breakdownTitle') }}</v-card-title>

        <v-btn-toggle
          v-model="by"
          class="ms-auto"
          density="compact"
          mandatory
          variant="outlined"
        >
          <v-btn size="small" value="theme">{{ t('insights.byTheme') }}</v-btn>
          <v-btn size="small" value="subtheme">{{ t('insights.bySubtheme') }}</v-btn>
          <v-btn size="small" value="purpose">{{ t('insights.byPurpose') }}</v-btn>
        </v-btn-toggle>
      </div>
    </v-card-item>

    <div class="breakdown-scroll">
      <v-table density="comfortable" fixed-header>
        <thead>
          <tr>
            <th v-for="column in COLUMNS" :key="column" :class="{ 'text-end': column !== 'label' }">
              <SortHeader
                :dir="headerDir(column, order, defaultDir)"
                :title="title(column)"
                @sort="order = nextSort(column, order, defaultDir)"
              />
            </th>
          </tr>
        </thead>

        <tbody>
          <tr v-for="row in sorted" :key="row.key ?? '_'">
            <td class="font-weight-medium">{{ label(row) }}</td>
            <td class="text-end">{{ row.pieces }}</td>
            <td class="text-end">{{ money(row.invested) }}</td>

            <td class="text-end">
              {{ money(row.market_value) }}
              <!-- Hodnota je len z ocenených kusov; koľko cenu nemá, povie poznámka. -->
              <div
                v-if="row.price_missing > 0 && row.market_value !== null"
                class="text-body-small text-medium-emphasis"
              >{{ t('totals.noPrice', { count: row.price_missing }) }}</div>
            </td>

            <!-- Bez ceny časti kusov by zisk vyšiel voči nule, preto pomlčka. -->
            <td class="text-end font-weight-medium" :class="profitClass(row)">
              <template v-if="row.price_missing > 0">—</template>

              <template v-else>
                {{ money(row.unrealized, { sign: true }) }}
                <span v-if="row.unrealized_pct !== null" class="text-body-small">
                  · {{ percent(row.unrealized_pct, { decimals: 0 }) }}
                </span>
              </template>
            </td>

            <td
              class="text-end"
              :class="row.cagr_pct === null ? 'text-medium-emphasis' : row.cagr_pct >= 0 ? 'text-positive' : 'text-negative'"
            >{{ row.cagr_pct === null ? '—' : percent(row.cagr_pct, { decimals: 1 }) }}</td>
          </tr>
        </tbody>
      </v-table>
    </div>

    <div v-if="subthemesMissing" class="px-4 pb-3 text-body-small text-medium-emphasis">
      {{ t('insights.subthemeHint') }}
    </div>
  </v-card>
</template>

<style scoped>
/* Na telefóne sa tabuľka posúva do strany, stránka nie. */
.breakdown-scroll {
  overflow-x: auto;
}

/* Najviac asi 12 riadkov (hlavička a 12 × 44 px), ďalej sa tabuľka posúva vnútri. */
.breakdown-scroll :deep(.v-table__wrapper) {
  max-height: 580px;
  overflow-y: auto;
}
</style>
