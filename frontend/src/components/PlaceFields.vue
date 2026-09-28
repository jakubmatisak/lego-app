<script setup lang="ts">
  /**
   * Kde kus leží: miestnosť a krabica vedľa seba. Krabica je nepovinná
   * a našepkáva tie, ktoré sa už v zvolenej miestnosti použili (Povala →
   * 1, 2, 3…). Jedno miesto pre Pridať set, Kúpil som, Mám všetky aj
   * úpravu kusu, nech sa správa všade rovnako.
   *
   * Combobox pri vymazaní vráti null; text sa berie aj pri písaní, nie až
   * po opustení poľa, inak by rýchle uloženie (sken) vzalo starú hodnotu.
   */
  import { computed } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useCollectionStore } from '@/stores/collection'
  import { boxesFor } from '@/utils/place'

  const location = defineModel<string | null>('location', { required: true })
  const box = defineModel<string | null>('box', { required: true })
  defineProps<{ variant?: 'outlined' | 'filled' | 'underlined' }>()

  const { t } = useI18n()
  const collection = useCollectionStore()

  const boxItems = computed(() => boxesFor(collection.boxes, location.value))
</script>

<template>
  <div class="d-flex ga-3 flex-wrap">
    <v-combobox
      v-model="location"
      class="place-room"
      clearable
      :hint="t('place.roomHint')"
      :items="collection.locations"
      :label="t('add.location')"
      persistent-hint
      :variant="variant"
      @update:search="text => location = text"
    />

    <v-combobox
      v-model="box"
      class="place-box"
      clearable
      :hint="t('place.boxHint')"
      :items="boxItems"
      :label="t('place.box')"
      persistent-hint
      prepend-inner-icon="mdi-package-variant-closed"
      :variant="variant"
      @update:search="text => box = text"
    />
  </div>
</template>

<style scoped>
  .place-room {
    flex: 2 1 200px;
  }

  .place-box {
    flex: 1 1 130px;
  }
</style>
