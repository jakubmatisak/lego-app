<script setup lang="ts">
  /**
   * Zbierka ako tabuľka. `v-data-table-virtual` kreslí len riadky na
   * obrazovke, takže aj 1500 riadkov sa posúva plynulo. Radí server: klik
   * na hlavičku zmení kľúč a smer v store (`sortFromHeader`), tabuľka sama
   * neradí nič. Pri zoskupení je riadok set alebo séria, pri „každom kuse“
   * kus. V režime výberu klik riadok označí, inak otvorí detail setu.
   */
  import type { Selection } from '@/composables/useSelection'
  import type { TableRow } from '@/utils/tableColumns'
  import type { VNodeRef } from 'vue'
  import { computed } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useRouter } from 'vue-router'
  import { VDataTable, VDataTableVirtual } from 'vuetify/components'
  import { defaultDir, useCollectionStore } from '@/stores/collection'
  import { COLUMNS, rowFromGroup, rowFromItem, sortFromHeader } from '@/utils/tableColumns'

  /**
   * `fill`: široká obrazovka, tabuľka vyplní výšku výsledkov a posúva sa
   * sama (virtuálne, len riadky na obrazovke). Na telefóne sa posúva celá
   * stránka, preto obyčajná tabuľka bez vlastného posuvníka.
   */
  const props = defineProps<{ selection: Selection, sold: boolean, fill?: boolean }>()

  const { t } = useI18n()
  const router = useRouter()
  const collection = useCollectionStore()

  const rows = computed<TableRow[]>(() =>
    collection.grouping === 'item'
      ? collection.items.map(item => rowFromItem(item))
      : collection.grouped.map(row => rowFromGroup(row, props.sold)),
  )

  const headers = computed(() => COLUMNS.map(column => ({
    key: column.key,
    title: t(`table.${column.key}`),
    align: column.align ?? 'start',
    sortable: false,
    width: column.width,
  })))

  function sortIcon (key: string): string | null {
    const column = COLUMNS.find(c => c.key === key)
    if (!column?.sort || column.sort !== collection.sort) return null
    const dir = collection.sortDir ?? defaultDir(collection.sort)
    return dir === 'asc' ? 'mdi-arrow-up' : 'mdi-arrow-down'
  }

  function onHeader (key: string): void {
    const column = COLUMNS.find(c => c.key === key)
    if (!column) return
    const next = sortFromHeader(column, { sort: collection.sort, dir: collection.sortDir })
    if (!next) return
    // Nový kľúč najprv: watch v store pri zmene kľúča smer vynuluje.
    collection.sort = next.sort
    collection.sortDir = next.dir
  }

  /** Virtuálna tabuľka meria riadok cez itemRef; obyčajná ho nemá. */
  function rowRef (slot: unknown): VNodeRef | undefined {
    return (slot as { itemRef?: VNodeRef }).itemRef
  }

  function selected (row: TableRow): boolean {
    return typeof row.selectKey === 'number'
      ? props.selection.hasItem(row.selectKey)
      : props.selection.hasGroup(row.selectKey)
  }

  function onRow (row: TableRow): void {
    if (props.selection.active.value) {
      if (typeof row.selectKey === 'number') props.selection.toggleItem(row.selectKey)
      else props.selection.toggleGroup(row.selectKey)
      return
    }
    router.push({ name: 'set-detail', params: { num: row.num } })
  }

  function conditionText (conditions: Record<string, number>): string {
    const entries = Object.entries(conditions)
    if (entries.length === 1) return t(`condition.${entries[0]![0]}`)
    return entries.map(([key, n]) => `${n}× ${t(`condition.${key}`).toLowerCase()}`).join(', ')
  }
</script>

<template>
  <v-card border class="collection-table-card" :class="{ 'collection-table-card--fill': fill }" flat>
    <component
      :is="fill ? VDataTableVirtual : VDataTable"
      class="collection-table"
      density="compact"
      fixed-header
      :headers="headers"
      :height="fill ? '100%' : undefined"
      :hide-default-footer="!fill"
      hover
      :item-height="fill ? 41 : undefined"
      item-value="key"
      :items="rows"
      :items-per-page="fill ? undefined : -1"
    >
      <template v-for="column in COLUMNS" :key="column.key" #[`header.${column.key}`]="{ column: header }">
        <span
          :class="{ 'collection-table__sortable': column.sort }"
          @click="onHeader(column.key)"
        >
          {{ header.title }}
          <v-icon v-if="sortIcon(column.key)" :icon="sortIcon(column.key)!" size="x-small" />
        </span>
      </template>

      <!--
        Riadok musí odovzdať itemRef: virtuálna tabuľka z neho meria výšku.
        Bez neho by ostala pri prvých piatich riadkoch a ďalšie by neukázala.
      -->
      <template #item="slot">
        <tr
          :ref="rowRef(slot)"
          class="collection-table__row"
          :class="{ 'collection-table__row--selected': selection.active.value && selected(slot.item) }"
          @click="onRow(slot.item)"
        >
          <!-- Tabuľka je na prehľad čísel, fotky sú na kartách. -->
          <td class="text-no-wrap">
            <v-icon
              v-if="selection.active.value"
              class="me-1"
              :color="selected(slot.item) ? 'primary' : undefined"
              :icon="selected(slot.item) ? 'mdi-checkbox-marked' : 'mdi-checkbox-blank-outline'"
              size="small"
            />{{ slot.item.num }}
          </td>

          <td>{{ slot.item.name }}</td>
          <td>{{ slot.item.theme }}</td>
          <td class="text-end">{{ slot.item.year ?? '—' }}</td>
          <td class="text-end">{{ slot.item.quantity }}</td>
          <td>{{ conditionText(slot.item.conditions) }}</td>
          <td>{{ slot.item.location }}</td>
          <td class="text-end text-no-wrap">{{ slot.item.purchase }}</td>
          <td class="text-end text-no-wrap">{{ slot.item.value }}</td>

          <td
            class="text-end text-no-wrap"
            :class="slot.item.profitSign > 0 ? 'text-positive' : slot.item.profitSign < 0 ? 'text-negative' : ''"
          >{{ slot.item.profit }}</td>

          <td class="text-end text-no-wrap">{{ slot.item.profitPct }}</td>
          <td class="text-end text-no-wrap">{{ slot.item.cagr }}</td>
        </tr>
      </template>
    </component>
  </v-card>
</template>

<style scoped>
  .collection-table-card--fill {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }

  .collection-table-card--fill .collection-table {
    flex: 1;
    min-height: 0;
  }

  /*
   * Pevné rozloženie: šírky z hlavičky platia pre všetky riadky, aj tie,
   * ktoré virtuálna tabuľka dokreslí pri posúvaní. Najmenšia šírka drží
   * stĺpce čitateľné; na úzkej obrazovke sa tabuľka posúva do strany.
   */
  .collection-table :deep(table) {
    table-layout: fixed;
    min-width: 1400px;
  }

  /* Hlavička sa nesmie lámať („Kus / y“), šírky sú na to dosť veľké. */
  .collection-table :deep(th) {
    white-space: nowrap;
  }

  .collection-table :deep(td) {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .collection-table__sortable {
    cursor: pointer;
    user-select: none;
  }

  .collection-table__row {
    cursor: pointer;
  }

  .collection-table__row--selected {
    background: rgba(var(--v-theme-primary), 0.08);
  }
</style>
