<script setup lang="ts">
  /**
   * Lišta hromadnej úpravy: počet vybraných, „vybrať všetko“ a akcie. Pred
   * uložením sa server opýta, koľko kusov by sa zmenilo (`dry_run`), a
   * používateľ to potvrdí („Zmeniť umiestnenie 143 kusov na Povala?“). Menia
   * sa len vlastnené kusy; kategória sa zaradí na set.
   *
   * Rozsah je filter Zbierky (bez figúrok zo sérií). Detail série pošle
   * vlastný `query` (`series`), inak by sa figúrky hromadne upraviť nedali.
   */
  import type { Selection } from '@/composables/useSelection'
  import { computed, ref } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { api } from '@/api/client'
  import { CONDITIONS, FLAGS, PURPOSES } from '@/api/types'
  import { useCollectionStore } from '@/stores/collection'
  import { useFilterStore } from '@/stores/filters'
  import { useNotifyStore } from '@/stores/notify'
  import { boxesFor } from '@/utils/place'

  type Action = 'location' | 'box' | 'purpose' | 'condition' | 'flags_add' | 'flags_remove' | 'category_add' | 'category_remove'

  /**
   * `total`: koľko položiek výsledok má; `unit`: karty setov, alebo kusy.
   * `query`: rozsah výberu pre server; bez neho filter Zbierky.
   */
  const props = defineProps<{
    selection: Selection
    total: number
    unit: 'sets' | 'pieces'
    query?: Record<string, unknown>
  }>()
  const emit = defineEmits<{ done: [] }>()

  const { t } = useI18n()
  const collection = useCollectionStore()
  const filters = useFilterStore()
  const notify = useNotifyStore()

  const ACTIONS: Action[] = ['location', 'box', 'purpose', 'condition', 'flags_add', 'flags_remove', 'category_add', 'category_remove']

  const open = ref(false)
  const action = ref<Action>('location')
  const value = ref<string | number | null>(null)
  /** Kde uložené: voľný text s našepkávačom. */
  const location = ref<string | null>('')
  /** Počet kusov a setov, ktoré by sa zmenili; po ňom príde potvrdenie. */
  const preview = ref<{ items: number, sets: number } | null>(null)
  const busy = ref(false)

  const selected = computed(() => props.selection.count(props.total))

  function countLabel (n: number): string {
    return props.unit === 'pieces'
      ? t('collection.piecesPlural', n, { named: { count: n } })
      : t('collection.setsPlural', n, { named: { count: n } })
  }

  const options = computed<Array<{ value: string | number, title: string }>>(() => {
    switch (action.value) {
      case 'purpose': { return [
        ...PURPOSES.map(p => ({ value: p, title: t(`purpose.${p}`) })),
        { value: '', title: t('purpose.none') },
      ] }
      case 'condition': { return CONDITIONS.map(c => ({ value: c, title: t(`condition.${c}`) })) }
      case 'flags_add':
      case 'flags_remove': { return FLAGS.map(f => ({ value: f, title: t(`flag.${f}`) })) }
      case 'category_add':
      case 'category_remove': { return filters.categories.map(c => ({ value: c.id, title: c.name })) }
      default: { return [] }
    }
  })

  const valueTitle = computed(() => {
    if (action.value === 'location' || action.value === 'box') {
      return (location.value ?? '').trim() || t('bulk.nothing')
    }
    return options.value.find(o => o.value === value.value)?.title ?? ''
  })

  function start (next: Action): void {
    action.value = next
    value.value = null
    location.value = ''
    preview.value = null
    open.value = true
    if (next.startsWith('category') && filters.categories.length === 0) filters.loadCategories()
    if ((next === 'location' || next === 'box') && collection.locations.length === 0) collection.loadLocations()
  }

  function changes (): Record<string, unknown> {
    const v = value.value
    switch (action.value) {
      case 'flags_add':
      case 'flags_remove': { return { [action.value]: [v] } }
      case 'location':
      case 'box': { return { [action.value]: (location.value ?? '').trim() } }
      default: { return { [action.value]: v } }
    }
  }

  async function send (dryRun: boolean): Promise<{ items: number, sets: number } | null> {
    const { data, error } = await api.POST('/items/bulk-update', {
      params: { query: (props.query ?? collection.filterQuery()) as never },
      body: { ...props.selection.payload(), changes: changes() as never, dry_run: dryRun },
    })
    if (error || !data) {
      notify.error(error, t('notice.saveFailed'))
      return null
    }
    return data
  }

  const canContinue = computed(() => action.value === 'location' || action.value === 'box' || (value.value !== null && value.value !== undefined))

  async function check (): Promise<void> {
    busy.value = true
    preview.value = await send(true)
    busy.value = false
  }

  async function confirm (): Promise<void> {
    busy.value = true
    const result = await send(false)
    busy.value = false
    if (!result) return
    notify.success(t('bulk.done', { pieces: t('collection.piecesPlural', result.items, { named: { count: result.items } }) }))
    open.value = false
    props.selection.clear()
    emit('done')
  }
</script>

<template>
  <v-card class="bulk-bar pa-2 d-flex align-center flex-wrap ga-2" color="surface-variant" flat>
    <span class="text-body-medium font-weight-medium px-2">
      {{ t('bulk.selected', { what: countLabel(selected) }) }}
    </span>

    <v-btn
      v-if="!selection.all.value"
      size="small"
      variant="text"
      @click="selection.selectAll()"
    >{{ t('bulk.selectAll', { what: countLabel(total) }) }}</v-btn>

    <v-spacer />

    <v-menu>
      <template #activator="{ props: menu }">
        <v-btn
          v-bind="menu"
          color="primary"
          :disabled="selection.empty.value"
          prepend-icon="mdi-pencil-outline"
          size="small"
          variant="flat"
        >{{ t('bulk.change') }}</v-btn>
      </template>

      <v-list density="compact">
        <v-list-item
          v-for="a in ACTIONS"
          :key="a"
          :title="t(`bulk.actions.${a}`)"
          @click="start(a)"
        />
      </v-list>
    </v-menu>

    <v-btn size="small" variant="text" @click="selection.stop()">
      {{ t('common.cancel') }}
    </v-btn>
  </v-card>

  <v-dialog v-model="open" max-width="460">
    <v-card :title="t(`bulk.actions.${action}`)">
      <v-card-text class="d-flex flex-column ga-3">
        <template v-if="!preview">
          <v-combobox
            v-if="action === 'location' || action === 'box'"
            v-model="location"
            clearable
            :hint="t('bulk.locationHint')"
            :items="action === 'box' ? boxesFor(collection.boxes, null) : collection.locations"
            :label="t('bulk.value')"
            persistent-hint
            @update:search="text => location = text"
          />

          <v-select
            v-else
            v-model="value"
            :items="options"
            :label="t('bulk.value')"
          />
        </template>

        <div v-else class="text-body-large">
          {{ t('bulk.confirm', {
            action: t(`bulk.actions.${action}`),
            value: valueTitle,
            pieces: t('collection.piecesPlural', preview.items, { named: { count: preview.items } }),
          }) }}
          <div v-if="action.startsWith('category')" class="text-body-small text-medium-emphasis mt-1">
            {{ t('bulk.categoryNote', { sets: t('collection.setsPlural', preview.sets, { named: { count: preview.sets } }) }) }}
          </div>
        </div>
      </v-card-text>

      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="open = false">{{ t('common.cancel') }}</v-btn>

        <v-btn
          v-if="!preview"
          color="primary"
          :disabled="!canContinue"
          :loading="busy"
          variant="flat"
          @click="check"
        >{{ t('bulk.continue') }}</v-btn>

        <v-btn
          v-else
          color="primary"
          :disabled="preview.items === 0"
          :loading="busy"
          variant="flat"
          @click="confirm"
        >{{ t('common.confirm') }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<style scoped>
  .bulk-bar {
    position: sticky;
    bottom: 0;
    z-index: 2;
  }
</style>
