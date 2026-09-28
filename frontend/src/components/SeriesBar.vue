<script setup lang="ts">
  /** Pruh kompletnosti série (farba a dĺžka zo `seriesBar`). */
  import { computed } from 'vue'
  import { seriesBar } from '@/utils/series'

  const props = defineProps<{ owned: number, total: number }>()

  const bar = computed(() => seriesBar(props.owned, props.total))
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
