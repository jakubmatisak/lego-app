<script setup lang="ts">
/**
 * Výkonnosť vlastnených kusov podľa témy, podtémy alebo zoznamu.
 * Počíta sa z uložených cien, zdroj cien sa tu nevolá. Skupina, v ktorej
 * cenu nemá ani jeden kus, príde s hodnotou null a ukáže pomlčku, nie 0 €.
 */
  import type { BreakdownRow } from '@/api/types'
  import { computed, onMounted, ref, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { api } from '@/api/client'
  import { onPageReload } from '@/composables/usePageLoad'
  import { useCollectionStore } from '@/stores/collection'
  import { money, percent } from '@/utils/format'

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
      <v-table density="comfortable">
        <thead>
          <tr>
            <th />
            <th class="text-end">{{ t('insights.colPieces') }}</th>
            <th class="text-end">{{ t('insights.colInvested') }}</th>
            <th class="text-end">{{ t('insights.colValue') }}</th>
            <th class="text-end">{{ t('insights.colProfit') }}</th>
            <th class="text-end">{{ t('insights.colYearly') }}</th>
          </tr>
        </thead>

        <tbody>
          <tr v-for="row in rows" :key="row.key ?? '_'">
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
</style>
