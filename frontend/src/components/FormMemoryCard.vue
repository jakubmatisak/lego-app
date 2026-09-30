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
    <div class="text-body-large font-weight-medium">{{ t('formMemory.title') }}</div>
    <div class="text-body-medium text-medium-emphasis">{{ t('formMemory.intro') }}</div>

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

    <div class="text-body-small text-medium-emphasis">{{ t('formMemory.where') }}</div>
  </v-card>
</template>
