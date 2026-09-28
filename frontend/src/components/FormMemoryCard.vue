<script setup lang="ts">
  /**
   * Nastavenia → Formuláre: ktoré polia si pridávanie pamätá.
   *
   * Zapnuté pole sa pri ďalšom pridaní predvyplní poslednou hodnotou
   * (useFormMemory). Hodí sa pri skenovaní kopy krabíc z jednej police.
   */
  import { onMounted } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { FORM_FIELDS, useFormMemory } from '@/composables/useFormMemory'

  const { t } = useI18n()
  const memory = useFormMemory()

  onMounted(() => memory.load())
</script>

<template>
  <v-card border class="pa-4 d-flex flex-column ga-2" flat>
    <div class="text-subtitle-1 font-weight-medium">{{ t('formMemory.title') }}</div>
    <div class="text-body-2 text-medium-emphasis">{{ t('formMemory.intro') }}</div>

    <v-switch
      v-for="field in FORM_FIELDS"
      :key="field"
      color="primary"
      density="compact"
      hide-details
      :label="t(`formMemory.fields.${field}`)"
      :model-value="memory.remembered.value[field]"
      @update:model-value="value => memory.setRemember(field, Boolean(value))"
    />

    <div class="text-caption text-medium-emphasis">{{ t('formMemory.where') }}</div>
  </v-card>
</template>
