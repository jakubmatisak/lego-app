<script setup lang="ts">
  import type { Catalog } from '@/api/types'
  /**
   * Figúrka, ktorá zo zbieranej série chýba. Prerušovaný okraj, aby sa
   * nedala zameniť s tým, čo mám. Rovno sa dá pridať do Chcem, alebo
   * „Mám ju“, keď ju už kúpil, a to bez hľadania čísla.
   */
  import { useI18n } from 'vue-i18n'
  import GhostActions from '@/components/GhostActions.vue'
  import SetImage from '@/components/SetImage.vue'
  import { imageSrc } from '@/utils/imageSrc'

  defineProps<{
    catalog: Catalog
    /** Už je v Chcem. */
    wanted?: boolean
    /** Štítok chýbajúceho, predvolene „Chýba v sérii“. */
    missingLabel?: string
  }>()
  const emit = defineEmits<{ owned: [] }>()

  const { t } = useI18n()
</script>

<template>
  <v-card border class="ghost-card h-100 d-flex flex-column" flat>
    <div class="ghost-card__image">
      <SetImage :alt="catalog.name" rounded="0" :size="132" :src="imageSrc(catalog.image_url) ?? undefined" />
    </div>

    <div class="pa-3 d-flex flex-column ga-1 flex-grow-1">
      <div class="text-body-large font-weight-medium text-truncate">{{ catalog.name }}</div>

      <div class="text-body-small text-medium-emphasis text-truncate">
        {{ catalog.catalog_num }}
      </div>

      <v-chip class="align-self-start mt-1" label size="x-small" variant="outlined">
        {{ missingLabel ?? t('filters.missingCard') }}
      </v-chip>

      <div class="mt-auto pt-2 d-flex flex-wrap ga-1">
        <GhostActions :catalog="catalog" :wanted="wanted" @owned="emit('owned')" />
      </div>
    </div>
  </v-card>
</template>

<style scoped>
.ghost-card {
  background: transparent;
  border-style: dashed !important;
}

/* Chýbajúca figúrka je vidno, ale tlmene, nech sa nemýli s vlastnenou. */
.ghost-card__image {
  filter: grayscale(0.6);
  opacity: 0.6;
}
</style>
