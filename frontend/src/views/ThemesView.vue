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
  import LoadFailed from '@/components/LoadFailed.vue'
  import PageSkeleton from '@/components/PageSkeleton.vue'
  import SeriesBar from '@/components/SeriesBar.vue'
  import ThemeSetSearch from '@/components/ThemeSetSearch.vue'
  import { usePageLoad } from '@/composables/usePageLoad'
  import { arrangeThemes, savedYears, themeSource } from '@/utils/themeList'

  const { t } = useI18n()
  const router = useRouter()

  const mine = ref<ThemeRow[]>([])
  const all = ref<ThemeRow[]>([])
  const enabled = ref(true)
  /** Text chyby (Brickset neodpovedá), pre LoadFailed. */
  const error = ref<string | null>(null)
  const picked = ref<string | null>(null)

  const SORTS: ThemeSort[] = ['mine', 'completeness', 'name']
  const view = reactive({
    sort: 'mine' as ThemeSort,
    followed: false,
    withSets: false,
    incomplete: false,
    downloaded: false,
  })
  const shown = computed(() => arrangeThemes(themeSource(mine.value, all.value, view), view.sort, view))
  const CHIPS = ['followed', 'withSets', 'incomplete', 'downloaded'] as const

  const themeItems = computed(() =>
    all.value.map(row => ({
      value: row.theme,
      title: `${row.theme} (${row.set_count})`,
      row,
    })),
  )

  /** „uložené: 2 ročníky“, alebo „uložené všetko“, keď nič nezostáva. */
  function savedLabel (row: ThemeRow): string | null {
    const saved = savedYears(row)
    if (!saved) return null
    if (saved.all) return t('themes.savedAll')
    return t('themes.savedYearsPlural', saved.saved, { named: { count: saved.saved } })
  }

  /** „zostáva: 5“; bez známeho počtu ročníkov a pri všetkom uloženom nič. */
  function leftLabel (row: ThemeRow): string | null {
    const saved = savedYears(row)
    return saved && saved.left !== null && !saved.all ? t('themes.savedLeft', { count: saved.left }) : null
  }

  async function load (): Promise<boolean> {
    const { data, error: err } = await api.GET('/themes', {})
    if (err || !data) {
      error.value = errorMessage(err, t('themes.loadFailed'))
      return false
    }
    error.value = null
    mine.value = data.mine
    all.value = data.all
    enabled.value = data.provider_enabled
    return true
  }

  /** Prvé načítanie kostra, Obnoviť stránku nad starými kartami (usePageLoad). */
  const page = usePageLoad(load)

  function open (theme: string | null): void {
    if (theme) router.push({ name: 'theme', params: { theme } })
  }

  onMounted(() => page.run())
</script>

<template>
  <div class="d-flex flex-column ga-4">
    <v-alert v-if="page.loaded && !enabled" icon="mdi-key-outline" type="info" variant="tonal">
      {{ t('themes.needsKey') }}
      <template #append>
        <v-btn size="small" :to="{ name: 'settings', query: { tab: 'data' } }" variant="text">
          {{ t('nav.settings') }}
        </v-btn>
      </template>
    </v-alert>

    <!-- Séria aj set v jednom riadku; výsledky v plávajúcej ponuke, stránka sa neposúva. -->
    <div v-if="enabled" class="d-flex flex-wrap align-start ga-3">
      <v-autocomplete
        v-model="picked"
        clearable
        density="comfortable"
        hide-details
        :items="themeItems"
        :label="t('themes.search')"
        prepend-inner-icon="mdi-magnify"
        style="max-width: 480px; flex: 1 1 320px"
        @update:model-value="open"
      >
        <!-- Séria s uloženými ročníkmi: koľko je uložených a pod tým koľko zostáva. -->
        <template #item="{ props: itemProps, item }">
          <v-list-item v-bind="itemProps">
            <template v-if="savedLabel(item.row)" #append>
              <div class="text-body-small text-medium-emphasis text-end me-2">
                <div>{{ savedLabel(item.row) }}</div>
                <div v-if="leftLabel(item.row)">{{ leftLabel(item.row) }}</div>
              </div>

              <v-icon icon="mdi-cloud-check-outline" size="16" />
            </template>
          </v-list-item>
        </template>
      </v-autocomplete>

      <ThemeSetSearch />
    </div>

    <!-- Kým server neodpovedal, kostra; „Zatiaľ žiadne série“ až po odpovedi. -->
    <PageSkeleton v-if="page.initial" kind="cards" />

    <LoadFailed v-else-if="page.error" :loading="page.loading" :message="error" @retry="page.run()" />

    <template v-else-if="enabled">
      <div class="d-flex align-center flex-wrap ga-2">
        <div class="text-title-large font-weight-medium me-2">{{ t('themes.mine') }}</div>

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
        v-if="mine.length === 0 && !view.downloaded"
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
            <span class="text-body-large font-weight-medium">{{ row.theme }}</span>

            <v-icon
              v-if="row.followed"
              color="amber-darken-2"
              icon="mdi-star"
              size="small"
              :title="t('themes.followed')"
            />
          </div>

          <div class="text-body-small text-medium-emphasis">
            {{ row.year_from }}–{{ row.year_to }} · {{ t('themes.setsInTheme', { count: row.set_count }) }}
          </div>

          <div class="text-body-medium mt-2">
            <template v-if="row.owned">
              {{ t('collection.setsPlural', row.owned, { named: { count: row.owned } }) }}
              {{ t('themes.inCollection') }}
            </template>

            <span v-else class="text-medium-emphasis">{{ t('themes.noSetYet') }}</span>
          </div>

          <SeriesBar
            v-if="row.set_count > 0"
            class="mt-auto"
            :complete="row.complete"
            :owned="row.owned"
            :total="row.set_count"
          />

          <!-- Uložené ročníky, ako vo výbere série. -->
          <div v-if="savedLabel(row)" class="d-flex align-center ga-1 text-body-small text-medium-emphasis">
            <v-icon icon="mdi-cloud-check-outline" size="14" />
            <span>{{ savedLabel(row) }}</span>
            <span v-if="leftLabel(row)">· {{ leftLabel(row) }}</span>
          </div>
        </v-card>
      </CardGrid>
    </template>
  </div>
</template>
