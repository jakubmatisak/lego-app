<script setup lang="ts">
  /**
   * Stiahnutie zbierky do CSV.
   *
   * Nesmie to byť obyčajný odkaz: prihlásenie je token v pamäti, nie cookie,
   * a prehliadač by pri odkaze poslal požiadavku bez neho. Server by vrátil
   * 401 a namiesto súboru by sa stiahla chyba. Preto fetch cez klienta a súbor
   * sa poskladá v prehliadači.
   */
  import { ref } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { api } from '@/api/client'
  import { useNotifyStore } from '@/stores/notify'
  import { isoDate } from '@/utils/format'

  defineOptions({ inheritAttrs: false })

  const { t } = useI18n()
  const notify = useNotifyStore()
  const busy = ref(false)

  async function download (): Promise<void> {
    busy.value = true
    try {
      const { data, error: err } = await api.GET('/export/items.csv', { parseAs: 'blob' })
      if (err || !(data instanceof Blob)) {
        notify.error(err, t('collection.exportFailed'))
        return
      }
      const url = URL.createObjectURL(data)
      const link = document.createElement('a')
      link.href = url
      link.download = `zbierka-${isoDate()}.csv`
      link.click()
      // Uvoľniť až po spustení sťahovania, niektoré prehliadače si URL čítajú neskôr.
      setTimeout(() => URL.revokeObjectURL(url), 10_000)
    } catch (error_) {
      notify.error(error_, t('collection.exportFailed'))
    } finally {
      busy.value = false
    }
  }
</script>

<template>
  <v-btn
    v-bind="$attrs"
    :loading="busy"
    prepend-icon="mdi-download"
    @click="download"
  >{{ t('collection.exportCsv') }}</v-btn>
</template>
