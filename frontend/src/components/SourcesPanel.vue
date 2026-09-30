<script setup lang="ts">
  /**
   * Nastavenia → Dáta: služby ako karty v poradí úrovní (Rebrickable,
   * Brickset, BrickEconomy, UPCitemdb, Eurostat).
   *
   * Zoznam aj stav prichádzajú zo servera (register schopností), takže nová
   * služba alebo nové volanie sa tu ukáže samo. Ukladanie a súbeh rýchlych
   * klikov rieši `createSources`; po každej zmene sa obnoví aj zoznam
   * schopností účtu, podľa ktorého sa inde v appke skrýva, čo nejde.
   */
  import { onMounted, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { api, errorMessage } from '@/api/client'
  import SourceCard from '@/components/SourceCard.vue'
  import { createSources } from '@/composables/useSources'
  import { useAuthStore } from '@/stores/auth'
  import { useNotifyStore } from '@/stores/notify'

  const { t } = useI18n()
  const notify = useNotifyStore()
  const auth = useAuthStore()

  const state = createSources(async body => {
    const { data, error: err } = await api.PUT('/auth/me/sources', { body })
    if (err || !data) throw new Error(errorMessage(err, t('sources.saveFailed')))
    // Schopnosti účtu sa zmenili: tlačidlo cien, Témy a pod. sa prekreslia.
    await auth.loadKeys()
    notify.success(t('notice.sourcesSaved'))
    return data.sources
  })
  const { sources, error } = state
  // Chyba uloženia ide do oznámenia; stav prepínačov sa už vrátil sám.
  watch(error, message => {
    if (message) notify.error(message)
  })

  async function load (): Promise<void> {
    const { data, error: err } = await api.GET('/auth/me/sources', {})
    if (err || !data) {
      notify.error(err, t('sources.loadFailed'))
      return
    }
    state.set(data.sources)
  }

  onMounted(load)
</script>

<template>
  <div class="d-flex flex-column ga-4">
    <div class="text-body-medium text-medium-emphasis">{{ t('sources.intro') }}</div>

    <SourceCard
      v-for="source in sources"
      :key="source.provider"
      :source="source"
      @auto-purchase="on => state.setAutoPurchase(on)"
      @batch="value => state.setBatch(value)"
      @key-changed="load"
      @reserve="(provider, value) => state.setReserve(provider, value)"
      @toggle="(cap, enabled) => state.toggle(cap, enabled)"
    />
  </div>
</template>
