<script setup lang="ts">
  import type { Catalog } from '@/api/types'
  /**
   * Akcie chýbajúcej figúrky: „Mám ju“ (dialóg kúpy) a pridanie do Chcem.
   *
   * Jedny pre kartu (`GhostCard`) aj pre riadok tabuľky v sérii, aby sa
   * logika nerozišla. V tabuľke je srdiečko len ikona (`compact`).
   */
  import { ref, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { api } from '@/api/client'
  import PurchaseDialog from '@/components/PurchaseDialog.vue'
  import { useNotifyStore } from '@/stores/notify'

  const props = defineProps<{
    catalog: Catalog
    /** Už je v Chcem. */
    wanted?: boolean
    /** Srdiečko bez textu, do riadku tabuľky. */
    compact?: boolean
  }>()
  const emit = defineEmits<{ owned: [], wished: [] }>()

  const { t } = useI18n()
  const notify = useNotifyStore()
  const added = ref(props.wanted ?? false)
  const buyOpen = ref(false)
  const saving = ref(false)

  // Po načítaní série znova (napríklad po kúpe) platí stav zo servera.
  watch(() => props.wanted, value => {
    if (value) added.value = true
  })

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
      emit('wished')
    } else {
      notify.error(error, t('notice.wishFailed'))
    }
  }
</script>

<template>
  <v-btn
    color="primary"
    prepend-icon="mdi-check-circle-outline"
    size="small"
    variant="tonal"
    @click="buyOpen = true"
  >{{ catalog.kind === 'minifig' ? t('purchase.haveIt') : t('purchase.haveItSet') }}</v-btn>

  <v-btn
    v-if="compact"
    :color="added ? 'positive' : 'primary'"
    :disabled="added"
    :icon="added ? 'mdi-check' : 'mdi-heart-outline'"
    :loading="saving"
    size="small"
    :title="added ? t('filters.inWish') : t('filters.addWish')"
    variant="text"
    @click="wish"
  />

  <v-btn
    v-else
    :color="added ? 'positive' : 'primary'"
    :disabled="added"
    :loading="saving"
    :prepend-icon="added ? 'mdi-check' : 'mdi-heart-outline'"
    size="small"
    variant="text"
    @click="wish"
  >{{ added ? t('filters.inWish') : t('filters.addWish') }}</v-btn>

  <PurchaseDialog v-model="buyOpen" :catalog="catalog" @saved="emit('owned')" />
</template>
