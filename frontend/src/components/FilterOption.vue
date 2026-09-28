<script setup lang="ts">
  /**
   * Jedna voľba v paneli filtrov: začiarkávatko, popis a počet.
   *
   * Vybraná voľba je červená, aby bolo na prvý pohľad vidno, čo je zapnuté.
   * Poradie volieb určuje server podľa celej zbierky, takže zaškrtnutá voľba
   * zostane tam, kde bola. Voľba s nulou zošedne, kým nie je vybraná; dá sa
   * teda vždy odškrtnúť.
   */
  import { computed } from 'vue'

  const props = defineProps<{
    label: string
    /** Koľko kusov ostane s touto voľbou; nula voľbu zošedí. */
    count: number
    /** Iný text namiesto počtu, napríklad „2/12“ pri sérii. */
    countLabel?: string | null
    selected: boolean
    /** Podtéma pod témou. */
    nested?: boolean
    /** Farba kategórie (bodka pred popisom). */
    color?: string | null
  }>()

  const emit = defineEmits<{ toggle: [] }>()

  const dim = computed(() => props.count === 0 && !props.selected)
</script>

<template>
  <label
    class="filter-row"
    :class="{
      'filter-row--nested': nested,
      'filter-row--dim': dim,
      'filter-row--on': selected,
    }"
  >
    <v-checkbox-btn
      :color="selected ? 'primary' : undefined"
      density="compact"
      :model-value="selected"
      @update:model-value="emit('toggle')"
    />

    <span v-if="color" class="filter-dot" :class="`bg-${color}`" />
    <span class="filter-label">{{ label }}</span>
    <span class="filter-count">{{ countLabel ?? count }}</span>
  </label>
</template>

<style scoped>
.filter-row {
  align-items: center;
  cursor: pointer;
  display: flex;
  gap: 4px;
  min-height: 34px;
}

/* Vuetify dáva ovládaču flex: 1, bez toho by odtlačil popis na druhý kraj. */
.filter-row :deep(.v-selection-control) {
  flex: none;
}

.filter-row--nested {
  padding-left: 22px;
}

/* Voľba, po ktorej by nič neostalo. Ostáva klikateľná, len nevyčnieva. */
.filter-row--dim {
  opacity: 0.45;
}

.filter-row--on .filter-label,
.filter-row--on .filter-count {
  color: rgb(var(--v-theme-primary));
  font-weight: 500;
}

.filter-label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.filter-count {
  color: rgba(var(--v-theme-on-surface), 0.6);
  font-size: 0.8125rem;
  font-variant-numeric: tabular-nums;
}

.filter-dot {
  border-radius: 50%;
  display: inline-block;
  flex: none;
  height: 10px;
  width: 10px;
}
</style>
