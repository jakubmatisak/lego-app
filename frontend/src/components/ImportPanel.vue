<script setup lang="ts">
  /**
   * Hromadný import zbierky z Excelu alebo CSV.
   *
   * Tri kroky: šablóna, nahratie, náhľad. Kým používateľ nepotvrdí, v zbierke
   * nič nevznikne; náhľad pri každom riadku povie, čo z neho bude, alebo prečo
   * sa preskočí. Neznáme čísla dohľadáva server na pozadí cez Rebrickable
   * a táto karta sa ho každé dve sekundy pýta na priebeh. Dokončený import
   * sa dá celý vrátiť z histórie.
   */
  import type { ImportDetail, ImportRow, ImportSummary } from '@/api/types'
  import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { api, errorMessage } from '@/api/client'
  import { useCollectionStore } from '@/stores/collection'
  import { useNotifyStore } from '@/stores/notify'
  import { dateTime, exactMoney, shortDate } from '@/utils/format'
  import { imageSrc } from '@/utils/imageSrc'

  type RowFilter = 'all' | 'ok' | 'duplicate' | 'error'

  const { t } = useI18n()
  const notify = useNotifyStore()
  const collection = useCollectionStore()

  const current = ref<ImportDetail | null>(null)
  const history = ref<ImportSummary[]>([])
  const uploading = ref(false)
  const committing = ref(false)
  const error = ref<string | null>(null)
  const dragging = ref(false)
  const filter = ref<RowFilter>('all')
  /** Riadky s duplicitou, ktoré chce používateľ importovať aj tak. */
  const forced = ref<Set<number>>(new Set())
  const undoTarget = ref<ImportSummary | null>(null)
  const undoing = ref(false)
  const picker = ref<HTMLInputElement | null>(null)
  let timer: ReturnType<typeof setTimeout> | null = null

  const lookingUp = computed(() => current.value?.state === 'looking_up')
  const isDraft = computed(() => current.value?.state === 'ready' || lookingUp.value)

  const shownRows = computed(() => {
    const rows = current.value?.rows ?? []
    return filter.value === 'all' ? rows : rows.filter(r => r.state === filter.value)
  })

  /** Čo presne vznikne po potvrdení, vrátane zaškrtnutých duplicít. */
  const planned = computed(() => {
    let pieces = 0
    let sold = 0
    let wishes = 0
    for (const row of current.value?.rows ?? []) {
      const take = row.state === 'ok' || (row.state === 'duplicate' && row.ownership !== 'wish' && forced.value.has(row.line))
      if (!take) continue
      if (row.ownership === 'wish') wishes += 1
      else if (row.ownership === 'sold') sold += row.quantity
      else pieces += row.quantity
    }
    return { pieces, sold, wishes, total: pieces + sold + wishes }
  })

  const commitLabel = computed(() => {
    const parts: string[] = []
    const p = planned.value
    if (p.pieces) parts.push(t('imports.piecesPlural', p.pieces, { named: { count: p.pieces } }))
    if (p.sold) parts.push(t('imports.soldPlural', p.sold, { named: { count: p.sold } }))
    if (p.wishes) parts.push(t('imports.wishesPlural', p.wishes, { named: { count: p.wishes } }))
    return t('imports.commit', { what: parts.join(', ') })
  })

  const progressPct = computed(() => {
    const c = current.value
    if (!c || c.progress_total === 0) return 0
    return Math.round((c.progress_done / c.progress_total) * 100)
  })

  function stopPolling (): void {
    if (timer) clearTimeout(timer)
    timer = null
  }

  async function loadHistory (): Promise<void> {
    const { data } = await api.GET('/imports', {})
    history.value = data ?? []
  }

  async function open (id: number): Promise<void> {
    const { data, error: err } = await api.GET('/imports/{import_id}', {
      params: { path: { import_id: id } },
    })
    if (err || !data) {
      error.value = errorMessage(err, t('imports.loadFailed'))
      return
    }
    current.value = data
    stopPolling()
    if (data.state === 'looking_up') {
      timer = setTimeout(() => open(id), 2000)
    }
  }

  async function upload (file: File | undefined): Promise<void> {
    if (!file) return
    error.value = null
    uploading.value = true
    forced.value = new Set()
    filter.value = 'all'
    try {
      const body = new FormData()
      body.append('file', file)
      const { data, error: err } = await api.POST('/imports', { body: body as never })
      if (err || !data) {
        error.value = errorMessage(err, t('imports.uploadFailed'))
        return
      }
      current.value = data
      if (data.state === 'looking_up') {
        await open(data.id)
      }
      loadHistory()
    } finally {
      uploading.value = false
      if (picker.value) picker.value.value = ''
    }
  }

  function onDrop (event: DragEvent): void {
    dragging.value = false
    upload(event.dataTransfer?.files?.[0])
  }

  function onPick (event: Event): void {
    upload((event.target as HTMLInputElement).files?.[0])
  }

  function toggleForced (line: number, value: boolean | null): void {
    const next = new Set(forced.value)
    if (value) next.add(line)
    else next.delete(line)
    forced.value = next
  }

  async function commit (): Promise<void> {
    if (!current.value) return
    committing.value = true
    error.value = null
    try {
      const { data, error: err } = await api.POST('/imports/{import_id}/commit', {
        params: { path: { import_id: current.value.id } },
        body: { include_duplicates: [...forced.value] },
      })
      if (err || !data) {
        error.value = errorMessage(err, t('imports.commitFailed'))
        return
      }
      current.value = data
      notify.success(t('notice.importCommitted'))
      collection.refreshAll()
      loadHistory()
    } finally {
      committing.value = false
    }
  }

  async function discard (): Promise<void> {
    stopPolling()
    const draft = current.value
    current.value = null
    if (draft && (draft.state === 'ready' || draft.state === 'looking_up')) {
      await api.DELETE('/imports/{import_id}', { params: { path: { import_id: draft.id } } })
      notify.info(t('notice.importDiscarded'))
    }
    loadHistory()
  }

  async function undo (): Promise<void> {
    if (!undoTarget.value) return
    undoing.value = true
    try {
      const { data, error: err } = await api.POST('/imports/{import_id}/undo', {
        params: { path: { import_id: undoTarget.value.id } },
      })
      if (err || !data) {
        error.value = errorMessage(err, t('imports.undoFailed'))
        return
      }
      if (current.value?.id === data.id) current.value = data
      undoTarget.value = null
      notify.success(t('notice.importUndone'))
      collection.refreshAll()
      loadHistory()
    } finally {
      undoing.value = false
    }
  }

  async function download (kind: 'xlsx' | 'csv'): Promise<void> {
    const path = kind === 'xlsx' ? '/imports/template.xlsx' : '/imports/template.csv'
    const { data, error: err } = await api.GET(path, { parseAs: 'blob' })
    if (err || !(data instanceof Blob)) {
      error.value = errorMessage(err, t('imports.templateFailed'))
      return
    }
    const url = URL.createObjectURL(data)
    const link = document.createElement('a')
    link.href = url
    link.download = `sablona-zbierka.${kind}`
    link.click()
    setTimeout(() => URL.revokeObjectURL(url), 10_000)
  }

  function stateIcon (row: ImportRow): { icon: string, color: string } {
    if (row.state === 'error') return { icon: 'mdi-close-circle', color: 'negative' }
    if (row.state === 'duplicate') return { icon: 'mdi-content-duplicate', color: 'warning' }
    return { icon: 'mdi-check-circle', color: 'positive' }
  }

  function hasNotes (row: ImportRow): boolean {
    return row.errors.length > 0 || row.warnings.length > 0
  }

  function ownershipLabel (row: ImportRow): string {
    return t(`imports.ownership.${row.ownership}`)
  }

  function historyLabel (item: ImportSummary): string {
    if (item.state === 'committed') {
      return t('imports.historyCommitted', { pieces: item.pieces_created, wishes: item.wishes_created })
    }
    if (item.state === 'undone') return t('imports.historyUndone')
    return t('imports.historyDraft', { rows: item.counts.rows })
  }

  onMounted(loadHistory)
  onBeforeUnmount(stopPolling)
</script>

<template>
  <div class="d-flex flex-column ga-4">
    <v-alert
      v-if="error"
      closable
      type="error"
      variant="tonal"
      @click:close="error = null"
    >{{ error }}</v-alert>

    <!-- 1. Nahratie -->
    <v-card v-if="!current" border class="pa-4" flat>
      <div class="text-h6 mb-1">{{ t('imports.title') }}</div>
      <div class="text-body-2 text-medium-emphasis mb-4">{{ t('imports.intro') }}</div>

      <div class="steps mb-4">
        <div class="step">
          <v-avatar color="primary" size="28" variant="tonal">1</v-avatar>

          <div>
            <div class="text-subtitle-2">{{ t('imports.step1') }}</div>

            <div class="d-flex ga-2 flex-wrap mt-2">
              <v-btn prepend-icon="mdi-microsoft-excel" size="small" variant="outlined" @click="download('xlsx')">
                {{ t('imports.templateXlsx') }}
              </v-btn>

              <v-btn prepend-icon="mdi-file-delimited-outline" size="small" variant="text" @click="download('csv')">
                {{ t('imports.templateCsv') }}
              </v-btn>
            </div>
          </div>
        </div>

        <div class="step">
          <v-avatar color="primary" size="28" variant="tonal">2</v-avatar>

          <div>
            <div class="text-subtitle-2">{{ t('imports.step2') }}</div>
            <div class="text-caption text-medium-emphasis">{{ t('imports.step2Hint') }}</div>
          </div>
        </div>

        <div class="step">
          <v-avatar color="primary" size="28" variant="tonal">3</v-avatar>

          <div>
            <div class="text-subtitle-2">{{ t('imports.step3') }}</div>
            <div class="text-caption text-medium-emphasis">{{ t('imports.step3Hint') }}</div>
          </div>
        </div>
      </div>

      <div
        class="drop-zone"
        :class="{ 'drop-zone--active': dragging }"
        role="button"
        tabindex="0"
        @click="picker?.click()"
        @dragleave.prevent="dragging = false"
        @dragover.prevent="dragging = true"
        @drop.prevent="onDrop"
        @keydown.enter="picker?.click()"
      >
        <v-progress-circular v-if="uploading" color="primary" indeterminate />

        <template v-else>
          <v-icon color="primary" icon="mdi-file-upload-outline" size="40" />
          <div class="text-subtitle-1 mt-2">{{ t('imports.drop') }}</div>
          <div class="text-caption text-medium-emphasis">{{ t('imports.dropHint') }}</div>
        </template>

        <input
          ref="picker"
          accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          hidden
          type="file"
          @change="onPick"
        >
      </div>

      <div class="text-caption text-medium-emphasis mt-3">
        <v-icon icon="mdi-lightbulb-outline" size="small" />
        {{ t('imports.tipExport') }}
      </div>
    </v-card>

    <!-- 2. Náhľad a výsledok -->
    <v-card v-else border class="pa-4" flat>
      <div class="d-flex align-center flex-wrap ga-2 mb-3">
        <v-icon icon="mdi-file-table-outline" />
        <span class="text-h6">{{ current.filename }}</span>
        <v-chip v-if="current.state === 'committed'" color="positive" size="small" variant="tonal">{{ t('imports.state.committed') }}</v-chip>
        <v-chip v-else-if="current.state === 'undone'" size="small" variant="tonal">{{ t('imports.state.undone') }}</v-chip>
        <v-spacer />

        <v-btn
          v-if="isDraft"
          prepend-icon="mdi-close"
          size="small"
          variant="text"
          @click="discard"
        >{{ t('imports.discard') }}</v-btn>

        <v-btn
          v-else
          prepend-icon="mdi-file-upload-outline"
          size="small"
          variant="text"
          @click="discard"
        >{{ t('imports.another') }}</v-btn>
      </div>

      <!-- Dohľadávanie -->
      <div v-if="lookingUp" class="mb-4">
        <div class="text-body-2 mb-1">
          {{ t('imports.lookingUp', { done: current.progress_done, total: current.progress_total }) }}
        </div>

        <v-progress-linear color="primary" height="8" :model-value="progressPct" rounded />
        <div class="text-caption text-medium-emphasis mt-1">{{ t('imports.lookingUpHint') }}</div>
      </div>

      <!-- Hotovo -->
      <v-alert v-if="current.state === 'committed'" class="mb-4" type="success" variant="tonal">
        {{ t('imports.done', { pieces: current.pieces_created, wishes: current.wishes_created }) }}
        <div class="text-caption mt-1">{{ t('imports.doneHint') }}</div>

        <template #append>
          <div class="d-flex ga-2 flex-wrap">
            <v-btn size="small" :to="{ name: 'collection', query: { imported: String(current.id) } }" variant="flat">{{ t('imports.openCollection') }}</v-btn>
            <v-btn size="small" variant="text" @click="undoTarget = current">{{ t('imports.undo') }}</v-btn>
          </div>
        </template>
      </v-alert>

      <v-alert v-if="current.state === 'undone'" class="mb-4" type="info" variant="tonal">{{ t('imports.undoneInfo') }}</v-alert>

      <v-alert
        v-if="current.ignored_columns.length > 0"
        class="mb-4"
        density="compact"
        icon="mdi-table-column-remove"
        type="info"
        variant="tonal"
      >
        {{ t('imports.ignored', { columns: current.ignored_columns.join(', ') }) }}
      </v-alert>

      <!-- Súhrn a filter -->
      <v-chip-group v-model="filter" class="mb-2" mandatory selected-class="text-primary">
        <v-chip filter value="all" variant="outlined">{{ t('imports.filterAll', { count: current.counts.rows }) }}</v-chip>
        <v-chip color="positive" filter value="ok" variant="outlined">{{ t('imports.filterOk', { count: current.counts.ok }) }}</v-chip>

        <v-chip
          v-if="current.counts.duplicate"
          color="warning"
          filter
          value="duplicate"
          variant="outlined"
        >
          {{ t('imports.filterDuplicate', { count: current.counts.duplicate }) }}
        </v-chip>

        <v-chip
          v-if="current.counts.error"
          color="negative"
          filter
          value="error"
          variant="outlined"
        >
          {{ t('imports.filterError', { count: current.counts.error }) }}
        </v-chip>
      </v-chip-group>

      <div v-if="isDraft && current.counts.duplicate" class="text-caption text-medium-emphasis mb-2">
        {{ t('imports.duplicateHint') }}
      </div>

      <div class="rows-scroll">
        <v-table density="compact">
          <thead>
            <tr>
              <th />
              <th>{{ t('imports.colLine') }}</th>
              <th>{{ t('imports.colSet') }}</th>
              <th>{{ t('imports.colWhat') }}</th>
              <th class="text-end">{{ t('imports.colQuantity') }}</th>
              <th>{{ t('imports.colCondition') }}</th>
              <th class="text-end">{{ t('imports.colPrice') }}</th>
              <th>{{ t('imports.colDate') }}</th>
              <th>{{ t('imports.colLocation') }}</th>
            </tr>
          </thead>

          <tbody>
            <template v-for="row in shownRows" :key="row.line">
              <tr :class="{ 'row--skip': row.state === 'error', 'row--noted': hasNotes(row) }">
                <td class="state-cell">
                  <v-checkbox-btn
                    v-if="isDraft && row.state === 'duplicate' && row.ownership !== 'wish'"
                    density="compact"
                    :model-value="forced.has(row.line)"
                    :title="t('imports.importAnyway')"
                    @update:model-value="value => toggleForced(row.line, value)"
                  />

                  <v-icon v-else v-bind="stateIcon(row)" size="small" />
                </td>

                <td class="text-medium-emphasis">{{ row.line }}</td>

                <td class="set-cell">
                  <div class="d-flex align-center ga-2">
                    <img v-if="row.image_url" alt="" class="thumb" :src="imageSrc(row.image_url) ?? undefined">

                    <div>
                      <div class="text-body-2">{{ row.name ?? row.name_hint ?? '—' }}</div>
                      <div class="text-caption text-medium-emphasis">{{ row.catalog_num ?? row.raw_num }}</div>
                    </div>
                  </div>
                </td>

                <td>
                  <v-chip label size="x-small" variant="tonal">{{ ownershipLabel(row) }}</v-chip>
                </td>

                <td class="text-end">{{ row.ownership === 'wish' ? '' : row.quantity }}</td>

                <td class="text-no-wrap">{{ row.ownership === 'wish' ? '' : t(`condition.${row.condition}`) }}</td>

                <td class="text-end text-no-wrap">
                  <template v-if="row.ownership === 'wish'">{{ row.target_price ? exactMoney(row.target_price) : '' }}</template>

                  <template v-else>
                    {{ row.purchase_price ? exactMoney(row.purchase_price) : '—' }}
                    <div v-if="row.ownership === 'sold'" class="text-caption text-medium-emphasis">
                      → {{ exactMoney(row.sold_price) }}
                    </div>
                  </template>
                </td>

                <td class="text-no-wrap">
                  {{ row.purchase_date ? shortDate(row.purchase_date) : '' }}
                  <div v-if="row.sold_date" class="text-caption text-medium-emphasis">→ {{ shortDate(row.sold_date) }}</div>
                </td>

                <td>{{ row.location ?? '' }}</td>

              </tr>

              <!-- Dôvod pod riadkom cez celú šírku, aby ho nebolo treba hľadať vpravo. -->
              <tr v-if="hasNotes(row)" class="notes-row">
                <td />

                <td colspan="8">
                  <div v-for="(message, i) in row.errors" :key="`e${i}`" class="text-caption text-negative">
                    <v-icon icon="mdi-alert-circle-outline" size="x-small" /> {{ message }}
                  </div>

                  <div v-for="(message, i) in row.warnings" :key="`w${i}`" class="text-caption text-medium-emphasis">
                    <v-icon icon="mdi-information-outline" size="x-small" /> {{ message }}
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </v-table>
      </div>

      <div v-if="isDraft" class="d-flex align-center flex-wrap ga-2 mt-4">
        <div class="text-body-2 text-medium-emphasis">
          <template v-if="current.counts.error">{{ t('imports.skipped', { count: current.counts.error }) }}</template>
        </div>

        <v-spacer />
        <v-btn variant="text" @click="discard">{{ t('imports.discard') }}</v-btn>

        <v-btn
          color="primary"
          :disabled="lookingUp || planned.total === 0"
          :loading="committing"
          prepend-icon="mdi-database-import-outline"
          variant="flat"
          @click="commit"
        >{{ planned.total === 0 ? t('imports.nothing') : commitLabel }}</v-btn>
      </div>
    </v-card>

    <!-- História -->
    <v-card v-if="history.length > 0" border class="pa-4" flat>
      <div class="text-h6 mb-2">{{ t('imports.history') }}</div>

      <v-list density="compact">
        <v-list-item
          v-for="item in history"
          :key="item.id"
          :subtitle="`${dateTime(item.created_at)} · ${historyLabel(item)}`"
          :title="item.filename"
        >
          <template #prepend>
            <v-icon
              :color="item.state === 'committed' ? 'positive' : undefined"
              :icon="item.state === 'committed' ? 'mdi-check-circle-outline' : item.state === 'undone' ? 'mdi-undo' : 'mdi-file-clock-outline'"
            />
          </template>

          <template #append>
            <v-btn
              v-if="item.state === 'committed'"
              size="small"
              variant="text"
              @click="undoTarget = item"
            >{{ t('imports.undo') }}</v-btn>

            <v-btn
              v-else-if="item.state === 'ready' || item.state === 'looking_up'"
              size="small"
              variant="text"
              @click="open(item.id)"
            >{{ t('imports.continue') }}</v-btn>
          </template>
        </v-list-item>
      </v-list>
    </v-card>

    <!-- Potvrdenie vrátenia -->
    <v-dialog max-width="480" :model-value="undoTarget !== null" @update:model-value="undoTarget = null">
      <v-card v-if="undoTarget">
        <v-card-title>{{ t('imports.undoTitle', { name: undoTarget.filename }) }}</v-card-title>

        <v-card-text>
          {{ t('imports.undoText', { pieces: undoTarget.pieces_created, wishes: undoTarget.wishes_created }) }}
        </v-card-text>

        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="undoTarget = null">{{ t('common.cancel') }}</v-btn>
          <v-btn color="negative" :loading="undoing" variant="flat" @click="undo">{{ t('imports.undoConfirm') }}</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<style scoped>
.steps {
  display: grid;
  gap: 16px;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}

.step {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.drop-zone {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 160px;
  padding: 24px;
  border: 2px dashed rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 12px;
  cursor: pointer;
  text-align: center;
  transition: border-color 0.15s, background-color 0.15s;
}

.drop-zone:hover,
.drop-zone--active {
  border-color: rgb(var(--v-theme-primary));
  background-color: rgba(var(--v-theme-primary), 0.04);
}

.rows-scroll {
  max-height: 60vh;
  overflow: auto;
}

.thumb {
  width: 40px;
  height: 32px;
  object-fit: contain;
}

.set-cell {
  min-width: 200px;
}

.row--noted > td {
  border-bottom: none !important;
}

.notes-row > td {
  height: auto !important;
  padding-bottom: 8px !important;
}

.state-cell {
  width: 40px;
}

.row--skip {
  opacity: 0.7;
}
</style>
