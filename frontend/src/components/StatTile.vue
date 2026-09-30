<script setup lang="ts">
/** Jedno číslo na Prehľade: názov, hodnota a jednoriadkový podtitul. */
  withDefaults(defineProps<{
    label: string
    value: string
    hint?: string | null
    color?: string | null
    chip?: string | null
    chipColor?: string | null
  }>(), {
    hint: null,
    color: null,
    chip: null,
    chipColor: 'positive',
  })
</script>

<template>
  <v-card border class="stat-tile h-100 pa-4 d-flex flex-column justify-space-between" flat>
    <span class="text-label-medium text-uppercase text-medium-emphasis stat-tile__label">{{ label }}</span>
    <span class="stat-tile__value" :class="color ? `text-${color}` : ''">{{ value }}</span>

    <v-chip
      v-if="chip"
      class="align-self-start"
      :color="chipColor ?? undefined"
      density="comfortable"
      size="small"
      variant="tonal"
    >{{ chip }}</v-chip>

    <!-- Čip aj poznámka môžu byť naraz: pri zisku percento aj ročný výnos. -->
    <span v-if="hint" class="text-body-small text-medium-emphasis">{{ hint }}</span>
    <span v-if="!chip && !hint" class="text-body-small">&nbsp;</span>
  </v-card>
</template>

<style scoped>
.stat-tile {
  min-height: 108px;
  gap: 4px;
}

.stat-tile__label {
  line-height: 1.2;
  letter-spacing: 0.4px;
}

.stat-tile__value {
  font-size: 1.6rem;
  font-weight: 500;
  line-height: 1.15;
}
</style>
