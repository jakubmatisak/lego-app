<script setup lang="ts">
  import type { FacetOption } from '@/api/types'
  import type { ListKey } from '@/stores/filters'
  /**
   * Panel filtrov. Stav drží úložisko filtrov, panel ho len mení.
   *
   * Číslo pri voľbe hovorí, koľko kusov ostane, keď ju pridáš. Voľba s
   * nulou zošedne, ale dá sa zaškrtnúť, keď už vybraná je, dá sa aj odškrtnúť.
   *
   * Voľby len pre figúrky zo sérií (typ, séria, podoba, chýbajúce,
   * nekompletné) tu nie sú: Zbierka ich neukazuje, majú sekciu Figúrky.
   */
  import { computed, ref } from 'vue'
  import { useI18n } from 'vue-i18n'
  import FilterOption from '@/components/FilterOption.vue'
  import FilterRange from '@/components/FilterRange.vue'
  import { useFilterLabels } from '@/composables/useFilterLabels'
  import { useAuthStore } from '@/stores/auth'
  import { NONE, useFilterStore } from '@/stores/filters'
  import { exactMoney, shortDate } from '@/utils/format'

  const emit = defineEmits<{ manage: [] }>()

  const { t } = useI18n()
  const store = useFilterStore()
  const auth = useAuthStore()
  const f = store.filters

  /** Otvorené sekcie. Tie najpoužívanejšie sú otvorené hneď. */
  const open = ref(['categories', 'theme', 'condition'])

  const facets = computed(() => store.facets)

  /** Podtémy pod témou, bez „Bez podtémy“, tá by len zavadzala. */
  function subthemesOf (theme: string): FacetOption[] {
    return (facets.value?.subtheme ?? []).filter(s => s.parent === theme && s.value !== NONE)
  }

  const { optionLabel } = useFilterLabels()

  function label (key: ListKey, option: FacetOption): string {
    return optionLabel(key, option.value)
  }

  function selected (key: ListKey, value: string): boolean {
    return f[key].includes(value)
  }

  const sections = computed(() => [
    { key: 'condition' as const, title: t('filters.condition'), options: facets.value?.condition ?? [] },
    { key: 'purpose' as const, title: t('filters.purpose'), options: facets.value?.purpose ?? [] },
    { key: 'location' as const, title: t('filters.location'), options: facets.value?.location ?? [] },
    // Krabice len keď nejaká je; inak by skupina ukázala len „Bez krabice“.
    ...((facets.value?.box ?? []).some(o => o.value !== NONE)
      ? [{ key: 'box' as const, title: t('filters.box'), options: facets.value?.box ?? [] }]
      : []),
    { key: 'flag' as const, title: t('filters.flags'), options: facets.value?.flag ?? [] },
    // Štítky sú len pri setoch, ktoré už prešli Brickset; prázdna skupina sa neukáže.
    { key: 'tag' as const, title: t('filters.tags'), options: facets.value?.tag ?? [] },
    { key: 'price' as const, title: t('filters.price'), options: facets.value?.price ?? [] },
    // Odhad rastu je z BrickEconomy; bez zdroja cien by bol všade „bez odhadu“.
    ...(auth.can('brickeconomy.prices')
      ? [{ key: 'growth' as const, title: t('filters.growth'), options: facets.value?.growth ?? [] }]
      : []),
    { key: 'source' as const, title: t('filters.source'), options: facets.value?.source ?? [] },
    { key: 'purchase' as const, title: t('filters.purchase'), options: facets.value?.purchase ?? [] },
    // Kanál predaja má zmysel len pri predaných kusoch; prázdna skupina sa neukáže.
    { key: 'channel' as const, title: t('filters.channel'), options: facets.value?.channel ?? [] },
  ])

  /** Skupiny, ktoré sa bez hodnôt neukazujú (štítky, kanál). */
  const HIDE_WHEN_EMPTY = new Set(['tag', 'channel'])

  /** Hodnotenie z Brickset: prah „aspoň“, alebo bez obmedzenia. */
  const ratingModel = computed({
    get: () => (f.rating_min === null ? 'any' : String(f.rating_min)),
    set: (value: string) => {
      f.rating_min = value === 'any' ? null : Number(value)
    },
  })

  function moneyHint (value: string | null | undefined): string | null {
    return value ? exactMoney(value) : null
  }

  function setYear (edge: 'year_from' | 'year_to', raw: string): void {
    const value = raw.trim() === '' ? null : Number(raw)
    f[edge] = value !== null && Number.isFinite(value) ? value : null
  }

  const retiredModel = computed({
    get: () => (f.retired === null ? 'any' : (f.retired ? 'yes' : 'no')),
    set: (value: string) => {
      f.retired = value === 'any' ? null : value === 'yes'
    },
  })
</script>

<template>
  <div class="filter-panel">
    <v-expansion-panels v-model="open" flat multiple variant="accordion">
      <!-- Moje kategórie ---------------------------------------------------->
      <v-expansion-panel value="categories">
        <v-expansion-panel-title>{{ t('filters.categories') }}</v-expansion-panel-title>

        <v-expansion-panel-text>
          <div v-if="(facets?.category ?? []).length === 0" class="text-body-small text-medium-emphasis mb-2">
            {{ t('filters.noCategories') }}
          </div>

          <FilterOption
            v-for="option in facets?.category ?? []"
            :key="option.value"
            :color="option.color"
            :count="option.count"
            :label="option.label"
            :selected="f.category.includes(Number(option.value))"
            @toggle="store.toggleCategory(Number(option.value))"
          />

          <v-btn
            class="mt-1"
            prepend-icon="mdi-tag-multiple-outline"
            size="small"
            variant="text"
            @click="emit('manage')"
          >{{ t('filters.manage') }}</v-btn>
        </v-expansion-panel-text>
      </v-expansion-panel>

      <!-- Téma a podtéma --------------------------------------------------->
      <v-expansion-panel value="theme">
        <v-expansion-panel-title>{{ t('filters.theme') }}</v-expansion-panel-title>

        <v-expansion-panel-text>
          <template v-for="option in facets?.theme ?? []" :key="option.value">
            <FilterOption
              :count="option.count"
              :label="option.label"
              :selected="selected('theme', option.value)"
              @toggle="store.toggle('theme', option.value)"
            />

            <FilterOption
              v-for="sub in subthemesOf(option.value)"
              :key="`${option.value}/${sub.value}`"
              :count="sub.count"
              :label="sub.label"
              nested
              :selected="selected('subtheme', sub.value)"
              @toggle="store.toggle('subtheme', sub.value)"
            />
          </template>
        </v-expansion-panel-text>
      </v-expansion-panel>

      <!-- Kúpa a hodnota: rozsahy a kde kúpené ---------------------------->
      <v-expansion-panel value="purchase">
        <v-expansion-panel-title>{{ t('filters.purchase') }}</v-expansion-panel-title>

        <v-expansion-panel-text class="d-flex flex-column ga-3">
          <div>
            <div class="text-body-small text-medium-emphasis mb-1">{{ t('filters.bought') }}</div>

            <FilterRange
              :from="f.bought_from"
              :high-hint="facets?.bought_max ? shortDate(facets.bought_max) : null"
              :low-hint="facets?.bought_min ? shortDate(facets.bought_min) : null"
              :to="f.bought_to"
              type="date"
              @update:from="f.bought_from = $event as string | null"
              @update:to="f.bought_to = $event as string | null"
            />
          </div>

          <div>
            <div class="text-body-small text-medium-emphasis mb-1">{{ t('filters.purchasePrice') }}</div>

            <FilterRange
              :from="f.price_min"
              :high-hint="moneyHint(facets?.price_high)"
              :low-hint="moneyHint(facets?.price_low)"
              suffix="€"
              :to="f.price_max"
              type="number"
              @update:from="f.price_min = $event as number | null"
              @update:to="f.price_max = $event as number | null"
            />
          </div>

          <div>
            <div class="text-body-small text-medium-emphasis mb-1">{{ t('filters.marketValue') }}</div>

            <FilterRange
              :from="f.value_min"
              :high-hint="moneyHint(facets?.value_high)"
              :low-hint="moneyHint(facets?.value_low)"
              suffix="€"
              :to="f.value_max"
              type="number"
              @update:from="f.value_min = $event as number | null"
              @update:to="f.value_max = $event as number | null"
            />
          </div>

          <div v-if="(facets?.place ?? []).length > 0">
            <div class="text-body-small text-medium-emphasis mb-1">{{ t('filters.place') }}</div>

            <FilterOption
              v-for="option in facets?.place ?? []"
              :key="option.value"
              :count="option.count"
              :label="label('place', option)"
              :selected="selected('place', option.value)"
              @toggle="store.toggle('place', option.value)"
            />
          </div>
        </v-expansion-panel-text>
      </v-expansion-panel>

      <!-- Hodnotenie z Brickset ---------------------------------------------->
      <v-expansion-panel v-if="(facets?.rating ?? []).some(r => r.count > 0)" value="rating">
        <v-expansion-panel-title>{{ t('filters.rating') }}</v-expansion-panel-title>

        <v-expansion-panel-text>
          <v-btn-toggle
            v-model="ratingModel"
            density="compact"
            divided
            mandatory
            variant="outlined"
          >
            <v-btn size="small" value="any">{{ t('filters.ratingAny') }}</v-btn>

            <v-btn v-for="step in facets?.rating ?? []" :key="step.value" size="small" :value="step.value">
              {{ step.value.replace('.', ',') }}+ ({{ step.count }})
            </v-btn>
          </v-btn-toggle>
        </v-expansion-panel-text>
      </v-expansion-panel>

      <!-- Import --------------------------------------------------------------->
      <v-expansion-panel v-if="(facets?.imported ?? []).length > 0" value="imported">
        <v-expansion-panel-title>{{ t('filters.imported') }}</v-expansion-panel-title>

        <v-expansion-panel-text>
          <FilterOption
            v-for="option in facets?.imported ?? []"
            :key="option.value"
            :count="option.count"
            :label="option.label"
            :selected="f.imported.includes(Number(option.value))"
            @toggle="store.toggleId('imported', Number(option.value))"
          />
        </v-expansion-panel-text>
      </v-expansion-panel>

      <!-- Stav, zoznam, umiestnenie, príznaky, cena ------------------------->
      <v-expansion-panel
        v-for="section in sections.filter(item => !HIDE_WHEN_EMPTY.has(item.key) || item.options.length > 0)"
        :key="section.key"
        :value="section.key"
      >
        <v-expansion-panel-title>{{ section.title }}</v-expansion-panel-title>

        <v-expansion-panel-text>
          <FilterOption
            v-for="option in section.options"
            :key="option.value"
            :count="option.count"
            :label="label(section.key, option)"
            :selected="selected(section.key, option.value)"
            @toggle="store.toggle(section.key, option.value)"
          />

          <!-- Duplikáty sú o tom, čo mám, rovnako ako stav kusu. -->
          <template v-if="section.key === 'condition'">
            <v-divider class="my-2" />

            <v-switch
              v-model="f.duplicates"
              class="filter-switch"
              color="primary"
              density="compact"
              hide-details
              :label="`${t('filters.duplicates')} (${facets?.duplicates ?? 0})`"
            />
          </template>
        </v-expansion-panel-text>
      </v-expansion-panel>

      <!-- Rok a stiahnutie ------------------------------------------------->
      <v-expansion-panel value="year">
        <v-expansion-panel-title>{{ t('filters.year') }}</v-expansion-panel-title>

        <v-expansion-panel-text>
          <div class="d-flex ga-2">
            <v-text-field
              density="compact"
              hide-details
              :label="t('filters.from')"
              :model-value="f.year_from ?? ''"
              :placeholder="facets?.year_min ? String(facets.year_min) : ''"
              type="number"
              variant="outlined"
              @update:model-value="setYear('year_from', String($event))"
            />

            <v-text-field
              density="compact"
              hide-details
              :label="t('filters.to')"
              :model-value="f.year_to ?? ''"
              :placeholder="facets?.year_max ? String(facets.year_max) : ''"
              type="number"
              variant="outlined"
              @update:model-value="setYear('year_to', String($event))"
            />
          </div>

          <div class="text-body-small text-medium-emphasis mt-3 mb-1">{{ t('filters.retired') }}</div>

          <v-btn-toggle
            v-model="retiredModel"
            density="compact"
            divided
            mandatory
            variant="outlined"
          >
            <v-btn size="small" value="any">{{ t('filters.retiredAny') }}</v-btn>
            <v-btn size="small" value="yes">{{ t('filters.retiredYes') }} ({{ facets?.retired_yes ?? 0 }})</v-btn>
            <v-btn size="small" value="no">{{ t('filters.retiredNo') }} ({{ facets?.retired_no ?? 0 }})</v-btn>
          </v-btn-toggle>

          <v-switch
            v-model="f.retired_recent"
            class="filter-switch mt-2"
            color="primary"
            density="compact"
            hide-details
            :label="`${t('filters.retiredRecent')} (${facets?.retired_recent ?? 0})`"
          />
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>
  </div>
</template>

<style scoped>
/*
 * Prepínač má stopu širšiu než svoj obal, bez posunu by trčal naľavo od
 * začiarkávatok a popis by mu liezol do stopy. Posun zarovná stopu so
 * štvorčekmi a popis s popismi volieb.
 */
.filter-switch {
  padding-left: 8px;
}

.filter-switch :deep(.v-label) {
  padding-inline-start: 10px;
}

.filter-panel :deep(.v-expansion-panel-title) {
  font-size: 0.875rem;
  font-weight: 500;
  min-height: 44px;
  padding: 8px 12px;
}

.filter-panel :deep(.v-expansion-panel-text__wrapper) {
  padding: 0 12px 12px;
}
</style>
