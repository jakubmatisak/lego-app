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
  import SetImage from '@/components/SetImage.vue'
  import { count, exactMoney } from '@/utils/format'
  import { imageSrc } from '@/utils/imageSrc'

  const route = useRoute()
  const { t } = useI18n()

  const data = ref<PublicCollection | null>(null)
  const loading = ref(true)
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

  onMounted(async () => {
    try {
      // Zámerne bez klienta s tokenom, táto stránka je anonymná.
      const response = await fetch(`${API_BASE}/public/${route.params.token}`)
      if (!response.ok) {
        notFound.value = true
        return
      }
      data.value = await response.json() as PublicCollection
    } catch {
      notFound.value = true
    } finally {
      loading.value = false
    }
  })
</script>

<template>
  <v-app>
    <v-main class="bg-background">
      <div v-if="loading" class="d-flex justify-center pa-12">
        <v-progress-circular color="primary" indeterminate />
      </div>

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
              <div class="text-h5 font-weight-medium">
                {{ data.owner }}
              </div>

              <div class="text-body-2 text-medium-emphasis">
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
              <div class="text-caption text-medium-emphasis">{{ t('dashboard.invested') }}</div>
              <div class="text-h6">{{ exactMoney(data.invested) }}</div>
            </div>

            <div>
              <div class="text-caption text-medium-emphasis">{{ t('dashboard.marketValue') }}</div>
              <div class="text-h6">{{ exactMoney(data.market_value) }}</div>
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
                  <div class="text-body-2 font-weight-medium text-truncate">{{ wish.name }}</div>

                  <div class="text-caption text-medium-emphasis">
                    {{ wish.catalog_num }}<span v-if="wish.theme"> · {{ wish.theme }}</span><span v-if="wish.year"> · {{ wish.year }}</span>
                  </div>

                  <div v-if="data.show_values && wish.market_price" class="text-body-2 mt-1">
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
                  <div class="text-body-2 font-weight-medium text-truncate">{{ item.name }}</div>

                  <div class="text-caption text-medium-emphasis">
                    {{ item.catalog_num }}<span v-if="item.year"> · {{ item.year }}</span>
                  </div>

                  <div v-if="data.show_values && item.market_total" class="text-body-2 mt-1">
                    {{ exactMoney(item.market_total) }}
                  </div>
                </div>
              </v-card>
            </v-col>
          </v-row>

          <div class="d-flex align-center ga-2 mt-6 text-caption text-medium-emphasis">
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
