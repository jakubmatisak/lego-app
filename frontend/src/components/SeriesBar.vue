<script setup lang="ts">
  /** Pruh kompletnosti série (farba a dĺžka zo `seriesBar`). */
  import { computed } from 'vue'
  import { seriesBar } from '@/utils/series'

  /**
   * `complete`: kompletnosť zo servera (Série), inak podľa počtov. Predvolené
   * `undefined`, nie `false`: Vue by chýbajúci boolean zmenil na false.
   */
  const props = withDefaults(defineProps<{ owned: number, total: number, complete?: boolean }>(), {
    complete: undefined,
  })

  const bar = computed(() => seriesBar(props.owned, props.total, props.complete))
</script>

<template>
  <v-progress-linear
    bg-color="on-surface"
    bg-opacity="0.12"
    :color="bar.color"
    height="6"
    :model-value="bar.pct"
    rounded
  />
</template>
