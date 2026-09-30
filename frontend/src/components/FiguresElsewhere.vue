<script setup lang="ts">
  /**
   * Riadok v Zbierke: figúrky zo sérií, ktoré by hľadanie či filter našlo,
   * sú v sekcii Figúrky. Zbierka ich neukazuje (`sets_only`), takže bez toho
   * by hľadanie figúrky skončilo „Nič sa nenašlo“ bez vysvetlenia a import
   * samých figúrok by vyzeral ako prázdny. Počet je `FacetsOut.hidden_figures`.
   *
   * Kedy sa ukáže, rozhoduje Zbierka (len pri hľadaní alebo prázdnom
   * výsledku). Je to nenápadný riadok ako súčty nad ním, nie `v-alert`:
   * ten má v rozložení Zbierky `flex: 1 1` a roztiahol by sa do výšky.
   * Písmo je `text-body-medium` (14 px): Vuetify 4 má typografiu MD3 a stará
   * `text-body-medium` v ňom nie je, riadok by bol väčší než text okolo.
   *
   * `pending`: hľadanie sa práve spresňuje a počty ešte patria predošlému.
   * Riadok si podrží miesto, aby výsledky pod ním pri písaní neposkakovali,
   * ale starý počet neukáže ani neprečíta.
   */
  import { useI18n } from 'vue-i18n'

  withDefaults(defineProps<{ count: number, pending?: boolean }>(), { pending: false })

  const { t } = useI18n()
</script>

<template>
  <div
    v-if="count > 0"
    :aria-hidden="pending || undefined"
    class="figures-elsewhere text-body-medium text-medium-emphasis"
    :class="{ 'figures-elsewhere--pending': pending }"
  >
    <v-icon icon="mdi-account-group-outline" size="small" />
    <span>{{ t('collection.figuresElsewherePlural', count, { named: { count } }) }}</span>

    <!-- Pomenovaná trasa, aby viedla aj v desktope s hash routerom. -->
    <router-link class="figures-elsewhere__link" :to="{ name: 'minifigs' }">
      {{ t('collection.openMinifigs') }}
    </router-link>
  </div>
</template>

<style scoped>
.figures-elsewhere {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 8px;
}

/* Miesto ostane, obsah (aj odkaz) nie je vidieť ani sa naň nedá prejsť. */
.figures-elsewhere--pending {
  visibility: hidden;
}

.figures-elsewhere__link {
  color: rgb(var(--v-theme-primary));
  font-weight: 500;
  text-decoration: none;
}

.figures-elsewhere__link:hover,
.figures-elsewhere__link:focus-visible {
  text-decoration: underline;
}
</style>
