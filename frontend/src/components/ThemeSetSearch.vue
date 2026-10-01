<script setup lang="ts">
  /**
   * Série: nájsť set podľa názvu či čísla a otvoriť jeho sériu a rok.
   * Výsledky sú v plávajúcej ponuke (stránka sa neposúva). Hľadá len medzi
   * známymi setmi (katalóg a stiahnuté vlny Brickset), nič nevolá von;
   * riadok pod poľom to povie aj s počtom.
   */
  import { useDebounceFn } from '@vueuse/core'
  import { computed, onMounted, ref, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useRouter } from 'vue-router'
  import { api } from '@/api/client'
  import SetImage from '@/components/SetImage.vue'
  import { count } from '@/utils/format'
  import { imageSrc } from '@/utils/imageSrc'

  interface Found {
    catalog: { catalog_num: string, name: string, image_url?: string | null }
    theme: string | null
    year: number | null
    owned: number
    wanted: boolean
  }

  const { t } = useI18n()
  const router = useRouter()
  const query = ref('')
  const picked = ref<Found | null>(null)
  const results = ref<Found[]>([])
  const loading = ref(false)
  let asked = 0

  /** Koľko setov je známych; hľadanie nájde len medzi nimi. */
  const known = ref<number | null>(null)
  const hint = computed(() => known.value === null
    ? t('themes.findHintPlain')
    : t('themes.findHint', { count: t('themes.findKnownPlural', known.value, { named: { count: count(known.value) } }) }))

  onMounted(async () => {
    const { data } = await api.GET('/themes/find/count', {})
    known.value = data?.count ?? null
  })

  async function search (text: string): Promise<void> {
    const mine = ++asked
    loading.value = true
    const { data } = await api.GET('/themes/find', { params: { query: { q: text } } })
    if (mine !== asked) {
      return
    }
    results.value = (data ?? []) as Found[]
    loading.value = false
  }

  const later = useDebounceFn((text: string) => {
    search(text).catch(() => {
      loading.value = false
    })
  }, 300)

  watch(query, value => {
    const text = (value ?? '').trim()
    if (text.length < 2) {
      asked++
      results.value = []
      loading.value = false
      return
    }
    later(text)
  })

  /** „40651-1 · Creator 2023“ */
  function subtitle (found: Found): string {
    const where = [found.theme, found.year].filter(Boolean).join(' ')
    return where ? `${found.catalog.catalog_num} · ${where}` : found.catalog.catalog_num
  }

  function open (found: Found | null): void {
    if (!found) {
      return
    }
    picked.value = null
    query.value = ''
    results.value = []
    if (found.theme) {
      router.push({ name: 'theme', params: { theme: found.theme }, query: found.year ? { year: String(found.year) } : {} })
    } else {
      router.push({ name: 'set-detail', params: { num: found.catalog.catalog_num } })
    }
  }
</script>

<template>
  <v-autocomplete
    v-model="picked"
    v-model:search="query"
    clearable
    density="comfortable"
    :hint="hint"
    :item-title="(found: Found) => found.catalog.name"
    :item-value="(found: Found) => found.catalog.catalog_num"
    :items="results"
    :label="t('themes.findSet')"
    :loading="loading"
    :menu-props="{ maxHeight: 420 }"
    :no-data-text="(query ?? '').trim().length < 2 ? t('themes.findType') : t('themes.findNone')"
    no-filter
    persistent-hint
    prepend-inner-icon="mdi-cube-scan"
    return-object
    style="max-width: 480px; flex: 1 1 320px"
    @update:model-value="open"
  >
    <template #item="{ props: itemProps, item }">
      <v-list-item v-bind="itemProps" :subtitle="subtitle(item)" :title="item.catalog.name">
        <template #prepend>
          <SetImage
            :alt="item.catalog.name"
            class="me-3"
            rounded="sm"
            :size="36"
            :src="imageSrc(item.catalog.image_url) ?? undefined"
            style="width: 48px"
          />
        </template>

        <template #append>
          <v-chip
            v-if="item.owned > 0"
            color="primary"
            label
            size="x-small"
            variant="tonal"
          >{{ t('wishlist.owned', { count: t('collection.pieces', { count: item.owned }) }) }}</v-chip>

          <v-chip
            v-else-if="item.wanted"
            label
            prepend-icon="mdi-heart-outline"
            size="x-small"
            variant="tonal"
          >{{ t('nav.wishlist') }}</v-chip>
        </template>
      </v-list-item>
    </template>
  </v-autocomplete>
</template>
