<script setup lang="ts">
  /**
   * Karta „Čo ešte z neho postavíš · N“: alternatívne stavby (MOC) z dielikov
   * setu podľa Rebrickable. Zoznam sa stiahne až po rozbalení karty (server
   * ho drží raz na set, 90 dní). Počet v nadpise je z uloženého zoznamu,
   * kým ho nikto nestiahol, nadpis je bez čísla.
   */
  import type { SetAlternate } from '@/api/types'
  import { computed, onMounted, ref, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { api, errorMessage } from '@/api/client'
  import CardGrid from '@/components/CardGrid.vue'
  import LoadFailed from '@/components/LoadFailed.vue'
  import SetImage from '@/components/SetImage.vue'
  import SourceCredit from '@/components/SourceCredit.vue'
  import { count } from '@/utils/format'
  import { imageSrc } from '@/utils/imageSrc'

  const props = defineProps<{ num: string }>()

  const { t } = useI18n()

  const panel = ref<string | null>(null)
  const state = ref<'idle' | 'loading' | 'failed' | 'ready'>('idle')
  const error = ref<string | null>(null)
  const builds = ref<SetAlternate[]>([])
  /** Počet z uloženého zoznamu, bez volania von. */
  const known = ref<number | null>(null)

  async function loadSummary (): Promise<void> {
    const { data } = await api.GET('/catalog/{num}/parts-summary', { params: { path: { num: props.num } } })
    known.value = data?.alternates ?? null
  }

  async function load (): Promise<void> {
    state.value = 'loading'
    const { data, error: err } = await api.GET('/catalog/{num}/alternates', { params: { path: { num: props.num } } })
    if (err || !data) {
      error.value = errorMessage(err, t('common.loadFailed'))
      state.value = 'failed'
      return
    }
    builds.value = data.alternates ?? []
    known.value = data.fetched_at ? builds.value.length : known.value
    state.value = 'ready'
  }

  watch(panel, value => {
    if (value && state.value === 'idle') load()
  })
  watch(() => props.num, () => {
    state.value = 'idle'
    builds.value = []
    known.value = null
    loadSummary()
    if (panel.value) load()
  })
  onMounted(loadSummary)

  const title = computed(() =>
    known.value === null ? t('alternates.title') : t('alternates.titleCount', { count: count(known.value) }),
  )
</script>

<template>
  <v-expansion-panels v-model="panel" flat>
    <v-expansion-panel class="border" rounded="lg" value="alternates">
      <v-expansion-panel-title>
        <span class="text-title-large font-weight-medium">{{ title }}</span>
      </v-expansion-panel-title>

      <v-expansion-panel-text>
        <v-skeleton-loader
          v-if="state === 'loading' || state === 'idle'"
          data-test="alternates-loading"
          type="list-item-avatar-two-line@3"
        />

        <LoadFailed v-else-if="state === 'failed'" :message="error" @retry="load" />

        <v-empty-state
          v-else-if="builds.length === 0"
          data-test="alternates-empty"
          icon="mdi-shape-outline"
          :title="t('alternates.empty')"
        />

        <div v-else class="d-flex flex-column ga-3">
          <CardGrid :min="200">
            <v-card
              v-for="build in builds"
              :key="build.set_num"
              :aria-label="`${build.name}: ${t('alternates.open')}`"
              border
              data-test="alternate"
              flat
              :href="build.url ?? undefined"
              rel="noopener"
              target="_blank"
            >
              <SetImage :alt="build.name" rounded="0" :size="132" :src="imageSrc(build.image_url) ?? undefined" />

              <div class="pa-3">
                <div class="text-body-large font-weight-medium text-truncate">{{ build.name }}</div>

                <div class="text-body-small text-medium-emphasis text-truncate">
                  <template v-if="build.designer_name">{{ t('alternates.by', { name: build.designer_name }) }} · </template>

                  <template v-if="build.num_parts">
                    {{ t('collection.partsPlural', build.num_parts, { named: { count: count(build.num_parts) } }) }}
                  </template>
                </div>
              </div>
            </v-card>
          </CardGrid>

          <SourceCredit href="https://rebrickable.com" :text="t('alternates.credit')" />
        </div>
      </v-expansion-panel-text>
    </v-expansion-panel>
  </v-expansion-panels>
</template>
