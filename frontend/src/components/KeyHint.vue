<script setup lang="ts">
  /**
   * Nenápadná poznámka tam, kde by údaj doplnila služba, ku ktorej účet
   * nemá kľúč (alebo ju má vypnutú): čo by pribudlo a odkaz do Nastavení →
   * Dáta. Bez nej sa človek dozvie len „zadaj ručne“, nie že sa to dá pripojiť.
   */
  import { useI18n } from 'vue-i18n'

  defineProps<{
    /** rebrickable, brickset, brickeconomy, upcitemdb, eurostat */
    service: string
    /** Čo služba doplní, napríklad „Trhovú cenu a históriu doplní BrickEconomy.“ */
    text: string
  }>()

  const { t } = useI18n()
</script>

<template>
  <div class="key-hint d-flex align-center ga-2 flex-wrap text-body-medium">
    <v-icon color="primary" icon="mdi-key-plus" size="small" />
    <span class="text-medium-emphasis">{{ text }}</span>

    <v-btn
      class="px-1"
      color="primary"
      :data-service="service"
      size="small"
      :to="{ name: 'settings', query: { tab: 'data' } }"
      variant="text"
    >{{ t('keyHint.connect') }}</v-btn>
  </div>
</template>
