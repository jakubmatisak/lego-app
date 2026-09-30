<script setup lang="ts">
  /**
   * Moje údaje (GDPR): stiahnutie všetkého a zmazanie účtu.
   *
   * Export ide cez klienta a blob, nie odkazom: prihlásenie je token
   * v pamäti, obyčajný odkaz by sa stiahol ako 401. Zmazanie sa potvrdzuje
   * heslom a pred ním dialóg ponúkne export.
   */
  import { ref } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { api, errorMessage } from '@/api/client'
  import { useNotifyStore } from '@/stores/notify'
  import { isoDate } from '@/utils/format'
  import { reloadTo } from '@/utils/navigation'

  const { t } = useI18n()
  const notify = useNotifyStore()
  const exporting = ref(false)
  const deleteOpen = ref(false)
  const password = ref('')
  const deleting = ref(false)
  const deleteError = ref<string | null>(null)

  async function exportData (): Promise<void> {
    exporting.value = true
    try {
      const { data, error } = await api.GET('/auth/me/export', { parseAs: 'blob' })
      if (error || !(data instanceof Blob)) {
        notify.error(error, t('account.exportFailed'))
        return
      }
      const url = URL.createObjectURL(data)
      const link = document.createElement('a')
      link.href = url
      link.download = `moje-kocky-udaje-${isoDate()}.zip`
      link.click()
      setTimeout(() => URL.revokeObjectURL(url), 10_000)
    } catch (error_) {
      notify.error(error_, t('account.exportFailed'))
    } finally {
      exporting.value = false
    }
  }

  function openDelete (): void {
    password.value = ''
    deleteError.value = null
    deleteOpen.value = true
  }

  async function deleteAccount (): Promise<void> {
    deleting.value = true
    deleteError.value = null
    const { error } = await api.DELETE('/auth/me', { body: { password: password.value } })
    deleting.value = false
    if (error) {
      deleteError.value = errorMessage(error, t('account.deleteFailed'))
      return
    }
    // Nové načítanie vyprázdni pamäť stránky, aby po účte nič neostalo.
    reloadTo('/prihlasenie')
  }
</script>

<template>
  <v-card border class="pa-4 d-flex flex-column ga-3" flat>
    <div class="text-body-large font-weight-medium">{{ t('account.title') }}</div>
    <div class="text-body-medium text-medium-emphasis">{{ t('account.intro') }}</div>

    <div class="d-flex ga-2 flex-wrap">
      <v-btn :loading="exporting" prepend-icon="mdi-download" variant="tonal" @click="exportData">
        {{ t('account.export') }}
      </v-btn>

      <v-btn color="error" prepend-icon="mdi-account-remove-outline" variant="text" @click="openDelete">
        {{ t('account.delete') }}
      </v-btn>

      <v-spacer />

      <v-btn prepend-icon="mdi-shield-account-outline" to="/sukromie" variant="text">
        {{ t('privacy.title') }}
      </v-btn>
    </div>

    <v-dialog v-model="deleteOpen" max-width="520">
      <v-card :title="t('account.deleteTitle')">
        <v-card-text class="d-flex flex-column ga-3">
          <v-alert type="error" variant="tonal">{{ t('account.deleteWarning') }}</v-alert>
          <div class="text-body-medium">{{ t('account.deleteExportFirst') }}</div>

          <v-btn
            class="align-self-start"
            :loading="exporting"
            prepend-icon="mdi-download"
            variant="tonal"
            @click="exportData"
          >
            {{ t('account.export') }}
          </v-btn>

          <v-text-field
            v-model="password"
            autocomplete="current-password"
            :error-messages="deleteError ?? undefined"
            :label="t('account.password')"
            type="password"
          />
        </v-card-text>

        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="deleteOpen = false">{{ t('common.cancel') }}</v-btn>

          <v-btn
            color="error"
            :disabled="!password"
            :loading="deleting"
            variant="flat"
            @click="deleteAccount"
          >{{ t('account.deleteConfirm') }}</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>
