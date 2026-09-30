<script setup lang="ts">
  import type { Catalog } from '@/api/types'
  /**
   * Figúrka, ktorá zo zbieranej série chýba. Prerušovaný okraj, aby sa
   * nedala zameniť s tým, čo mám. Rovno sa dá pridať do Chcem, alebo
   * „Mám ju“, keď ju už kúpil, a to bez hľadania čísla.
   */
  import { ref } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { api } from '@/api/client'
  import PurchaseDialog from '@/components/PurchaseDialog.vue'
  import SetImage from '@/components/SetImage.vue'
  import { useNotifyStore } from '@/stores/notify'
  import { imageSrc } from '@/utils/imageSrc'

  const props = defineProps<{
    catalog: Catalog
    /** Už je v Chcem. */
    wanted?: boolean
    /** Štítok chýbajúceho, predvolene „Chýba v sérii“. */
    missingLabel?: string
  }>()
  const emit = defineEmits<{ owned: [] }>()

  const { t } = useI18n()
  const notify = useNotifyStore()
  const added = ref(props.wanted ?? false)
  const buyOpen = ref(false)
  const saving = ref(false)

  async function wish (): Promise<void> {
    saving.value = true
    const { error, response } = await api.POST('/wishlist', {
      body: { catalog_num: props.catalog.catalog_num },
    })
    saving.value = false
    // 409 znamená, že set už v Chcem je. Aj to je pre používateľa „hotovo“.
    added.value = !error || response.status === 409
    if (added.value) {
      notify.success(t('notice.wishAdded', { name: props.catalog.name }))
    } else {
      notify.error(error, t('notice.wishFailed'))
    }
  }
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
        <v-btn
          color="primary"
          prepend-icon="mdi-check-circle-outline"
          size="small"
          variant="tonal"
          @click="buyOpen = true"
        >{{ catalog.kind === 'minifig' ? t('purchase.haveIt') : t('purchase.haveItSet') }}</v-btn>

        <v-btn
          :color="added ? 'positive' : 'primary'"
          :disabled="added"
          :loading="saving"
          :prepend-icon="added ? 'mdi-check' : 'mdi-heart-outline'"
          size="small"
          variant="text"
          @click="wish"
        >{{ added ? t('filters.inWish') : t('filters.addWish') }}</v-btn>
      </div>
    </div>

    <PurchaseDialog v-model="buyOpen" :catalog="catalog" @saved="emit('owned')" />
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
