<script setup lang="ts">
  // Rám appky vykresľuje router, lebo verejná stránka zbierky
  // má vlastný layout bez navigácie.
  import { watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useLocale } from 'vuetify'

  // Jazyk Vuetify (kalendár, formát dátumu v poli) ide za jazykom appky,
  // inak by dátumové pole čakalo americký mm/dd/rrrr.
  const { locale } = useI18n()
  const vuetifyLocale = useLocale()
  watch(locale, value => {
    vuetifyLocale.current.value = value
  }, { immediate: true })
</script>

<template>
  <router-view />
</template>
