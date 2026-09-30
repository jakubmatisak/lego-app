<script setup lang="ts">
  /**
   * Verzia appky, ktorú hlási server (`GET /health`, zdroj je
   * `pyproject.toml`). Nenápadný riadok v Nastaveniach → Aplikácia, aby bolo
   * jasné, čo beží; podľa zmeny verzie server pri štarte zálohuje databázu.
   */
  import { onMounted, ref } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { api } from '@/api/client'

  const { t } = useI18n()
  const version = ref<string | null>(null)

  onMounted(async () => {
    try {
      const { data } = await api.GET('/health', {})
      version.value = data?.version ?? null
    } catch {
      // Bez spojenia so serverom verziu nevieme, riadok sa neukáže.
      version.value = null
    }
  })
</script>

<template>
  <div v-if="version" class="text-caption text-medium-emphasis">{{ t('settings.appVersion', { version }) }}</div>
</template>
