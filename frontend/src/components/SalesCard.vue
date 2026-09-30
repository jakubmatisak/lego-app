<script setup lang="ts">
/** Predaje podľa kanála (Aukro, Bazoš, osobne) s čistým ziskom po nákladoch. */
  import type { SalesChannel } from '@/api/types'
  import { onMounted, ref, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { api } from '@/api/client'
  import { useCollectionStore } from '@/stores/collection'
  import { money, percent } from '@/utils/format'

  const { t } = useI18n()
  const rows = ref<SalesChannel[]>([])

  const collection = useCollectionStore()

  async function load (): Promise<void> {
    const { data } = await api.GET('/stats/sales', { params: { query: collection.statsQuery() } })
    rows.value = data ?? []
  }

  onMounted(load)
  watch(() => [collection.real, collection.scope], load)
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
            <th />
            <th class="text-end">{{ t('insights.colSold') }}</th>
            <th class="text-end">{{ t('insights.colProceeds') }}</th>
            <th class="text-end">{{ t('insights.colCosts') }}</th>
            <th class="text-end">{{ t('insights.colRealized') }}</th>
            <th class="text-end">{{ t('insights.colRoi') }}</th>
          </tr>
        </thead>

        <tbody>
          <tr v-for="row in rows" :key="row.label">
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
