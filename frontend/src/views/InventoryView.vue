<script setup lang="ts">
  import type { Photo, ValuedItem } from '@/api/types'
  /**
   * Súpis zbierky pre poistku. Samostatná stránka bez ponuky a lišty,
   * aby sa dala rovno vytlačiť alebo uložiť ako PDF z prehliadača.
   *
   * PDF zámerne nerobí server: prehliadač slovenskú diakritiku aj fotky
   * zvládne sám, server by na to potreboval knižnicu aj písmo navyše.
   */
  import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { api } from '@/api/client'
  import { useAuthStore } from '@/stores/auth'
  import { isoDate, money, shortDate, toNumber } from '@/utils/format'

  /** Na kus stačia do súpisu tri fotky, zvyšok je v appke. */
  const PHOTOS_PER_ROW = 3

  const { t } = useI18n()
  const auth = useAuthStore()

  const pieces = ref<ValuedItem[]>([])
  const photosByItem = ref<Record<number, Photo[]>>({})
  const urls = ref<Record<number, string>>({})
  const loading = ref(true)

  const today = isoDate()

  const totals = computed(() => {
    let paid = 0
    let value = 0
    let missing = 0
    for (const p of pieces.value) {
      paid += toNumber(p.purchase_price_eur) ?? 0
      if (p.price_source === 'missing') missing++
      else value += toNumber(p.market_value) ?? 0
    }
    return { paid, value, missing }
  })

  function flagsText (item: ValuedItem): string {
    return (item.flags ?? []).map(f => t(`flag.${f}`)).join(', ')
  }

  function valueText (item: ValuedItem): string {
    if (item.price_source === 'missing') return '—'
    const prefix = item.price_source === 'market_approx' ? '≈ ' : ''
    return prefix + money(item.market_value, { decimals: 2 })
  }

  async function loadPhotos (): Promise<void> {
    const { data } = await api.GET('/photos', {})
    const grouped: Record<number, Photo[]> = {}
    for (const photo of data ?? []) (grouped[photo.item_id] ??= []).push(photo)
    photosByItem.value = grouped

    const wanted = Object.values(grouped).flatMap(list => list.slice(0, PHOTOS_PER_ROW))
    await Promise.all(wanted.map(async photo => {
      const res = await api.GET('/photos/{photo_id}', {
        params: { path: { photo_id: photo.id } },
        parseAs: 'blob',
      })
      if (res.data) urls.value[photo.id] = URL.createObjectURL(res.data as Blob)
    }))
  }

  onMounted(async () => {
    const { data } = await api.GET('/items', {
      params: { query: { status: 'owned', sort: 'name' } },
    })
    pieces.value = data ?? []
    await loadPhotos()
    loading.value = false
  })

  onBeforeUnmount(() => {
    for (const url of Object.values(urls.value)) URL.revokeObjectURL(url)
  })

  function print (): void {
    window.print()
  }
</script>

<template>
  <v-app>
    <v-main class="bg-background">
      <div class="inventory">
        <div class="no-print d-flex ga-2 mb-4 flex-wrap">
          <v-btn prepend-icon="mdi-arrow-left" :to="{ name: 'settings', query: { tab: 'data' } }" variant="text">
            {{ t('inventory.back') }}
          </v-btn>

          <v-spacer />

          <v-btn
            color="primary"
            :disabled="loading"
            prepend-icon="mdi-printer-outline"
            variant="flat"
            @click="print"
          >{{ t('inventory.print') }}</v-btn>
        </div>

        <header class="mb-4">
          <h1 class="text-h5 font-weight-bold">{{ t('inventory.title') }}</h1>

          <div class="text-body-2">
            {{ t('inventory.owner') }}: {{ auth.user?.display_name || auth.user?.email }}
            · {{ t('inventory.subtitle', { date: shortDate(today) }) }}
            · {{ t('collection.piecesPlural', pieces.length, { named: { count: pieces.length } }) }}
          </div>
        </header>

        <div v-if="loading" class="d-flex justify-center pa-8 no-print">
          <v-progress-circular color="primary" indeterminate />
        </div>

        <div v-else class="inventory-scroll">
          <table class="inventory-table">
            <thead>
              <tr>
                <th>{{ t('inventory.colItem') }}</th>
                <th>{{ t('inventory.colCondition') }}</th>
                <th>{{ t('inventory.colPlace') }}</th>
                <th>{{ t('inventory.colBought') }}</th>
                <th class="num">{{ t('inventory.colPaid') }}</th>
                <th class="num">{{ t('inventory.colValue') }}</th>
              </tr>
            </thead>

            <tbody>
              <tr v-for="item in pieces" :key="item.id">
                <td>
                  <div class="font-weight-medium">{{ item.catalog.name }}</div>

                  <div class="muted">
                    {{ item.catalog_num }}<span v-if="item.catalog.theme"> · {{ item.catalog.theme }}</span>
                  </div>

                  <div v-if="photosByItem[item.id]?.length" class="inventory-photos">
                    <template v-for="photo in photosByItem[item.id].slice(0, 3)" :key="photo.id">
                      <img v-if="urls[photo.id]" :alt="item.catalog.name" :src="urls[photo.id]">
                    </template>
                  </div>
                </td>

                <td>
                  <div>{{ t(`condition.${item.condition}`) }}</div>
                  <div v-if="flagsText(item)" class="muted">{{ flagsText(item) }}</div>
                </td>

                <td>{{ item.location || '—' }}</td>
                <td>{{ item.purchase_date ? shortDate(item.purchase_date) : '—' }}</td>
                <td class="num">{{ item.purchase_price_eur ? money(item.purchase_price_eur, { decimals: 2 }) : '—' }}</td>
                <td class="num">{{ valueText(item) }}</td>
              </tr>
            </tbody>

            <tfoot>
              <tr>
                <td class="font-weight-bold" colspan="4">{{ t('inventory.total') }}</td>
                <td class="num font-weight-bold">{{ money(totals.paid, { decimals: 2 }) }}</td>
                <td class="num font-weight-bold">{{ money(totals.value, { decimals: 2 }) }}</td>
              </tr>
            </tfoot>
          </table>

          <p class="muted mt-3">{{ t('inventory.note') }}</p>
        </div>
      </div>
    </v-main>
  </v-app>
</template>

<style scoped>
.inventory {
  margin: 0 auto;
  max-width: 1100px;
  padding: 24px 16px;
}

.inventory-scroll {
  overflow-x: auto;
}

.inventory-table {
  border-collapse: collapse;
  font-size: 0.875rem;
  width: 100%;
}

.inventory-table th,
.inventory-table td {
  border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  padding: 8px 10px;
  text-align: left;
  vertical-align: top;
}

.inventory-table th {
  font-weight: 600;
  white-space: nowrap;
}

.inventory-table .num {
  text-align: right;
  white-space: nowrap;
}

.inventory-table tfoot td {
  border-bottom: none;
  border-top: 2px solid currentColor;
}

.muted {
  color: rgba(var(--v-theme-on-surface), 0.6);
  font-size: 0.8125rem;
}

.inventory-photos {
  display: flex;
  gap: 6px;
  margin-top: 6px;
}

.inventory-photos img {
  border-radius: 4px;
  height: 64px;
  object-fit: cover;
  width: 64px;
}

/*
  Pri tlači čierne na bielom bez ohľadu na tmavý režim, bez tlačidiel
  a bez delenia riadku medzi dve strany.
*/
@media print {
  .no-print {
    display: none !important;
  }

  .inventory {
    color: #000;
    max-width: none;
    padding: 0;
  }

  .muted {
    color: #555;
  }

  .inventory-table th,
  .inventory-table td {
    border-bottom-color: #ccc;
  }

  .inventory-table tr {
    break-inside: avoid;
  }

  .inventory-table thead {
    display: table-header-group;
  }
}
</style>
