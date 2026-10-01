<script setup lang="ts">
/**
 * Predaje podľa kanála (Aukro, Bazoš, osobne) s čistým ziskom po nákladoch.
 * Radí sa klikom na hlavičku, na klientovi; predvolene podľa zisku ako zo
 * servera. Neuvedený kanál a výnos bez hodnoty sú na konci v oboch smeroch.
 */
  import type { SalesChannel } from '@/api/types'
  import type { SortDir, SortState, SortValue } from '@/utils/tableSort'
  import { computed, onMounted, ref, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { api } from '@/api/client'
  import SortHeader from '@/components/SortHeader.vue'
  import { onPageReload } from '@/composables/usePageLoad'
  import { useCollectionStore } from '@/stores/collection'
  import { money, percent, toNumber } from '@/utils/format'
  import { headerDir, nextSort, sortRows } from '@/utils/tableSort'

  const { t } = useI18n()
  const rows = ref<SalesChannel[]>([])

  const collection = useCollectionStore()

  async function load (): Promise<void> {
    const { data } = await api.GET('/stats/sales', { params: { query: collection.statsQuery() } })
    rows.value = data ?? []
  }

  type Column = 'label' | 'count' | 'proceeds' | 'costs' | 'realized' | 'roi'
  const COLUMNS: Array<{ key: Column, title: string }> = [
    { key: 'label', title: 'insights.colChannel' },
    { key: 'count', title: 'insights.colSold' },
    { key: 'proceeds', title: 'insights.colProceeds' },
    { key: 'costs', title: 'insights.colCosts' },
    { key: 'realized', title: 'insights.colRealized' },
    { key: 'roi', title: 'insights.colRoi' },
  ]
  const VALUES: Record<Column, (row: SalesChannel) => SortValue> = {
    label: row => (row.channel ? row.label : null),
    count: row => row.count,
    proceeds: row => toNumber(row.proceeds),
    costs: row => toNumber(row.costs),
    realized: row => toNumber(row.realized),
    roi: row => row.roi_pct,
  }
  const defaultDir = (column: Column): SortDir => (column === 'label' ? 'asc' : 'desc')
  const order = ref<SortState<Column>>({ sort: 'realized', dir: null })
  const sorted = computed(() =>
    sortRows(rows.value, VALUES[order.value.sort], order.value.dir ?? defaultDir(order.value.sort)),
  )

  onMounted(load)
  watch(() => [collection.real, collection.scope], load)
  // Tlačidlo Obnoviť stránku v hornej lište.
  onPageReload(load)
</script>

<template>
  <v-card v-if="rows.length > 0" border flat>
    <v-card-item>
      <v-card-title class="text-title-large font-weight-medium pa-0">{{ t('insights.salesTitle') }}</v-card-title>
    </v-card-item>

    <div class="sales-scroll">
      <v-table density="comfortable">
        <thead>
          <tr>
            <th v-for="column in COLUMNS" :key="column.key" :class="{ 'text-end': column.key !== 'label' }">
              <SortHeader
                :dir="headerDir(column.key, order, defaultDir)"
                :title="t(column.title)"
                @sort="order = nextSort(column.key, order, defaultDir)"
              />
            </th>
          </tr>
        </thead>

        <tbody>
          <tr v-for="row in sorted" :key="row.label">
            <td class="font-weight-medium">{{ row.label }}</td>
            <td class="text-end">{{ row.count }}</td>
            <td class="text-end">{{ money(row.proceeds) }}</td>
            <td class="text-end text-medium-emphasis">{{ money(row.costs) }}</td>

            <td
              class="text-end font-weight-medium"
              :class="Number(row.realized) >= 0 ? 'text-positive' : 'text-negative'"
            >{{ money(row.realized, { sign: true }) }}</td>

            <td class="text-end">{{ row.roi_pct === null ? '—' : percent(row.roi_pct, { decimals: 0 }) }}</td>
          </tr>
        </tbody>
      </v-table>
    </div>
  </v-card>
</template>

<style scoped>
.sales-scroll {
  overflow-x: auto;
}
</style>
