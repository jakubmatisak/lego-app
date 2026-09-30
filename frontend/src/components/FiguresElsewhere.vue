<script setup lang="ts">
  /**
   * Upozornenie v Zbierke: figúrky zo sérií, ktoré by filter či hľadanie
   * našlo, sú v sekcii Figúrky. Zbierka ich neukazuje (`sets_only`), takže
   * bez toho by hľadanie figúrky skončilo „Nič sa nenašlo“ bez vysvetlenia
   * a import samých figúrok by vyzeral ako prázdny. Počet je
   * `FacetsOut.hidden_figures`.
   */
  import { useI18n } from 'vue-i18n'

  defineProps<{ count: number }>()

  const { t } = useI18n()
</script>

<template>
  <v-alert
    v-if="count > 0"
    density="compact"
    icon="mdi-account-group-outline"
    type="info"
    variant="tonal"
  >
    <div class="d-flex align-center flex-wrap ga-2">
      <span>{{ t('collection.figuresElsewherePlural', count, { named: { count } }) }}</span>

      <v-btn
        size="small"
        :to="{ name: 'minifigs' }"
        variant="text"
      >{{ t('collection.openMinifigs') }}</v-btn>
    </div>
  </v-alert>
</template>
