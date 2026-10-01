<script setup lang="ts">
  /**
   * Karta „Diely · N“ v detaile setu. Zoznam dielikov z Rebrickable sa
   * stiahne až po rozbalení karty (server ho drží raz na set, 90 dní),
   * zoskupený podľa farby, náhradné diely zvlášť.
   *
   * Kontrola úplnosti je pri kuse: pri dieliku sa zadá, koľko ho je, a server
   * si uloží len to, čo chýba. Kus s chýbajúcimi dielikmi má potom štítok
   * „chýbajú N“ v detaile aj na karte v Zbierke. Zoznam chýbajúcich sa
   * sťahuje cez klienta a blob, odkaz by odišiel bez prihlásenia.
   *
   * Riadkov môže byť vyše tisíc (Titanic), preto sú jednoduché: obrázok
   * s `loading="lazy"`, obyčajné číselné pole a `content-visibility`.
   */
  import type { SetPart, ValuedItem } from '@/api/types'
  import { computed, onMounted, ref, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { api, errorMessage } from '@/api/client'
  import LoadFailed from '@/components/LoadFailed.vue'
  import SourceCredit from '@/components/SourceCredit.vue'
  import { useNotifyStore } from '@/stores/notify'
  import { count, isoDate, shortDate } from '@/utils/format'
  import { imageSrc } from '@/utils/imageSrc'

  const props = defineProps<{
    num: string
    /** Počet dielikov z katalógu, kým sa zoznam nestiahne. */
    numParts?: number | null
    /** Kusy setu, ktoré sa dajú skontrolovať (vlastnené a rezervované). */
    pieces: ValuedItem[]
  }>()
  const emit = defineEmits<{ checked: [itemId: number, missing: number] }>()

  const { t } = useI18n()
  const notify = useNotifyStore()

  const panel = ref<string | null>(null)
  const root = ref<HTMLElement | null>(null)
  const state = ref<'idle' | 'loading' | 'failed' | 'ready'>('idle')
  const error = ref<string | null>(null)
  const parts = ref<SetPart[]>([])

  async function load (): Promise<void> {
    state.value = 'loading'
    const { data, error: err } = await api.GET('/catalog/{num}/parts', { params: { path: { num: props.num } } })
    if (err || !data) {
      error.value = errorMessage(err, t('common.loadFailed'))
      state.value = 'failed'
      return
    }
    parts.value = data.parts ?? []
    state.value = 'ready'
  }

  watch(panel, value => {
    if (value && state.value === 'idle') load()
  })
  watch(() => props.num, () => {
    state.value = 'idle'
    parts.value = []
    checking.value = false
    if (panel.value) load()
  })

  interface ColorGroup {
    key: string
    name: string
    rgb: string | null
    total: number
    parts: SetPart[]
  }

  /** Farby od najpočetnejšej; v nej dieliky od najpočetnejšieho. */
  function byColor (list: SetPart[]): ColorGroup[] {
    const groups = new Map<number, ColorGroup>()
    for (const p of list) {
      let group = groups.get(p.color_id)
      if (!group) {
        group = { key: `${p.color_id}`, name: p.color_name, rgb: p.color_rgb ?? null, total: 0, parts: [] }
        groups.set(p.color_id, group)
      }
      group.total += p.quantity
      group.parts.push(p)
    }
    for (const group of groups.values()) {
      group.parts.sort((a, b) => b.quantity - a.quantity || a.part_num.localeCompare(b.part_num))
    }
    return [...groups.values()].toSorted((a, b) => b.total - a.total || a.name.localeCompare(b.name))
  }

  const regular = computed(() => byColor(parts.value.filter(p => !p.is_spare)))
  const spares = computed(() => byColor(parts.value.filter(p => p.is_spare)))
  const regularTotal = computed(() => regular.value.reduce((s, g) => s + g.total, 0))
  const spareTotal = computed(() => spares.value.reduce((s, g) => s + g.total, 0))

  /** Počet z uloženého zoznamu (bez volania von), kým sa karta nerozbalí. */
  const known = ref<number | null>(null)

  async function loadSummary (): Promise<void> {
    const { data } = await api.GET('/catalog/{num}/parts-summary', { params: { path: { num: props.num } } })
    known.value = data?.parts ?? null
  }
  onMounted(loadSummary)

  const title = computed(() => {
    const n = state.value === 'ready' && parts.value.length > 0
      ? regularTotal.value
      : (known.value ?? props.numParts)
    return n ? t('parts.titleCount', { count: count(n) }) : t('parts.title')
  })

  // --- kontrola úplnosti -------------------------------------------------------

  const checking = ref(false)
  const checkItemId = ref<number | null>(null)
  /** Kľúč dielika → koľko chýba. Uložené sú len nenulové. */
  const missing = ref<Record<string, number>>({})
  const missingTotal = ref(0)

  function partKey (p: Pick<SetPart, 'part_num' | 'color_id' | 'is_spare'>): string {
    return `${p.part_num}|${p.color_id}|${p.is_spare ? 1 : 0}`
  }

  function have (p: SetPart): number {
    return p.quantity - (missing.value[partKey(p)] ?? 0)
  }

  function applyChecks (data: { missing_total: number, checks?: { part_num: string, color_id: number, is_spare: boolean, missing: number }[] }): void {
    const map: Record<string, number> = {}
    for (const c of data.checks ?? []) map[partKey(c)] = c.missing
    missing.value = map
    missingTotal.value = data.missing_total
  }

  async function loadChecks (): Promise<void> {
    const id = checkItemId.value
    if (id === null) return
    const { data } = await api.GET('/items/{item_id}/part-checks', { params: { path: { item_id: id } } })
    if (data && checkItemId.value === id) applyChecks(data)
  }

  /** Otvorí kartu v režime kontroly pre kus (štítok „chýbajú N“ pri kuse). */
  async function startCheck (itemId?: number): Promise<void> {
    panel.value = 'parts'
    root.value?.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
    checkItemId.value = itemId ?? props.pieces[0]?.id ?? null
    checking.value = checkItemId.value !== null
    if (state.value === 'idle') await load()
    await loadChecks()
  }

  watch(checkItemId, () => {
    if (checking.value) loadChecks()
  })

  async function setHave (p: SetPart, raw: string): Promise<void> {
    const id = checkItemId.value
    if (id === null) return
    const parsed = Number.parseInt(raw, 10)
    const present = Number.isFinite(parsed) ? Math.min(Math.max(parsed, 0), p.quantity) : p.quantity
    const value = p.quantity - present
    const key = partKey(p)
    if ((missing.value[key] ?? 0) === value) return
    missing.value = { ...missing.value, [key]: value }
    const { data, error: err } = await api.PUT('/items/{item_id}/part-checks', {
      params: { path: { item_id: id } },
      body: { part_num: p.part_num, color_id: p.color_id, is_spare: p.is_spare ?? false, missing: value },
    })
    if (err || !data) {
      notify.error(err, t('parts.saveFailed'))
      await loadChecks()
      return
    }
    if (checkItemId.value === id) applyChecks(data)
    emit('checked', id, data.missing_total)
  }

  const pieceOptions = computed(() =>
    props.pieces.map(p => ({
      value: p.id,
      title: t('parts.pieceLabel', {
        condition: t(`condition.${p.condition}`),
        date: shortDate(p.purchase_date),
      }),
    })),
  )

  const downloading = ref(false)

  async function downloadMissing (): Promise<void> {
    const id = checkItemId.value
    if (id === null) return
    downloading.value = true
    try {
      const { data, error: err } = await api.GET('/items/{item_id}/missing-parts.csv', {
        params: { path: { item_id: id } },
        parseAs: 'blob',
      })
      if (err || !(data instanceof Blob)) {
        notify.error(err, t('parts.missingListFailed'))
        return
      }
      const url = URL.createObjectURL(data)
      const link = document.createElement('a')
      link.href = url
      link.download = `chybajuce-${props.num}-${isoDate()}.csv`
      link.click()
      setTimeout(() => URL.revokeObjectURL(url), 10_000)
    } catch (error_) {
      notify.error(error_, t('parts.missingListFailed'))
    } finally {
      downloading.value = false
    }
  }

  defineExpose({ startCheck })
</script>

<template>
  <div ref="root">
    <v-expansion-panels v-model="panel" class="parts-card" flat>
      <v-expansion-panel class="border" rounded="lg" value="parts">
        <v-expansion-panel-title>
          <span class="text-title-large font-weight-medium">{{ title }}</span>

          <v-chip
            v-if="checking && missingTotal > 0"
            class="ms-3"
            color="warning"
            label
            size="small"
            variant="tonal"
          >{{ t('parts.missingPlural', missingTotal, { named: { count: missingTotal } }) }}</v-chip>
        </v-expansion-panel-title>

        <v-expansion-panel-text>
          <v-skeleton-loader
            v-if="state === 'loading' || state === 'idle'"
            data-test="parts-loading"
            type="list-item-avatar-two-line@4"
          />

          <LoadFailed v-else-if="state === 'failed'" :message="error" @retry="load" />

          <v-empty-state
            v-else-if="parts.length === 0"
            data-test="parts-empty"
            icon="mdi-puzzle-outline"
            :title="t('parts.empty')"
          />

          <div v-else class="d-flex flex-column ga-3">
            <div class="d-flex align-center flex-wrap ga-2">
              <span class="text-body-medium text-medium-emphasis">
                {{ t('parts.totalPlural', regularTotal, { named: { count: count(regularTotal) } }) }}
                <template v-if="spareTotal > 0">
                  · {{ t('parts.sparesPlural', spareTotal, { named: { count: count(spareTotal) } }) }}
                </template>
              </span>

              <v-spacer />

              <v-select
                v-if="checking && pieceOptions.length > 1"
                v-model="checkItemId"
                class="parts-piece"
                density="compact"
                hide-details
                :items="pieceOptions"
                :label="t('parts.piece')"
                variant="outlined"
              />

              <v-btn
                v-if="checking && missingTotal > 0"
                data-test="parts-missing-csv"
                :loading="downloading"
                prepend-icon="mdi-download"
                size="small"
                variant="outlined"
                @click="downloadMissing"
              >{{ t('parts.missingList') }}</v-btn>

              <v-btn
                v-if="pieces.length > 0"
                :color="checking ? 'primary' : undefined"
                data-test="parts-check"
                :prepend-icon="checking ? 'mdi-check' : 'mdi-clipboard-check-outline'"
                size="small"
                :variant="checking ? 'flat' : 'outlined'"
                @click="checking ? (checking = false) : startCheck(checkItemId ?? undefined)"
              >{{ checking ? t('parts.checkDone') : t('parts.check') }}</v-btn>
            </div>

            <div v-if="checking" class="text-body-small text-medium-emphasis">
              {{ missingTotal > 0 ? t('parts.checkHint') : `${t('parts.checkHint')} ${t('parts.complete')}.` }}
            </div>

            <template
              v-for="section in [
                { key: 'regular', groups: regular, spare: false },
                { key: 'spare', groups: spares, spare: true },
              ]"
              :key="section.key"
            >
              <div
                v-if="section.spare && section.groups.length > 0"
                class="text-title-small font-weight-medium mt-2"
                data-test="parts-spares"
              >{{ t('parts.spares') }}</div>

              <section
                v-for="group in section.groups"
                :key="`${section.key}-${group.key}`"
                class="parts-group"
                data-test="parts-color"
              >
                <div class="d-flex align-center ga-2 text-body-medium font-weight-medium py-1">
                  <span class="parts-swatch" :style="{ background: group.rgb ? `#${group.rgb}` : undefined }" />
                  {{ group.name }}
                  <span class="text-body-small text-medium-emphasis">{{ count(group.total) }}</span>
                </div>

                <div v-for="p in group.parts" :key="partKey(p)" class="parts-row">
                  <img
                    v-if="p.image_url"
                    :alt="p.name"
                    class="parts-img"
                    loading="lazy"
                    :src="imageSrc(p.image_url) ?? undefined"
                  >

                  <v-icon v-else class="parts-img" color="medium-emphasis" icon="mdi-puzzle-outline" />

                  <div class="parts-text">
                    <div class="text-body-medium text-truncate">{{ p.name }}</div>
                    <div class="text-body-small text-medium-emphasis">{{ p.part_num }}</div>
                  </div>

                  <template v-if="checking">
                    <v-chip
                      v-if="(missing[partKey(p)] ?? 0) > 0"
                      color="warning"
                      label
                      size="x-small"
                      variant="tonal"
                    >{{ t('parts.missingShort', { count: missing[partKey(p)] }) }}</v-chip>

                    <label class="parts-have text-body-small">
                      <span class="text-medium-emphasis">{{ t('parts.have') }}</span>

                      <input
                        :aria-label="`${t('parts.have')}: ${p.name}`"
                        class="parts-input"
                        :data-part="partKey(p)"
                        :max="p.quantity"
                        min="0"
                        type="number"
                        :value="have(p)"
                        @change="setHave(p, ($event.target as HTMLInputElement).value)"
                      >

                      <span class="text-medium-emphasis">/ {{ p.quantity }}</span>
                    </label>
                  </template>

                  <span v-else class="parts-qty text-body-medium">× {{ p.quantity }}</span>
                </div>
              </section>
            </template>

            <SourceCredit href="https://rebrickable.com" :text="t('parts.credit')" />
          </div>
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>
  </div>
</template>

<style scoped>
.parts-piece {
  max-width: 280px;
  min-width: 200px;
}

.parts-swatch {
  border: thin solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 3px;
  display: inline-block;
  height: 14px;
  width: 14px;
}

/* Prehliadač vykreslí len riadky, ktoré sú vidieť; Titanic má vyše tisíc. */
.parts-row {
  align-items: center;
  border-bottom: thin solid rgba(var(--v-border-color), 0.12);
  contain-intrinsic-size: auto 52px;
  content-visibility: auto;
  display: flex;
  gap: 12px;
  padding: 4px 0;
}

.parts-img {
  background: #fff;
  border-radius: 4px;
  flex: 0 0 44px;
  height: 44px;
  object-fit: contain;
  width: 44px;
}

.parts-text {
  flex: 1 1 auto;
  min-width: 0;
}

.parts-qty {
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.parts-have {
  align-items: center;
  display: flex;
  gap: 6px;
  white-space: nowrap;
}

.parts-input {
  background: rgb(var(--v-theme-surface));
  border: thin solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 4px;
  color: inherit;
  font: inherit;
  padding: 2px 6px;
  text-align: end;
  width: 4.5rem;
}
</style>
