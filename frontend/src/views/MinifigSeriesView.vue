<script setup lang="ts">
  import type { CmfMember, CmfSeries } from '@/api/types'
  import type { MemberSort } from '@/utils/seriesList'
  import type { SortState } from '@/utils/tableSort'
  /**
   * Jedna zberateľská séria: všetky figúrky, ktoré mám a ktoré nie.
   *
   * Vlastnená figúrka vedie do detailu. Chýbajúca je prerušovaná karta,
   * z ktorej ide rovno do Chcem, alebo „Mám ju“, keď ju už kúpil.
   *
   * Zbierka figúrky zo sérií neukazuje, takže nerozbalené sáčky, predané
   * figúrky a obnova cien celej série sú v detaile série (`/set/:num`).
   */
  import { computed, onMounted, ref, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useRoute } from 'vue-router'
  import { api, errorMessage } from '@/api/client'
  import CardGrid from '@/components/CardGrid.vue'
  import GhostActions from '@/components/GhostActions.vue'
  import GhostCard from '@/components/GhostCard.vue'
  import LoadFailed from '@/components/LoadFailed.vue'
  import PageSkeleton from '@/components/PageSkeleton.vue'
  import SeriesBar from '@/components/SeriesBar.vue'
  import SeriesPurchaseDialog from '@/components/SeriesPurchaseDialog.vue'
  import SetImage from '@/components/SetImage.vue'
  import SortHeader from '@/components/SortHeader.vue'
  import { useMinifigsView } from '@/composables/useMinifigsView'
  import { usePageLoad } from '@/composables/usePageLoad'
  import { imageSrc } from '@/utils/imageSrc'
  import { memberDefaultDir, memberShowFrom, sortMembers } from '@/utils/seriesList'
  import { headerDir, nextSort } from '@/utils/tableSort'

  const { t } = useI18n()
  const route = useRoute()

  const num = computed(() => String(route.params.num))
  const series = ref<CmfSeries | null>(null)
  const members = ref<CmfMember[]>([])
  /** Z Prehľadu („Ukázať chýbajúce“) prichádza `?show=missing`. */
  const show = ref(memberShowFrom(route.query.show))
  const allOpen = ref(false)
  /** Karty alebo tabuľka, voľba pri účte (`preferences.minifigs.series`). */
  const { tableView, setView } = useMinifigsView('series')

  /** Text chyby (napríklad neznáma séria), pre LoadFailed. */
  const error = ref<string | null>(null)

  async function load (): Promise<boolean> {
    const { data, error: err } = await api.GET('/minifigs/series/{series_num}', {
      params: { path: { series_num: num.value } },
    })
    if (err || !data) {
      error.value = errorMessage(err, t('minifigs.loadFailed'))
      return false
    }
    error.value = null
    series.value = data.series
    members.value = data.members
    return true
  }

  /** Prvé načítanie kostra, po kúpe a Obnoviť stránku nad starými kartami. */
  const page = usePageLoad(load)

  const ownedCount = computed(() => members.value.filter(m => m.owned > 0).length)
  const missingCount = computed(() => members.value.length - ownedCount.value)

  /**
   * Zoradenie klikom na hlavičku tabuľky, platí aj pre karty. Pamätá sa
   * len kým je stránka otvorená; predvolene podľa čísla, ako zo servera.
   */
  const order = ref<SortState<MemberSort>>({ sort: 'number', dir: null })
  const COLUMNS: Array<{ key: MemberSort, title: string, class?: string }> = [
    { key: 'number', title: 'minifigs.colNumber' },
    { key: 'name', title: 'minifigs.colFigure' },
    { key: 'state', title: 'minifigs.colState' },
    { key: 'wanted', title: 'minifigs.colWish', class: 'text-center' },
  ]

  const shown = computed(() => sortMembers(
    members.value.filter(m =>
      show.value === 'all' || (show.value === 'owned' ? m.owned > 0 : m.owned === 0),
    ),
    order.value.sort,
    order.value.dir ?? memberDefaultDir(order.value.sort),
  ))

  // Iná séria: staré karty k nej nepatria, znova kostra.
  watch(num, () => {
    page.reset()
    page.run()
  })
  onMounted(() => page.run())
</script>

<template>
  <div class="d-flex flex-column ga-4">
    <div>
      <v-btn
        prepend-icon="mdi-arrow-left"
        size="small"
        :to="{ name: 'minifigs', query: series && series.category !== 'minifigs' ? { cat: series.category } : {} }"
        variant="text"
      >
        {{ t('minifigs.back') }}
      </v-btn>
    </div>

    <!-- Kostra hlavičky a kariet, kým server neodpovedal (usePageLoad). -->
    <template v-if="page.initial">
      <v-card border flat>
        <v-skeleton-loader type="list-item-avatar-three-line" />
      </v-card>

      <PageSkeleton :count="12" kind="cards" />
    </template>

    <LoadFailed v-else-if="page.error" :loading="page.loading" :message="error" @retry="page.run()" />

    <template v-else-if="series">
      <v-card border class="pa-4" flat>
        <div class="d-flex align-center ga-4 flex-wrap">
          <SetImage
            :alt="series.name"
            rounded="md"
            :size="88"
            :src="imageSrc(series.image_url) ?? undefined"
            style="width: 88px"
          />

          <div class="flex-grow-1" style="min-width: 220px">
            <div class="text-title-large font-weight-medium">{{ series.name }}</div>

            <div class="text-body-medium text-medium-emphasis">
              {{ series.series_num }}<span v-if="series.year"> · {{ series.year }}</span>
            </div>

            <div class="d-flex align-center ga-2 mt-2">
              <span class="text-body-medium font-weight-medium">
                {{ t('dashboard.seriesOf', { owned: ownedCount, total: series.total }) }}
              </span>

              <v-chip
                v-if="missingCount === 0"
                color="positive"
                label
                prepend-icon="mdi-check"
                size="small"
                variant="tonal"
              >{{ t('dashboard.seriesDone') }}</v-chip>

              <span v-else class="text-body-medium missing-count">
                · {{ t('dashboard.seriesMissingPlural', missingCount, { named: { count: missingCount } }) }}
              </span>
            </div>

            <SeriesBar
              class="mt-2"
              :owned="ownedCount"
              style="max-width: 420px"
              :total="series.total"
            />

            <div class="d-flex align-center flex-wrap ga-1 mt-2">
              <v-chip v-if="series.duplicates" label size="small" variant="tonal">
                {{ t('minifigs.duplicatesPlural', series.duplicates, { named: { count: series.duplicates } }) }}
              </v-chip>

              <v-chip v-if="series.sealed_bags" label size="small" variant="tonal">
                {{ t('minifigs.bagsPlural', series.sealed_bags, { named: { count: series.sealed_bags } }) }}
              </v-chip>

              <!-- Všetky kusy série vrátane sáčkov a predaných, aj obnova cien. -->
              <v-btn
                prepend-icon="mdi-format-list-bulleted"
                size="small"
                :title="t('minifigs.seriesPiecesHint')"
                :to="{ name: 'set-detail', params: { num: series.series_num ?? num }, query: { from: 'minifigs' } }"
                variant="text"
              >{{ t('minifigs.seriesPieces') }}</v-btn>
            </div>
          </div>
        </div>
      </v-card>

      <div class="d-flex align-center flex-wrap ga-2">
        <v-btn-toggle
          v-model="show"
          density="comfortable"
          mandatory
          variant="outlined"
        >
          <v-btn value="all">{{ t('minifigs.showAll') }} · {{ members.length }}</v-btn>
          <v-btn value="owned">{{ t('minifigs.showOwned') }} · {{ ownedCount }}</v-btn>
          <v-btn value="missing">{{ t('minifigs.showMissing') }} · {{ missingCount }}</v-btn>
        </v-btn-toggle>

        <v-btn-toggle
          density="comfortable"
          mandatory
          :model-value="tableView ? 'table' : 'cards'"
          variant="outlined"
          @update:model-value="value => setView(value === 'table')"
        >
          <v-btn icon="mdi-view-module-outline" :title="t('collection.viewCards')" value="cards" />
          <v-btn icon="mdi-view-headline" :title="t('collection.viewTable')" value="table" />
        </v-btn-toggle>

        <v-spacer />

        <!-- Celá séria naraz za jednu sumu, rozpočíta sa na figúrky. -->
        <v-btn
          color="primary"
          prepend-icon="mdi-check-all"
          variant="flat"
          @click="allOpen = true"
        >{{ missingCount > 0 ? t('purchase.haveAll') : t('purchase.haveAllAgain') }}</v-btn>
      </div>

      <SeriesPurchaseDialog v-model="allOpen" :members="members" :series="series" @saved="page.run()" />

      <v-card v-if="tableView" border class="minifigs-table" flat>
        <v-table density="comfortable" hover>
          <thead>
            <tr>
              <th class="minifigs-table__photo" />

              <th v-for="column in COLUMNS" :key="column.key" :class="column.class">
                <SortHeader
                  :dir="headerDir(column.key, order, memberDefaultDir)"
                  :title="t(column.title)"
                  @sort="order = nextSort(column.key, order, memberDefaultDir)"
                />
              </th>

              <th />
            </tr>
          </thead>

          <tbody>
            <tr
              v-for="member in shown"
              :key="member.catalog.catalog_num"
              :class="{ 'minifigs-table__row--missing': member.owned === 0 }"
            >
              <td class="minifigs-table__photo">
                <SetImage
                  :alt="member.catalog.name"
                  class="minifigs-table__image"
                  rounded="sm"
                  :size="64"
                  :src="imageSrc(member.catalog.image_url) ?? undefined"
                />
              </td>

              <td class="text-body-medium text-medium-emphasis text-no-wrap">{{ member.catalog.catalog_num }}</td>

              <td>
                <RouterLink
                  class="minifigs-table__name"
                  :to="{ name: 'set-detail', params: { num: member.catalog.catalog_num }, query: { from: 'minifigs' } }"
                >{{ member.catalog.name }}</RouterLink>
              </td>

              <td class="text-no-wrap">
                <div v-if="member.owned > 0" class="d-flex ga-1">
                  <v-chip
                    color="positive"
                    label
                    prepend-icon="mdi-check"
                    size="x-small"
                    variant="tonal"
                  >{{ t('minifigs.have') }}</v-chip>

                  <v-chip v-if="member.owned > 1" label size="x-small" variant="tonal">× {{ member.owned }}</v-chip>
                </div>

                <v-chip v-else label size="x-small" variant="outlined">{{ t('minifigs.missing') }}</v-chip>
              </td>

              <td class="text-center">
                <v-icon
                  v-if="member.wanted"
                  color="primary"
                  data-test="wanted"
                  icon="mdi-heart"
                  size="small"
                  :title="t('filters.inWish')"
                />
              </td>

              <td class="text-end text-no-wrap">
                <v-btn
                  v-if="member.owned > 0"
                  icon="mdi-chevron-right"
                  size="small"
                  :title="t('minifigs.openDetail')"
                  :to="{ name: 'set-detail', params: { num: member.catalog.catalog_num }, query: { from: 'minifigs' } }"
                  variant="text"
                />

                <GhostActions
                  v-else
                  :catalog="member.catalog"
                  compact
                  :wanted="member.wanted"
                  @owned="page.run()"
                  @wished="member.wanted = true"
                />
              </td>
            </tr>
          </tbody>
        </v-table>
      </v-card>

      <CardGrid v-else>
        <template v-for="member in shown" :key="member.catalog.catalog_num">
          <v-card
            v-if="member.owned > 0"
            border
            class="h-100 d-flex flex-column"
            flat
            :to="{ name: 'set-detail', params: { num: member.catalog.catalog_num }, query: { from: 'minifigs' } }"
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

          <GhostCard v-else :catalog="member.catalog" :wanted="member.wanted" @owned="page.run()" />
        </template>
      </CardGrid>
    </template>
  </div>
</template>

<style scoped>
/* Tabuľka série: riadky ako v Chcem a Zbierke, na telefóne sa posúva do strany. */
.minifigs-table {
  overflow-x: auto;
}

.minifigs-table__photo {
  width: 104px;
  padding-top: 6px !important;
  padding-bottom: 6px !important;
}

.minifigs-table__name {
  color: inherit;
  font-weight: 500;
  text-decoration: none;
}

.minifigs-table__name:hover {
  text-decoration: underline;
}

/* Chýbajúca figúrka tlmene, ako prerušovaná karta. */
.minifigs-table__row--missing .minifigs-table__image {
  filter: grayscale(0.6);
  opacity: 0.6;
}

/* Žltá z témy je na bielej nečitateľná, text potrebuje tmavší odtieň. */
.missing-count {
  color: #B25E00;
}

.v-theme--dark .missing-count {
  color: #FFB74D;
}
</style>
