<script setup lang="ts">
  import type { CmfMember, ThemeWave, ThemeYear } from '@/api/types'
  /**
   * Jedna téma po rokoch: „2025 · mám 5 z 17“ a sety zvoleného roku.
   *
   * Roky sú z Brickset zadarmo. Sety roka (vlna) sú jedno volanie, prvýkrát
   * pri otvorení roka; potom sa berú z databázy. Kým vlna nie je stiahnutá,
   * počet vlastnených pri roku je odhad (≈). Odhad ostane aj pri starej vlne,
   * v ktorej chýba môj set (`exact` vlny); ten je potom medzi setmi roka.
   */
  import { computed, onMounted, ref, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useRoute, useRouter } from 'vue-router'
  import { api, errorMessage } from '@/api/client'
  import CardGrid from '@/components/CardGrid.vue'
  import GhostCard from '@/components/GhostCard.vue'
  import LoadFailed from '@/components/LoadFailed.vue'
  import PageSkeleton from '@/components/PageSkeleton.vue'
  import SetImage from '@/components/SetImage.vue'
  import { usePageLoad } from '@/composables/usePageLoad'
  import { useCollectionStore } from '@/stores/collection'
  import { useProfileStore } from '@/stores/preferences'
  import { imageSrc } from '@/utils/imageSrc'

  type Show = 'all' | 'owned' | 'missing'

  const { t } = useI18n()
  const route = useRoute()
  const router = useRouter()

  const profile = useProfileStore()
  const collection = useCollectionStore()

  const theme = computed(() => String(route.params.theme))

  /** Témy uložené medzi moje, aj bez setu; pri účte, platí aj na telefóne. */
  const followed = computed<string[]>(() => {
    const raw = profile.get('themes')?.followed
    return Array.isArray(raw) ? raw.filter((x): x is string => typeof x === 'string') : []
  })
  const isFollowed = computed(() => followed.value.includes(theme.value))

  function toggleFollow (): void {
    const next = isFollowed.value
      ? followed.value.filter(x => x !== theme.value)
      : [...followed.value, theme.value]
    profile.save('themes', next.length > 0 ? { followed: next } : {})
    // Číslo pri Témach v ponuke sa má hneď pohnúť.
    setTimeout(() => collection.loadDashboard(), 1000)
  }
  const years = ref<ThemeYear[]>([])
  const year = ref<number | null>(null)
  const wave = ref<ThemeWave | null>(null)
  const show = ref<Show>('all')

  const shown = computed<CmfMember[]>(() => (wave.value?.members ?? []).filter(m =>
    show.value === 'all' || (show.value === 'owned' ? m.owned > 0 : m.owned === 0),
  ))
  const missingCount = computed(() => (wave.value ? wave.value.total - wave.value.owned : 0))

  /** Rok z adresy, inak najnovší, z ktorého niečo mám, inak najnovší vydaný. */
  function defaultYear (): number | null {
    const fromRoute = Number(route.query.year)
    if (years.value.some(y => y.year === fromRoute)) return fromRoute
    const now = new Date().getFullYear()
    return years.value.find(y => y.owned > 0)?.year
      ?? years.value.find(y => y.year <= now)?.year
      ?? years.value[0]?.year
      ?? null
  }

  /** Text chyby rokov a vlny, pre LoadFailed. */
  const yearsError = ref<string | null>(null)
  const waveError = ref<string | null>(null)

  async function loadYears (): Promise<boolean> {
    const { data, error: err } = await api.GET('/themes/years', { params: { query: { theme: theme.value } } })
    if (err || !data) {
      yearsError.value = errorMessage(err, t('themes.loadFailed'))
      return false
    }
    yearsError.value = null
    years.value = data
    if (year.value === null) year.value = defaultYear()
    return true
  }

  /** Stiahnuť znova (tlačidlo pri vlne): jedno volanie Brickset, len na klik. */
  let forceNext = false

  async function fetchWave (): Promise<boolean> {
    if (year.value === null) return true
    const force = forceNext
    forceNext = false
    const { data, error: err } = await api.GET('/themes/wave', {
      params: { query: { theme: theme.value, year: year.value, force } },
    })
    if (err || !data) {
      waveError.value = errorMessage(err, t('themes.loadFailed'))
      return false
    }
    waveError.value = null
    wave.value = data
    // Po stiahnutí vlny je počet pri roku presný, kým v nej nechýba môj set
    // (stará vlna, ktorú sa nepodarilo stiahnuť znova): vtedy ostane odhad.
    // Rok je odteraz uložený, značka sa ukáže hneď, nie až po ďalšom načítaní.
    years.value = years.value.map(y => (y.year === data.year
      ? { ...y, owned: data.owned, set_count: data.total, exact: data.exact, downloaded: true }
      : y))
    return true
  }

  /*
   * Roky a sety roka: prvé načítanie kostra, Obnoviť stránku nad starými
   * údajmi (usePageLoad). Iný rok či téma sú iný obsah, tie začnú kostrou.
   */
  const yearsPage = usePageLoad(loadYears)
  const wavePage = usePageLoad(fetchWave)

  function refreshWave (): void {
    forceNext = true
    wavePage.run()
  }

  async function onOwned (): Promise<void> {
    await wavePage.run()
  }

  watch(year, value => {
    if (value === null) return
    router.replace({ query: { ...route.query, year: String(value) } })
    show.value = 'all'
    wavePage.reset()
    wavePage.run()
  })

  watch(theme, () => {
    years.value = []
    year.value = null
    wave.value = null
    yearsPage.reset()
    wavePage.reset()
    yearsPage.run()
  })

  onMounted(() => {
    profile.load()
    yearsPage.run()
  })
</script>

<template>
  <div class="d-flex flex-column ga-4">
    <div>
      <v-btn prepend-icon="mdi-arrow-left" size="small" :to="{ name: 'themes' }" variant="text">
        {{ t('themes.back') }}
      </v-btn>
    </div>

    <div class="d-flex align-center flex-wrap ga-2">
      <div class="text-headline-small">{{ theme }}</div>

      <v-btn
        :color="isFollowed ? 'amber-darken-2' : undefined"
        :prepend-icon="isFollowed ? 'mdi-star' : 'mdi-star-outline'"
        size="small"
        :variant="isFollowed ? 'tonal' : 'outlined'"
        @click="toggleFollow"
      >{{ isFollowed ? t('themes.followed') : t('themes.follow') }}</v-btn>
    </div>

    <!-- Kým server neodpovedal, kostra rokov aj setov (usePageLoad). -->
    <v-skeleton-loader v-if="yearsPage.initial" class="year-skeleton" type="chip@8" />

    <LoadFailed
      v-else-if="yearsPage.error"
      :loading="yearsPage.loading"
      :message="yearsError"
      @retry="yearsPage.run()"
    />

    <!-- Roky témy; pri každom koľko z nich mám. -->
    <v-slide-group v-else v-model="year" mandatory show-arrows>
      <v-slide-group-item v-for="row in years" :key="row.year" v-slot="{ isSelected, toggle }" :value="row.year">
        <v-card
          border
          class="ma-1 pa-3 text-center year-card"
          :class="{ 'year-card--downloaded': row.downloaded && !isSelected }"
          :color="isSelected ? 'primary' : undefined"
          flat
          :variant="isSelected ? 'tonal' : 'outlined'"
          @click="toggle"
        >
          <!-- Stiahnutý rok: jemný odtieň a ikonka v rohu, otvorí sa bez volania Brickset. -->
          <v-icon
            v-if="row.downloaded"
            class="year-card__mark"
            icon="mdi-cloud-check-outline"
            size="14"
            :title="t('themes.savedYear')"
          />

          <div class="text-body-large font-weight-medium">{{ row.year }}</div>

          <div class="text-body-small">
            <span v-if="!row.exact && row.owned">≈ </span>{{ t('dashboard.seriesOf', { owned: row.owned, total: row.set_count }) }}
          </div>
        </v-card>
      </v-slide-group-item>
    </v-slide-group>

    <PageSkeleton v-if="!yearsPage.error && wavePage.initial" kind="cards" />

    <LoadFailed
      v-else-if="!yearsPage.error && wavePage.error"
      :loading="wavePage.loading"
      :message="waveError"
      @retry="wavePage.run()"
    />

    <template v-else-if="wave">
      <div class="d-flex align-center flex-wrap ga-3">
        <div>
          <span class="text-body-large font-weight-medium">
            <span v-if="!wave.exact">≈ </span>{{ t('dashboard.seriesOf', { owned: wave.owned, total: wave.total }) }}
          </span>

          <v-chip
            v-if="missingCount === 0 && wave.total > 0"
            class="ms-2"
            color="positive"
            label
            prepend-icon="mdi-check"
            size="small"
            variant="tonal"
          >{{ t('dashboard.seriesDone') }}</v-chip>
        </div>

        <v-progress-linear
          :color="missingCount === 0 ? 'positive' : 'warning'"
          height="6"
          :model-value="(wave.owned / Math.max(wave.total, 1)) * 100"
          rounded
          style="max-width: 320px"
        />

        <v-spacer />

        <v-btn-toggle v-model="show" density="comfortable" mandatory variant="outlined">
          <v-btn value="all">{{ t('minifigs.showAll') }} · {{ wave.total }}</v-btn>
          <v-btn value="owned">{{ t('minifigs.showOwned') }} · {{ wave.owned }}</v-btn>
          <v-btn value="missing">{{ t('minifigs.showMissing') }} · {{ missingCount }}</v-btn>
        </v-btn-toggle>

        <v-btn
          prepend-icon="mdi-refresh"
          size="small"
          :title="t('themes.refreshHint')"
          variant="text"
          @click="refreshWave"
        >{{ t('themes.refresh') }}</v-btn>
      </div>

      <CardGrid>
        <template v-for="member in shown" :key="member.catalog.catalog_num">
          <v-card
            v-if="member.owned > 0"
            border
            class="h-100 d-flex flex-column"
            flat
            :to="{ name: 'set-detail', params: { num: member.catalog.catalog_num } }"
          >
            <SetImage :alt="member.catalog.name" rounded="0" :size="132" :src="imageSrc(member.catalog.image_url) ?? undefined" />

            <div class="pa-3 d-flex flex-column ga-1 flex-grow-1">
              <div class="text-body-large font-weight-medium text-truncate">{{ member.catalog.name }}</div>
              <div class="text-body-small text-medium-emphasis">{{ member.catalog.catalog_num }}</div>

              <div class="d-flex ga-1 mt-1">
                <v-chip
                  color="positive"
                  label
                  prepend-icon="mdi-check"
                  size="x-small"
                  variant="tonal"
                >
                  {{ t('minifigs.have') }}
                </v-chip>

                <v-chip v-if="member.owned > 1" label size="x-small" variant="tonal">× {{ member.owned }}</v-chip>
              </div>
            </div>
          </v-card>

          <GhostCard
            v-else
            :catalog="member.catalog"
            :missing-label="t('themes.missing')"
            :wanted="member.wanted"
            @owned="onOwned"
          />
        </template>
      </CardGrid>
    </template>
  </div>
</template>

<style scoped>
.year-card {
  min-width: 96px;
  position: relative;
}

.year-card--downloaded {
  background: rgba(var(--v-theme-on-surface), 0.07);
}

.year-card__mark {
  position: absolute;
  top: 4px;
  right: 4px;
  opacity: 0.7;
}

/* Kostra rokov v riadku ako karty rokov, nie pod sebou. */
.year-skeleton {
  background: transparent;
}
</style>
