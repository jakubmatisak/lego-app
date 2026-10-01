<script setup lang="ts">
  /**
   * Hlavička stĺpca, ktorá radí: názov a šípka pri zoradenom stĺpci.
   * Rovnaká vo všetkých tabuľkách; čo klik znamená, rieši rodič
   * (`utils/tableSort.ts::nextSort`). Ide aj klávesnicou (Enter, medzera).
   */
  import type { SortDir } from '@/utils/tableSort'

  defineProps<{
    title: string
    /** Smer, keď sa podľa stĺpca práve radí; inak null a šípka nie je. */
    dir: SortDir | null
  }>()

  const emit = defineEmits<{ sort: [] }>()
</script>

<template>
  <span
    class="sort-header"
    data-test="sort-header"
    role="button"
    tabindex="0"
    @click="emit('sort')"
    @keydown.enter.prevent="emit('sort')"
    @keydown.space.prevent="emit('sort')"
  >
    {{ title }}
    <v-icon v-if="dir" :icon="dir === 'asc' ? 'mdi-arrow-up' : 'mdi-arrow-down'" size="x-small" />
  </span>
</template>

<style scoped>
  .sort-header {
    cursor: pointer;
    user-select: none;
    white-space: nowrap;
  }
</style>
