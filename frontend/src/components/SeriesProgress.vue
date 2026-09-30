<script setup lang="ts">
  import type { SeriesProgress } from '@/api/types'
  /**
   * Kompletnosť zberateľských sérií na Prehľade.
   *
   * Nekompletné idú prvé a chýbajúce figúrky sú vidieť hneď, bez rozkliknutia.
   * Pruh pri 11 z 12 vyzerá skoro plný, takže samotný pruh nestačí: stav
   * hovorí aj text („chýba 1“) a kompletná séria má vlastný zelený znak.
   * „Ukázať chýbajúce“ vedie do Figúrok, Zbierka figúrky zo sérií nemá.
   */
  import { computed } from 'vue'
  import { useI18n } from 'vue-i18n'
  import SeriesBar from '@/components/SeriesBar.vue'
  import SetImage from '@/components/SetImage.vue'
  import { imageSrc } from '@/utils/imageSrc'

  const props = defineProps<{ series: SeriesProgress[] }>()

  const { t } = useI18n()

  /** Koľko chýbajúcich ukázať ako obrázky, zvyšok ako „+N“. */
  const THUMBS = 6

  const rows = computed(() =>
    props.series
      .map(row => ({ ...row, missingCount: Math.max(row.total - row.owned, 0) }))
      .toSorted((a, b) => {
        // Nekompletné prvé, z nich tie, ktorým chýba najmenej.
        const aDone = a.missingCount === 0
        const bDone = b.missingCount === 0
        if (aDone !== bDone) return aDone ? 1 : -1
        return a.missingCount - b.missingCount || a.name.localeCompare(b.name)
      }),
  )
</script>

<template>
  <v-card border class="h-100 d-flex flex-column" flat>
    <v-card-item>
      <v-card-title class="text-h6 pa-0">{{ t('dashboard.seriesProgress') }}</v-card-title>
    </v-card-item>

    <div class="px-4 pb-4 d-flex flex-column ga-4">
      <div v-for="row in rows" :key="row.series_num">
        <div class="d-flex align-center ga-2">
          <span class="text-body-2 font-weight-medium text-truncate">{{ row.name }}</span>
          <v-spacer />

          <v-chip
            v-if="row.missingCount === 0"
            color="positive"
            label
            prepend-icon="mdi-check"
            size="small"
            variant="tonal"
          >{{ t('dashboard.seriesDone') }}</v-chip>

          <span v-else class="text-body-2 text-no-wrap">
            {{ t('dashboard.seriesOf', { owned: row.owned, total: row.total }) }}
            <span class="series-missing-count font-weight-medium">
              · {{ t('dashboard.seriesMissingPlural', row.missingCount, { named: { count: row.missingCount } }) }}
            </span>
          </span>
        </div>

        <SeriesBar class="mt-2" :owned="row.owned" :total="row.total" />

        <div v-if="row.missing.length > 0" class="d-flex align-center flex-wrap ga-2 mt-2">
          <SetImage
            v-for="missing in row.missing.slice(0, THUMBS)"
            :key="missing.catalog_num"
            :alt="missing.name"
            class="series-thumb"
            rounded="md"
            :size="40"
            :src="imageSrc(missing.image_url) ?? undefined"
            :title="missing.name"
          />

          <span v-if="row.missing.length > THUMBS" class="text-caption text-medium-emphasis">
            +{{ row.missing.length - THUMBS }}
          </span>

          <v-btn
            class="ms-auto"
            size="small"
            :to="{ name: 'minifig-series', params: { num: row.series_num }, query: { show: 'missing' } }"
            variant="text"
          >{{ t('dashboard.seriesShowMissing') }}</v-btn>
        </div>
      </div>
    </div>
  </v-card>
</template>

<style scoped>
/* Žltá z témy je na bielej nečitateľná, text potrebuje tmavší odtieň. */
.series-missing-count {
  color: #B25E00;
}

.v-theme--dark .series-missing-count {
  color: #FFB74D;
}

.series-thumb {
  flex: none;
  width: 40px;
}
</style>
