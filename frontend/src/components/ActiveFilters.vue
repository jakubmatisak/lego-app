<script setup lang="ts">
  /**
   * Aktívne filtre ako čipy s krížikom a uložené pohľady.
   * Z čipu je vidno, čo je zapnuté, aj keď je panel filtrov zavretý.
   *
   * Starší pohľad môže mať filter figúrok zo sérií (séria, nekompletné…),
   * ktorý Zbierka už nepozná. Čip je označený a po kliknutí oznámenie
   * ponúkne Figúrky; inak by pohľad potichu ukázal celú zbierku.
   */
  import type { SavedView } from '@/api/types'
  import type { ListKey } from '@/stores/filters'
  import { computed, ref } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useRouter } from 'vue-router'
  import { useFilterLabels } from '@/composables/useFilterLabels'
  import { LIST_KEYS, useFilterStore } from '@/stores/filters'
  import { useNotifyStore } from '@/stores/notify'
  import { exactMoney, shortDate } from '@/utils/format'
  import { figuresRoute, hasFigureFilters } from '@/utils/series'

  const emit = defineEmits<{ view: [group: string | null] }>()
  const props = defineProps<{ group: string }>()

  const { t } = useI18n()
  const router = useRouter()
  const notify = useNotifyStore()
  const store = useFilterStore()
  const f = store.filters

  interface Chip { key: string, label: string, remove: () => void }

  const { optionLabel } = useFilterLabels()

  /** „od – do“ s tromi bodkami pri chýbajúcej hranici. */
  function range (low: string | null, high: string | null): string {
    return `${low ?? '…'} – ${high ?? '…'}`
  }

  function money (value: number | null): string | null {
    return value === null ? null : exactMoney(value)
  }

  const chips = computed<Chip[]>(() => {
    const out: Chip[] = []
    if (f.q.trim()) out.push({ key: 'q', label: `„${f.q.trim()}“`, remove: () => (f.q = '') })
    for (const id of f.category) {
      out.push({
        key: `category:${id}`,
        label: store.categoryById.get(id)?.name ?? `#${id}`,
        remove: () => store.toggleCategory(id),
      })
    }
    for (const key of LIST_KEYS) {
      for (const value of f[key]) {
        out.push({ key: `${key}:${value}`, label: optionLabel(key, value), remove: () => store.toggle(key as ListKey, value) })
      }
    }
    for (const id of f.imported) {
      out.push({
        key: `imported:${id}`,
        label: t('filters.importedChip', { name: optionLabel('imported', String(id)) }),
        remove: () => store.toggleId('imported', id),
      })
    }
    if (f.bought_from !== null || f.bought_to !== null) {
      out.push({
        key: 'bought',
        label: t('filters.boughtChip', {
          range: range(f.bought_from ? shortDate(f.bought_from) : null, f.bought_to ? shortDate(f.bought_to) : null),
        }),
        remove: () => {
          f.bought_from = null
          f.bought_to = null
        },
      })
    }
    if (f.price_min !== null || f.price_max !== null) {
      out.push({
        key: 'price_range',
        label: t('filters.priceChip', { range: range(money(f.price_min), money(f.price_max)) }),
        remove: () => {
          f.price_min = null
          f.price_max = null
        },
      })
    }
    if (f.value_min !== null || f.value_max !== null) {
      out.push({
        key: 'value_range',
        label: t('filters.valueChip', { range: range(money(f.value_min), money(f.value_max)) }),
        remove: () => {
          f.value_min = null
          f.value_max = null
        },
      })
    }
    if (f.rating_min !== null) {
      out.push({
        key: 'rating',
        label: t('filters.ratingChip', { value: String(f.rating_min).replace('.', ',') }),
        remove: () => (f.rating_min = null),
      })
    }
    if (f.retired_recent) {
      out.push({ key: 'retired_recent', label: t('filters.retiredRecent'), remove: () => (f.retired_recent = false) })
    }
    if (f.year_from !== null || f.year_to !== null) {
      out.push({
        key: 'year',
        label: t('filters.yearRange', { from: f.year_from ?? '…', to: f.year_to ?? '…' }),
        remove: () => {
          f.year_from = null
          f.year_to = null
        },
      })
    }
    if (f.retired !== null) {
      out.push({
        key: 'retired',
        label: t('filters.retiredChip', { value: f.retired ? t('filters.retiredYes') : t('filters.retiredNo') }),
        remove: () => (f.retired = null),
      })
    }
    if (f.duplicates) out.push({ key: 'duplicates', label: t('filters.duplicates'), remove: () => (f.duplicates = false) })
    return out
  })

  const saveOpen = ref(false)
  const viewName = ref('')

  async function save (): Promise<void> {
    const name = viewName.value.trim()
    if (!name) return
    // Uložený pohľad si pamätá aj zoskupenie (karty setov alebo každý kus).
    if (await store.saveView(name, { group: props.group })) {
      saveOpen.value = false
      viewName.value = ''
    }
  }

  function figures (view: SavedView): boolean {
    return hasFigureFilters(view.query ?? {})
  }

  function apply (viewId: number): void {
    const view = store.views.find(v => v.id === viewId)
    if (!view) return
    emit('view', store.applyView(view))
    const target = figuresRoute(view.query ?? {})
    if (target) {
      notify.info(t('filters.viewFigures', { name: view.name }), {
        label: t('collection.openMinifigs'),
        run: () => {
          router.push(target)
        },
      })
    }
  }
</script>

<template>
  <div class="d-flex flex-column ga-2">
    <div v-if="chips.length > 0" class="d-flex flex-wrap ga-1 align-center">
      <v-chip
        v-for="chip in chips"
        :key="chip.key"
        closable
        color="primary"
        label
        size="small"
        variant="tonal"
        @click:close="chip.remove()"
      >{{ chip.label }}</v-chip>

      <v-btn size="small" variant="text" @click="store.clear()">{{ t('filters.clear') }}</v-btn>

      <v-btn
        prepend-icon="mdi-bookmark-plus-outline"
        size="small"
        variant="text"
        @click="saveOpen = true"
      >{{ t('filters.saveView') }}</v-btn>
    </div>

    <div v-if="store.views.length > 0" class="d-flex flex-wrap ga-1 align-center">
      <span class="text-caption text-medium-emphasis me-1">{{ t('filters.views') }}</span>

      <v-chip
        v-for="view in store.views"
        :key="view.id"
        closable
        :close-label="t('filters.deleteView')"
        label
        :prepend-icon="figures(view) ? 'mdi-bookmark-off-outline' : 'mdi-bookmark-outline'"
        size="small"
        :title="figures(view) ? t('filters.viewFiguresHint') : undefined"
        variant="outlined"
        @click="apply(view.id)"
        @click:close="store.deleteView(view.id)"
      >{{ view.name }}</v-chip>
    </div>

    <v-dialog v-model="saveOpen" max-width="420">
      <v-card>
        <v-card-title>{{ t('filters.saveView') }}</v-card-title>

        <v-card-text>
          <v-text-field
            v-model="viewName"
            autofocus
            :hint="t('filters.viewNameHint')"
            :label="t('filters.viewName')"
            persistent-hint
            @keyup.enter="save"
          />
        </v-card-text>

        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="saveOpen = false">{{ t('common.cancel') }}</v-btn>

          <v-btn color="primary" :disabled="!viewName.trim()" variant="flat" @click="save">
            {{ t('common.save') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>
