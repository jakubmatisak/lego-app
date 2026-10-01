<script setup lang="ts">
/**
 * Prvé načítanie stránky zlyhalo. Namiesto prázdneho stavu („Zatiaľ žiadne
 * sety“), ktorý by tvrdil, že zbierka je prázdna, povie, že sa nepodarilo
 * načítať, a ponúkne Skúsiť znova (`composables/usePageLoad.ts`).
 */
  import { useI18n } from 'vue-i18n'

  defineProps<{
    /** Konkrétnejší text (napríklad „Set sa nenašiel“); inak všeobecný. */
    message?: string | null
    /** Kým beží nový pokus, tlačidlo sa točí. */
    loading?: boolean
  }>()
  const emit = defineEmits<{ retry: [] }>()

  const { t } = useI18n()
</script>

<template>
  <v-empty-state
    class="load-failed"
    icon="mdi-cloud-alert-outline"
    :text="t('common.loadFailedHint')"
    :title="message || t('common.loadFailed')"
  >
    <template #actions>
      <v-btn
        color="primary"
        :loading="loading"
        prepend-icon="mdi-refresh"
        variant="flat"
        @click="emit('retry')"
      >{{ t('common.retry') }}</v-btn>
    </template>
  </v-empty-state>
</template>
