<script setup lang="ts">
  /**
   * Verejná stránka zbierky. Beží bez prihlásenia a bez navigácie.
   * Keď odkaz nemá zapnuté sumy, server ich do odpovede vôbec nedá,
   * takže tu nie je čo skrývať.
   */
  import type { PublicCollection } from '@/api/types'
  import { computed, onMounted, ref } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useRoute } from 'vue-router'
  import { API_BASE } from '@/api/client'
  import LoadFailed from '@/components/LoadFailed.vue'
  import PageSkeleton from '@/components/PageSkeleton.vue'
  import SetImage from '@/components/SetImage.vue'
  import { usePageLoad } from '@/composables/usePageLoad'
  import { count, exactMoney, isCurrency, setDisplayCurrency } from '@/utils/format'
  import { imageSrc } from '@/utils/imageSrc'

  const route = useRoute()
  const { t } = useI18n()

  const data = ref<PublicCollection | null>(null)
  const notFound = ref(false)

  const themes = computed(() => {
    if (!data.value) return []
    const names = new Set<string>()
    for (const item of data.value.items) {
      if (item.theme) names.add(item.theme)
    }
    return [...names].toSorted((a, b) => a.localeCompare(b, 'sk'))
  })

  const activeTheme = ref<string | null>(null)

  const visibleItems = computed(() => {
    if (!data.value) return []
    if (!activeTheme.value) return data.value.items
    return data.value.items.filter(item => item.theme === activeTheme.value)
  })

  /**
   * Odkaz neexistuje alebo bol zrušený (404, 410) je odpoveď: „Odkaz
   * neplatí“. Výpadok siete či chyba servera nie: tie ukážu „Nepodarilo sa
   * načítať“ so Skúsiť znova, nie tvrdenie, že odkaz neplatí.
   */
  async function load (): Promise<boolean> {
    // Zámerne bez klienta s tokenom, táto stránka je anonymná.
    const response = await fetch(`${API_BASE}/public/${route.params.token}`)
    if (response.status === 404 || response.status === 410) {
      notFound.value = true
      return true
    }
    if (!response.ok) return false
    data.value = await response.json() as PublicCollection
    // Sumy v mene majiteľa: server pošle kód a kurz, pri vypnutých sumách nič.
    const shown = data.value.currency
    setDisplayCurrency(isCurrency(shown) ? shown : 'EUR', Number(data.value.rate ?? 1), null)
    notFound.value = false
    return true
  }

  /** Bez hornej lišty appky, k Obnoviť stránku sa neprihlasuje. */
  const page = usePageLoad(load, { reload: false })

  onMounted(() => page.run())
</script>

<template>
  <v-app>
    <v-main class="bg-background">
      <!-- Kostra hlavičky a kariet, kým server neodpovedal (usePageLoad). -->
      <div v-if="page.initial" class="pa-6 d-flex flex-column ga-4">
        <v-skeleton-loader type="list-item-avatar-two-line" />
        <PageSkeleton kind="cards" />
      </div>

      <LoadFailed v-else-if="page.error" :loading="page.loading" @retry="page.run()" />

      <v-empty-state
        v-else-if="notFound || !data"
        icon="mdi-link-off"
        :text="t('public.notFoundHint')"
        :title="t('public.notFound')"
      />

      <div v-else>
        <v-sheet border class="px-6 py-5" flat>
          <div class="d-flex align-center ga-4 flex-wrap">
            <v-icon color="primary" icon="mdi-toy-brick" size="36" />

            <div>
              <div class="text-headline-small font-weight-medium">
                {{ data.owner }}
              </div>

              <div class="text-body-medium text-medium-emphasis">
                <template v-if="data.kind === 'wishlist'">
                  {{ t('public.wishlistSubtitle') }} ·
                  {{ t('collection.setsPlural', data.set_count, { named: { count: data.set_count } }) }}
                </template>

                <template v-else>
                  {{ t('public.collectionSubtitle') }} ·
                  {{ t('public.stats', {
                    sets: t('collection.setsPlural', data.set_count, { named: { count: data.set_count } }),
                    items: t('collection.piecesPlural', data.item_count, { named: { count: data.item_count } }),
                    parts: count(data.parts),
                  }) }}
                  <span v-if="data.oldest_year">
                    · {{ t('public.oldest', { year: data.oldest_year }) }}
                  </span>
                </template>
              </div>
            </div>

            <v-chip
              class="ms-auto"
              label
              prepend-icon="mdi-lock-outline"
              size="small"
              variant="tonal"
            >{{ t('public.readOnly') }}</v-chip>
          </div>

          <div v-if="data.show_values && data.kind !== 'wishlist'" class="d-flex ga-6 mt-4 flex-wrap">
            <div>
              <div class="text-body-small text-medium-emphasis">{{ t('dashboard.invested') }}</div>
              <div class="text-title-large font-weight-medium">{{ exactMoney(data.invested) }}</div>
            </div>

            <!-- Bez jedinej ceny pomlčka, nie 0 €; pri čiastočnej počet kusov bez ceny. -->
            <div>
              <div class="text-body-small text-medium-emphasis">{{ t('dashboard.marketValue') }}</div>
              <div class="text-title-large font-weight-medium">{{ exactMoney(data.market_value) }}</div>

              <div v-if="(data.price_missing ?? 0) > 0" class="text-body-small text-medium-emphasis">
                {{ t('totals.noPrice', { count: data.price_missing }) }}
              </div>
            </div>
          </div>
        </v-sheet>

        <v-container class="py-6" fluid>
          <div v-if="themes.length > 1" class="d-flex ga-2 flex-wrap mb-4">
            <v-chip
              :color="activeTheme === null ? 'primary' : undefined"
              label
              :variant="activeTheme === null ? 'tonal' : 'outlined'"
              @click="activeTheme = null"
            >{{ t('collection.status.all') }}</v-chip>

            <v-chip
              v-for="theme in themes"
              :key="theme"
              :color="activeTheme === theme ? 'primary' : undefined"
              label
              :variant="activeTheme === theme ? 'tonal' : 'outlined'"
              @click="activeTheme = activeTheme === theme ? null : theme"
            >{{ theme }}</v-chip>
          </div>

          <!-- Odkaz na Chcem: čo by vlastník rád mal. -->
          <v-row v-if="data.kind === 'wishlist'" dense>
            <v-col
              v-for="wish in data.wishes"
              :key="wish.catalog_num"
              cols="6"
              lg="3"
              md="3"
              sm="4"
              xl="2"
            >
              <v-card border class="h-100 d-flex flex-column" flat>
                <SetImage :alt="wish.name" rounded="0" :size="150" :src="imageSrc(wish.image_url) ?? undefined" />

                <div class="pa-3">
                  <div class="text-body-medium font-weight-medium text-truncate">{{ wish.name }}</div>

                  <div class="text-body-small text-medium-emphasis">
                    {{ wish.catalog_num }}<span v-if="wish.theme"> · {{ wish.theme }}</span><span v-if="wish.year"> · {{ wish.year }}</span>
                  </div>

                  <div v-if="data.show_values && wish.market_price" class="text-body-medium mt-1">
                    {{ exactMoney(wish.market_price) }}
                  </div>
                </div>
              </v-card>
            </v-col>

            <v-col v-if="(data.wishes ?? []).length === 0" cols="12">
              <v-empty-state icon="mdi-heart-outline" :title="t('public.wishlistEmpty')" />
            </v-col>
          </v-row>

          <v-row v-else dense>
            <v-col
              v-for="item in visibleItems"
              :key="item.catalog_num"
              cols="6"
              lg="3"
              md="3"
              sm="4"
              xl="2"
            >
              <v-card border class="h-100 d-flex flex-column" flat>
                <div class="position-relative">
                  <SetImage :alt="item.name" rounded="0" :size="150" :src="imageSrc(item.image_url) ?? undefined" />

                  <v-chip
                    v-if="item.quantity > 1"
                    class="public-badge"
                    color="primary"
                    label
                    size="small"
                    variant="flat"
                  >{{ t('collection.pieces', { count: item.quantity }) }}</v-chip>
                </div>

                <div class="pa-3">
                  <div class="text-body-medium font-weight-medium text-truncate">{{ item.name }}</div>

                  <div class="text-body-small text-medium-emphasis">
                    {{ item.catalog_num }}<span v-if="item.year"> · {{ item.year }}</span>
                  </div>

                  <!-- Server pošle null, keď cenu nemá ani jeden kus; reťazec „0.00“ by prešiel. -->
                  <template v-if="data.show_values">
                    <div v-if="item.market_total !== null && item.market_total !== undefined" class="text-body-medium mt-1">
                      {{ exactMoney(item.market_total) }}
                    </div>

                    <div v-else class="text-body-medium mt-1 text-medium-emphasis">
                      {{ t('collection.unknownPrice') }}
                    </div>
                  </template>
                </div>
              </v-card>
            </v-col>
          </v-row>

          <div class="d-flex align-center ga-2 mt-6 text-body-small text-medium-emphasis">
            <v-icon icon="mdi-toy-brick" size="18" />

            <span>
              {{ t('public.footer') }}
              <template v-if="!data.show_values"> {{ t('public.valuesHidden') }}</template>
            </span>
          </div>
        </v-container>
      </div>
    </v-main>
  </v-app>
</template>

<style scoped>
.public-badge {
  position: absolute;
  top: 8px;
  left: 8px;
}
</style>
