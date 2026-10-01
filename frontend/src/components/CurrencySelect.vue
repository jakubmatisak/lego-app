<script setup lang="ts">
  /**
   * Výber meny pri cene kúpy alebo predaja (Nastavenia → Zobrazenie →
   * „Kúpu a predaj zadávať aj v inej mene“). Uloží sa v eurách; sumu
   * v cudzej mene prepočíta server kurzom ECB zo dňa kúpy či predaja.
   */
  import { useI18n } from 'vue-i18n'
  import { CURRENCIES, type CurrencyCode } from '@/utils/format'

  const model = defineModel<CurrencyCode>({ required: true })
  const { t } = useI18n()
</script>

<template>
  <v-select
    v-model="model"
    class="currency-select"
    data-test="currency-select"
    hide-details
    :items="CURRENCIES"
    :label="t('currency.field')"
  />
</template>

<style scoped>
  /* Vedľa poľa s nápovedou by sa inak natiahol na výšku aj s ňou. */
  .currency-select {
    align-self: flex-start;
    flex: 0 0 104px;
    max-width: 104px;
  }
</style>
