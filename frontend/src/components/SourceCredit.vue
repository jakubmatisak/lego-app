<script setup lang="ts">
  /**
   * Poďakovanie zdroju údajov s odkazom von (Rebrickable, Brickset).
   * Nenápadné, vo farbe okolitého textu, nie modrý odkaz prehliadača.
   */
  defineProps<{ href: string, text: string }>()
</script>

<template>
  <div class="text-body-small text-medium-emphasis">
    <a class="source-credit" :href="href" rel="noopener" target="_blank">
      {{ text }}
      <v-icon icon="mdi-open-in-new" size="x-small" />
    </a>
  </div>
</template>

<style scoped>
  .source-credit {
    color: inherit;
    text-decoration: none;
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }

  .source-credit:hover,
  .source-credit:focus-visible {
    color: rgb(var(--v-theme-primary));
    text-decoration: underline;
  }
</style>
