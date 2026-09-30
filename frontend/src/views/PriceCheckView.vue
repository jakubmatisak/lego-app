<script setup lang="ts">
  /**
   * Overiť cenu: napíšem alebo naskenujem set a hneď vidím, čo to je a koľko
   * stojí. Všetko robí server (`POST /prices/lookup/{num}`): set hľadá
   * v katalógu, potom cez Rebrickable, a neznámy set spozná aj z odpovede
   * BrickEconomy o cene. Cena mladšia než deň sa vezme z vlastnej databázy
   * bez volania. Overené sety sa pamätajú pri účte (Naposledy overené).
   */
  import type { CatalogDetail, PriceCheck as Check, PriceOverview } from '@/api/types'
  import { computed, onMounted, ref } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useDisplay } from 'vuetify'
  import { api, errorMessage } from '@/api/client'
  import PriceHistoryChart from '@/components/PriceHistoryChart.vue'
  import SetImage from '@/components/SetImage.vue'
  import { useScanCodes } from '@/scanner/useScanCodes'
  import { useAuthStore } from '@/stores/auth'
  import { isBarcode } from '@/utils/barcode'
  import { count, dateTime, money } from '@/utils/format'
  import { imageSrc } from '@/utils/imageSrc'

  /** Cena mladšia než toto sa neťahá znova, overenie potom nič nestojí. */
  const FRESH_HOURS = 24

  const { t } = useI18n()
  const auth = useAuthStore()
  /** Na širokej obrazovke je stránka na výšku okna a tabuľka sa posúva sama. */
  const { smAndDown } = useDisplay()

  const query = ref('')
  const busy = ref(false)
  const found = ref<CatalogDetail | null>(null)
  const pricesN = ref<PriceOverview | null>(null)
  const pricesU = ref<PriceOverview | null>(null)
  const message = ref<string | null>(null)
  const priceNote = ref<string | null>(null)
  const checks = ref<Check[]>([])

  const canPrice = computed(() => auth.can('brickeconomy.price_detail'))
  const canIdentify = computed(() => auth.can('rebrickable.set'))
  /** Stav služieb, ktoré overenie potrebuje: kto spozná set a kto dá cenu. */
  const sources = computed(() => [
    { name: 'Rebrickable', on: canIdentify.value, role: t('check.roleIdentify') },
    { name: 'Brickset', on: auth.can('brickset.barcode'), role: t('check.roleBarcode') },
    { name: 'BrickEconomy', on: canPrice.value, role: t('check.rolePrice') },
  ])
  /** Keď set nie je v katalógu a nemá ho kto dohľadať, treba to povedať rovno. */
  const needsSettings = ref(false)
  const isSeries = computed(() => (found.value?.members?.length ?? 0) > 0)

  const headers = computed(() => [
    { key: 'num', title: t('check.colNumber'), width: 96, value: (c: Check) => c.catalog.catalog_num },
    { key: 'name', title: t('check.colName'), value: (c: Check) => c.catalog.name },
    { key: 'theme', title: t('check.colSeries'), width: 160, value: (c: Check) => c.catalog.theme ?? '' },
    { key: 'year', title: t('check.colYear'), width: 72, value: (c: Check) => c.catalog.year ?? 0 },
    { key: 'new', title: t('check.colNew'), width: 110, align: 'end' as const, value: (c: Check) => Number(c.new_value ?? -1) },
    { key: 'used', title: t('check.colUsed'), width: 110, align: 'end' as const, value: (c: Check) => Number(c.used_value ?? -1) },
    { key: 'when', title: t('check.colWhen'), width: 150, value: (c: Check) => c.checked_at },
    { key: 'actions', title: '', width: 56, sortable: false },
  ])

  async function loadChecks (): Promise<void> {
    const { data } = await api.GET('/prices/checks', {})
    checks.value = data ?? []
  }

  function reset (): void {
    found.value = null
    pricesN.value = null
    pricesU.value = null
    message.value = null
    priceNote.value = null
    needsSettings.value = false
  }

  /** Čiarový kód na číslo setu (katalóg, Brickset, UPCitemdb). */
  async function numberFromBarcode (raw: string): Promise<string | null> {
    const code = raw.replace(/\D/g, '')
    const { data, error } = await api.GET('/catalog/by-ean/{code}', { params: { path: { code } } })
    if (error || !data) {
      message.value = errorMessage(error, t('scan.invalid'))
      return null
    }
    if (!data.catalog) {
      message.value = t('check.eanUnknown', { code: data.ean })
      return null
    }
    return data.catalog.catalog_num
  }

  /** Čo sa stalo s cenou, po slovensky. */
  function priceMessage (price: string | null | undefined, left: number | null | undefined): string | null {
    switch (price) {
      case 'fetched': { return t('check.fetched', { left: left ?? '?' }) }
      case 'cached': { return t('check.cached') }
      case 'missing': { return t('check.noPriceFound') }
      case 'disconnected': { return t('check.priceDisconnected') }
      case 'quota': { return t('check.quota') }
      case 'blocked': { return t('check.blocked') }
      case 'unsupported': { return t('check.unsupported') }
      default: { return null }
    }
  }

  /** Uložené ceny oboch stavov, bez volania von. */
  async function loadStoredPrices (num: string): Promise<void> {
    const [n, u] = await Promise.all((['N', 'U'] as const).map(condition =>
      api.GET('/prices/{num}', { params: { path: { num }, query: { condition } } }),
    ))
    pricesN.value = n.data ?? null
    pricesU.value = u.data ?? null
  }

  /** Celé overenie jedným volaním servera: čo to je, cena, zápis do histórie. */
  async function check (raw: string): Promise<void> {
    const value = raw.trim()
    if (!value || busy.value) return
    busy.value = true
    reset()
    try {
      const num = isBarcode(value) ? await numberFromBarcode(value) : value
      if (!num) return
      const { data, error } = await api.POST('/prices/lookup/{num}', { params: { path: { num } } })
      if (error || !data) {
        message.value = errorMessage(error, t('check.priceFailed'))
        return
      }
      if (data.outcome !== 'ok' || !data.catalog) {
        needsSettings.value = data.outcome === 'no_sources'
        message.value = data.outcome === 'no_sources'
          ? t('check.noSources', { num })
          : (priceMessage(data.price, data.calls_left) ?? t('check.notFound', { num }))
        return
      }
      found.value = data.catalog
      query.value = ''
      if (data.price === 'series') return
      priceNote.value = priceMessage(data.price, data.calls_left)
      await loadStoredPrices(data.catalog.catalog_num)
      await loadChecks()
    } catch (error_) {
      message.value = errorMessage(error_)
    } finally {
      busy.value = false
      if (canPrice.value) auth.loadKeys()
    }
  }

  /** Otvorenie z tabuľky: len uložené ceny, nič nevolá a poradie sa nemení. */
  async function showStored (num: string): Promise<void> {
    if (busy.value) return
    busy.value = true
    reset()
    try {
      const { data } = await api.GET('/catalog/{num}', { params: { path: { num } } })
      if (!data) return
      found.value = data
      await loadStoredPrices(num)
    } finally {
      busy.value = false
    }
  }

  async function forget (num: string): Promise<void> {
    await api.DELETE('/prices/checks/{num}', { params: { path: { num } } })
    checks.value = checks.value.filter(c => c.catalog.catalog_num !== num)
  }

  const newValue = computed(() => pricesN.value?.current?.avg_price ?? null)
  const usedValue = computed(() => pricesU.value?.current?.avg_price ?? null)

  // Skeny z čítačky ostávajú na tejto obrazovke, neotvárajú Pridať set.
  useScanCodes(code => check(code))

  onMounted(loadChecks)
</script>

<template>
  <div class="check-page d-flex flex-column ga-4" :class="{ 'check-page--fit': !smAndDown }">
    <v-alert
      border="start"
      :icon="canPrice ? 'mdi-alert-outline' : 'mdi-connection'"
      prominent
      :title="canPrice ? t('check.warningTitle') : t('check.disconnectedTitle')"
      :type="canPrice ? 'warning' : 'error'"
      variant="tonal"
    >
      <div>{{ canPrice ? t('check.warningText', { hours: FRESH_HOURS }) : t('check.disconnectedText') }}</div>

      <div class="mt-1">
        {{ canIdentify
          ? t('check.identifyRebrickable')
          : (canPrice ? t('check.identifyBrickEconomy') : t('check.identifyNothing')) }}
      </div>

      <div class="d-flex ga-2 flex-wrap align-center mt-3">
        <v-chip
          v-for="s in sources"
          :key="s.name"
          :color="s.on ? 'positive' : undefined"
          :prepend-icon="s.on ? 'mdi-check-circle' : 'mdi-close-circle-outline'"
          size="small"
          :title="s.role"
          variant="flat"
        >{{ s.name }} · {{ s.role }}</v-chip>

        <v-btn
          v-if="!canPrice || !canIdentify"
          :color="canPrice ? undefined : 'error'"
          prepend-icon="mdi-cog-outline"
          size="small"
          :to="{ name: 'settings', query: { tab: 'data' } }"
          :variant="canPrice ? 'text' : 'flat'"
        >{{ t('check.openSettings') }}</v-btn>
      </div>
    </v-alert>

    <v-card>
      <v-card-text>
        <form class="d-flex ga-2 align-start" @submit.prevent="check(query)">
          <v-text-field
            v-model="query"
            autofocus
            :hint="t('check.inputHint')"
            :label="t('check.inputLabel')"
            persistent-hint
            prepend-inner-icon="mdi-barcode-scan"
            variant="outlined"
          />

          <v-btn
            color="primary"
            :disabled="!query.trim()"
            height="48"
            :loading="busy"
            type="submit"
            variant="flat"
          >{{ t('check.submit') }}</v-btn>
        </form>
      </v-card-text>
    </v-card>

    <v-alert v-if="message" :type="needsSettings ? 'error' : 'info'" variant="tonal">
      <div>{{ message }}</div>

      <v-btn
        v-if="needsSettings"
        class="mt-2"
        prepend-icon="mdi-cog-outline"
        size="small"
        :to="{ name: 'settings', query: { tab: 'data' } }"
        variant="flat"
      >{{ t('check.openSettings') }}</v-btn>
    </v-alert>

    <v-card v-if="found">
      <v-card-text class="d-flex flex-column ga-4">
        <div class="d-flex ga-4 flex-wrap">
          <SetImage :alt="found.name" :size="160" :src="imageSrc(found.image_url) ?? undefined" />

          <div class="flex-grow-1" style="min-width: 220px">
            <div class="text-headline-small font-weight-bold">{{ found.name }}</div>

            <div class="text-body-large text-medium-emphasis">
              {{ found.catalog_num }}
              <span v-if="found.theme"> · {{ found.theme }}</span>
              <span v-if="found.year"> · {{ found.year }}</span>
              <span v-if="found.num_parts"> · {{ t('check.parts', { count: count(found.num_parts) }) }}</span>
            </div>

            <div class="d-flex ga-2 flex-wrap mt-2">
              <v-chip
                v-if="found.ownership?.owned"
                color="primary"
                prepend-icon="mdi-check-decagram"
                variant="flat"
              >{{ t('check.owned', { count: found.ownership.owned_count }) }}</v-chip>

              <v-chip v-if="found.is_retired" variant="outlined">{{ t('check.retired') }}</v-chip>
              <v-chip v-if="found.rrp_eur" variant="outlined">{{ t('check.rrp', { price: money(found.rrp_eur) }) }}</v-chip>
            </div>
          </div>

          <div v-if="!isSeries" class="d-flex ga-6">
            <div>
              <div class="text-body-small text-medium-emphasis">{{ t('check.newLabel') }}</div>
              <div class="text-headline-large font-weight-bold">{{ money(newValue) }}</div>
            </div>

            <div>
              <div class="text-body-small text-medium-emphasis">{{ t('check.usedLabel') }}</div>
              <div class="text-headline-large font-weight-bold">{{ money(usedValue) }}</div>
            </div>
          </div>
        </div>

        <template v-if="isSeries">
          <div class="text-body-medium">{{ t('check.pickMember') }}</div>

          <div class="d-flex ga-2 flex-wrap">
            <v-chip
              v-for="m in found.members"
              :key="m.catalog_num"
              :disabled="busy"
              @click="check(m.catalog_num)"
            >{{ m.name }}</v-chip>
          </div>
        </template>

        <template v-else>
          <div class="d-flex align-center ga-2 flex-wrap">
            <span v-if="priceNote" class="text-body-medium text-medium-emphasis">{{ priceNote }}</span>

            <span
              v-if="pricesN?.current?.captured_at"
              class="text-body-small text-medium-emphasis"
            >{{ t('check.capturedAt', { time: dateTime(pricesN.current.captured_at) }) }}</span>

            <v-spacer />

            <v-btn
              v-if="canPrice && !priceNote"
              :loading="busy"
              prepend-icon="mdi-refresh"
              variant="tonal"
              @click="check(found.catalog_num)"
            >{{ t('check.checkNow') }}</v-btn>

            <v-btn
              prepend-icon="mdi-open-in-new"
              :to="{ name: 'set-detail', params: { num: found.catalog_num } }"
              variant="text"
            >{{ t('check.openDetail') }}</v-btn>
          </div>

          <PriceHistoryChart
            :new-points="pricesN?.history ?? []"
            :purchase="null"
            :used-points="pricesU?.history ?? []"
          />
        </template>
      </v-card-text>
    </v-card>

    <v-card class="check-recent">
      <v-card-title>{{ t('check.recentTitle') }}</v-card-title>

      <v-data-table
        class="check-table"
        density="compact"
        fixed-header
        :headers="headers"
        hide-default-footer
        hover
        item-value="catalog.catalog_num"
        :items="checks"
        :items-per-page="-1"
        :no-data-text="t('check.recentEmpty')"
        @click:row="(_: unknown, row: { item: Check }) => showStored(row.item.catalog.catalog_num)"
      >

        <template #[`item.year`]="{ item }">{{ item.catalog.year ?? '—' }}</template>
        <template #[`item.new`]="{ item }">{{ money(item.new_value) }}</template>
        <template #[`item.used`]="{ item }">{{ money(item.used_value) }}</template>
        <template #[`item.when`]="{ item }">{{ dateTime(item.checked_at) }}</template>

        <template #[`item.actions`]="{ item }">
          <v-btn
            density="comfortable"
            icon="mdi-close"
            size="small"
            :title="t('check.forget')"
            variant="text"
            @click.stop="forget(item.catalog.catalog_num)"
          />
        </template>
      </v-data-table>
    </v-card>
  </div>
</template>

<style scoped>
  /*
   * Ako Zbierka: stránka na výšku okna (app bar 64 px, okraj kontajnera
   * 2 × 16 px). Tabuľka vyplní, čo ostane, a posúva sa vnútri; keď je nad
   * ňou veľa (detail s grafom), posunie sa stránka a tabuľka ostane
   * aspoň taká, aby sa v nej dalo listovať.
   */
  .check-page--fit {
    height: calc(100dvh - 64px - 32px);
    overflow-y: auto;
  }

  .check-page--fit > * {
    flex: 0 0 auto;
  }

  .check-page--fit > .check-recent {
    flex: 1 1 auto;
    min-height: 320px;
    display: flex;
    flex-direction: column;
  }

  .check-page--fit .check-table {
    flex: 1 1 auto;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }

  .check-page--fit .check-table :deep(.v-table__wrapper) {
    flex: 1 1 auto;
    min-height: 0;
    overflow: auto;
  }

  /* Ako tabuľka Zbierky: pevné šírky, riadok sa nezalamuje, dlhý názov sa skráti. */
  .check-table :deep(table) {
    table-layout: fixed;
    min-width: 900px;
  }

  .check-table :deep(th) {
    white-space: nowrap;
  }

  .check-table :deep(td) {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .check-table :deep(tbody tr) {
    cursor: pointer;
  }
</style>
