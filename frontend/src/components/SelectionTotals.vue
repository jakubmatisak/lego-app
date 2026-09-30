<script setup lang="ts">
  /**
   * Súčty toho, čo filter v Zbierke ukazuje: kúpené, hodnota, zisk
   * a vedľa neho reálny zisk, teda po odpočítaní inflácie na Slovensku.
   *
   * Reálny zisk len pri zapnutej inflácii (prepínač v hornej lište).
   * Kus bez trhovej ceny do zisku nevstupuje, len sa spočíta.
   */
  import type { SelectionTotals } from '@/api/types'
  import { computed } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useCollectionStore } from '@/stores/collection'
  import { exactMoney, money, percent } from '@/utils/format'

  const props = defineProps<{ totals: SelectionTotals | null | undefined }>()
  // Reálne sumy len pri zapnutej inflácii; inak by riadok miešal dva pohľady.
  const collection = useCollectionStore()
  const { t } = useI18n()

  const month = computed(() => {
    const raw = props.totals?.real_month
    if (!raw) return null
    const [year, mm] = raw.split('-')
    return `${mm}/${year}`
  })

  function tone (value: string | null | undefined): string {
    // Null: cenu nemá ani jeden kus, zisk nepoznáme. Pomlčka bez farby.
    if (value === null || value === undefined) return 'text-medium-emphasis'
    return Number(value) >= 0 ? 'text-positive' : 'text-negative'
  }

  function gain (value: string | null | undefined, pct: number | null | undefined): string {
    const base = money(value, { sign: true, decimals: 2 })
    return pct === null || pct === undefined ? base : `${base} (${percent(pct, { sign: true, decimals: 0 })})`
  }
</script>

<template>
  <div v-if="totals && (totals.owned > 0 || totals.sold > 0)" class="selection-totals text-body-medium">
    <template v-if="totals.owned > 0">
      <span>
        <span class="text-medium-emphasis me-1">{{ t('totals.purchased') }}</span>
        {{ exactMoney(totals.purchase) }}
      </span>

      <span>
        <span class="text-medium-emphasis me-1">{{ t('totals.value') }}</span>
        {{ exactMoney(totals.market_value) }}
      </span>

      <span>
        <span class="text-medium-emphasis me-1">{{ t('totals.profit') }}</span>

        <span class="font-weight-medium" :class="tone(totals.unrealized)">
          {{ gain(totals.unrealized, totals.unrealized_pct) }}
        </span>
      </span>

      <v-tooltip
        v-if="collection.real && totals.unrealized_real !== null"
        location="bottom"
        max-width="340"
        :text="t('totals.realHint', { month, amount: exactMoney(totals.purchase_real) })"
      >
        <template #activator="{ props: tip }">
          <span v-bind="tip" class="real">
            <v-icon class="me-1" icon="mdi-cash-clock" size="small" />
            <span class="text-medium-emphasis me-1">{{ t('totals.realProfit') }}</span>

            <span class="font-weight-medium" :class="tone(totals.unrealized_real)">
              {{ gain(totals.unrealized_real, totals.unrealized_real_pct) }}
            </span>
          </span>
        </template>
      </v-tooltip>

      <span v-if="totals.price_missing > 0" class="text-medium-emphasis">
        {{ t('totals.noPrice', { count: totals.price_missing }) }}
      </span>
    </template>

    <span v-if="totals.sold > 0">
      <span class="text-medium-emphasis me-1">{{ t('totals.realized') }}</span>

      <span class="font-weight-medium" :class="tone(totals.realized)">
        {{ money(totals.realized, { sign: true, decimals: 2 }) }}
      </span>

      <span v-if="collection.real && totals.realized_real !== null" class="text-medium-emphasis ms-1">
        ({{ t('totals.realShort') }} {{ money(totals.realized_real, { sign: true, decimals: 2 }) }})
      </span>
    </span>
  </div>
</template>

<style scoped>
.selection-totals {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 16px;
  align-items: baseline;
}

.selection-totals > span,
.real {
  white-space: nowrap;
}

.real {
  cursor: help;
}
</style>
