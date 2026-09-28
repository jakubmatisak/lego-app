<script setup lang="ts">
  import type { ThemeRow } from '@/api/types'
  /**
   * Témy: tie, z ktorých niečo mám, a hľadanie vo všetkých.
   *
   * Zoznam tém je z Brickset a do jeho denného limitu sa neráta. Úplnosť
   * po rokoch (vlnách) je v detaile témy. Moje témy sa radia a filtrujú
   * v prehliadači (`utils/themeList.ts`), zoznam je malý a celý na obrazovke.
   */
  import type { ThemeSort } from '@/utils/themeList'
  import { computed, onMounted, reactive, ref } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useRouter } from 'vue-router'
  import { api, errorMessage } from '@/api/client'
  import CardGrid from '@/components/CardGrid.vue'
  import SeriesBar from '@/components/SeriesBar.vue'
  import { arrangeThemes } from '@/utils/themeList'

  const { t } = useI18n()
  const router = useRouter()

  const mine = ref<ThemeRow[]>([])
  const all = ref<ThemeRow[]>([])
  const enabled = ref(true)
  const loading = ref(true)
  const error = ref<string | null>(null)
  const picked = ref<string | null>(null)

  const SORTS: ThemeSort[] = ['mine', 'completeness', 'name']
  const view = reactive({ sort: 'mine' as ThemeSort, followed: false, withSets: false, incomplete: false })
  const shown = computed(() => arrangeThemes(mine.value, view.sort, view))
  const CHIPS = ['followed', 'withSets', 'incomplete'] as const

  const themeItems = computed(() =>
    all.value.map(row => ({ value: row.theme, title: `${row.theme} (${row.set_count})` })),
  )

  async function load (): Promise<void> {
    const { data, error: err } = await api.GET('/themes', {})
    loading.value = false
    if (err || !data) {
      error.value = errorMessage(err, t('themes.loadFailed'))
      return
    }
    mine.value = data.mine
    all.value = data.all
    enabled.value = data.provider_enabled
  }

  function open (theme: string | null): void {
    if (theme) router.push({ name: 'theme', params: { theme } })
  }

  onMounted(load)
</script>

<template>
  <div class="d-flex flex-column ga-4">
    <v-alert v-if="error" type="error" variant="tonal">{{ error }}</v-alert>

    <v-alert v-if="!loading && !enabled" icon="mdi-key-outline" type="info" variant="tonal">
      {{ t('themes.needsKey') }}
      <template #append>
        <v-btn size="small" :to="{ name: 'settings', query: { tab: 'data' } }" variant="text">
          {{ t('nav.settings') }}
        </v-btn>
      </template>
    </v-alert>

    <v-autocomplete
      v-if="enabled"
      v-model="picked"
      clearable
      density="comfortable"
      hide-details
      :items="themeItems"
      :label="t('themes.search')"
      prepend-inner-icon="mdi-magnify"
      style="max-width: 480px"
      @update:model-value="open"
    />

    <v-progress-linear v-if="loading" color="primary" indeterminate />

    <template v-else-if="enabled">
      <div class="d-flex align-center flex-wrap ga-2">
        <div class="text-h6 me-2">{{ t('themes.mine') }}</div>

        <v-chip
          v-for="chip in CHIPS"
          :key="chip"
          :color="view[chip] ? 'primary' : undefined"
          :prepend-icon="view[chip] ? 'mdi-check' : undefined"
          :variant="view[chip] ? 'tonal' : 'outlined'"
          @click="view[chip] = !view[chip]"
        >{{ t(`themes.filter.${chip}`) }}</v-chip>

        <v-spacer />

        <v-select
          v-model="view.sort"
          density="compact"
          hide-details
          :items="SORTS.map(value => ({ value, title: t(`themes.sort.${value}`) }))"
          :label="t('collection.sortBy')"
          style="max-width: 240px"
          variant="outlined"
        />
      </div>

      <v-empty-state
        v-if="mine.length === 0"
        icon="mdi-shape-outline"
        :text="t('themes.emptyHint')"
        :title="t('themes.empty')"
      />

      <v-empty-state v-else-if="shown.length === 0" icon="mdi-magnify" :title="t('themes.nothingMatches')" />

      <CardGrid v-else>
        <v-card
          v-for="row in shown"
          :key="row.theme"
          border
          class="pa-4 h-100 d-flex flex-column ga-1"
          flat
          :to="{ name: 'theme', params: { theme: row.theme } }"
        >
          <div class="d-flex align-center ga-1">
            <span class="text-subtitle-1 font-weight-medium">{{ row.theme }}</span>

            <v-icon
              v-if="row.followed"
              color="amber-darken-2"
              icon="mdi-star"
              size="small"
              :title="t('themes.followed')"
            />
          </div>

          <div class="text-caption text-medium-emphasis">
            {{ row.year_from }}–{{ row.year_to }} · {{ t('themes.setsInTheme', { count: row.set_count }) }}
          </div>

          <div class="text-body-2 mt-2">
            <template v-if="row.owned">
              {{ t('collection.setsPlural', row.owned, { named: { count: row.owned } }) }}
              {{ t('themes.inCollection') }}
            </template>

            <span v-else class="text-medium-emphasis">{{ t('themes.noSetYet') }}</span>
          </div>

          <SeriesBar v-if="row.set_count > 0" class="mt-auto" :owned="row.owned" :total="row.set_count" />
        </v-card>
      </CardGrid>
    </template>
  </div>
</template>
