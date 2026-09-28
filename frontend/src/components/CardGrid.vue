<script setup lang="ts">
/**
 * Mriežka kariet. Počet stĺpcov určuje dostupná šírka, nie breakpointy:
 * vojde sa toľko kariet, koľko sa ich zmestí pri minimálnej šírke. Na Full HD
 * je to šesť, na notebooku štyri, na telefóne jedna.
 *
 * Breakpointy Vuetify 4 na to nesedia. `xl` začína na 1545 px, takže šesť
 * kariet od neho by vyšlo po 215 px a suma s percentom sa do nich nezmestí.
 */
  const props = withDefaults(defineProps<{ min?: number }>(), { min: 250 })
</script>

<template>
  <div class="card-grid" :style="{ '--card-min': `${props.min}px` }">
    <slot />
  </div>
</template>

<style scoped>
.card-grid {
  display: grid;
  gap: 8px;
  /* min(…, 100%) drží jednu kartu na plnej šírke aj na najužšom telefóne. */
  grid-template-columns: repeat(auto-fill, minmax(min(var(--card-min), 100%), 1fr));
}
</style>
