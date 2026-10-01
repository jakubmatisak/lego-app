<script setup lang="ts">
/**
 * Spoločný rám appky. Na širokej obrazovke bočný panel, na mobile
 * spodná navigácia. V hlavičke je indikátor obnovy cien, ktorý po
 * dobehnutí dávky sám prenačíta Prehľad aj Zbierku.
 */
  import { computed, onMounted, ref, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useRoute, useRouter } from 'vue-router'
  import { useDisplay, useTheme } from 'vuetify'

  import { api } from '@/api/client'
  import ApiUsageDialog from '@/components/ApiUsageDialog.vue'
  import RefreshPricesDialog from '@/components/RefreshPricesDialog.vue'
  import { useDisplayCurrency } from '@/composables/useDisplayCurrency'
  import { useDisplayPrefs } from '@/composables/useDisplayPrefs'
  import { pageBusy, reloadPage } from '@/composables/usePageLoad'
  import { useScanCodes } from '@/scanner/useScanCodes'
  import { useAuthStore } from '@/stores/auth'
  import { useCollectionStore } from '@/stores/collection'
  import { useNotifyStore } from '@/stores/notify'
  import { useProfileStore } from '@/stores/preferences'
  import { usePriceStore } from '@/stores/prices'
  import { useScannerStore } from '@/stores/scanner'
  import { dialogOpen } from '@/utils/dialogOpen'
  import { pricesHidden, setPricesHidden } from '@/utils/format'
  import { sectionRoute } from '@/utils/navigation'

  const { t, locale } = useI18n()
  const display = useDisplay()
  const theme = useTheme()
  const router = useRouter()
  const route = useRoute()

  const auth = useAuthStore()
  const collection = useCollectionStore()
  const prices = usePriceStore()
  const profile = useProfileStore()
  const notify = useNotifyStore()
  const scanner = useScannerStore()

  const mobile = computed(() => display.smAndDown.value)
  const usageOpen = ref(false)
  const refreshOpen = ref(false)
  /** Stránka na výšku okna nepotrebuje dolnú rezervu, stránka by inak pretiekla. */
  const fitScreen = computed(() => route.meta.fitScreen === true && !mobile.value)

  /** Zásady sa zmenili od posledného prečítania (alebo účet vznikol pred nimi). */
  const privacyOutdated = computed(() => {
    const u = auth.user
    return Boolean(u && u.privacy_current && u.privacy_version !== u.privacy_current)
  })

  async function acceptPrivacy (): Promise<void> {
    await api.POST('/auth/me/privacy', {})
    await auth.loadMe()
  }

  const navItems = computed(() => [
    {
      to: { name: 'dashboard' },
      icon: 'mdi-view-dashboard-outline',
      label: t('nav.dashboard'),
      routes: ['dashboard'],
    },
    {
      to: { name: 'collection' },
      icon: 'mdi-layers-outline',
      label: t('nav.collection'),
      // Len sety: figúrky zo sérií sú vo Figúrkach, s vlastným počtom.
      badge: collection.summary?.collection_set_count,
      // Detail setu aj pridávanie patria do Zbierky, nech ponuka nepreskakuje.
      routes: ['collection', 'set-detail', 'add-set'],
    },
    {
      to: { name: 'minifigs' },
      icon: 'mdi-account-multiple-outline',
      label: t('nav.minifigs'),
      badge: collection.summary?.series_figures || undefined,
      routes: ['minifigs', 'minifig-series'],
    },
    {
      to: { name: 'themes' },
      icon: 'mdi-shape-outline',
      label: t('nav.themes'),
      badge: collection.summary?.theme_count || undefined,
      routes: ['themes', 'theme'],
    },
    {
      to: { name: 'wishlist' },
      icon: 'mdi-heart-outline',
      label: t('nav.wishlist'),
      routes: ['wishlist'],
      badge: collection.summary?.wishlist_count || undefined,
      // Len keď niečo kleslo na cieľovú cenu, inak by číslo nič nehovorilo.
      alert: collection.summary?.wishlist_hits || undefined,
    },
    { to: { name: 'price-check' }, icon: 'mdi-tag-search-outline', label: t('nav.priceCheck'), routes: ['price-check'] },
    { to: { name: 'settings' }, icon: 'mdi-cog-outline', label: t('nav.settings'), routes: ['settings'] },
  ]
    // Série sú z Brickset, Figúrky z Rebrickable: bez kľúča by boli prázdne.
    .filter(item => item.to.name !== 'themes' || auth.can('brickset.themes'))
    .filter(item => item.to.name !== 'minifigs' || auth.can('rebrickable.set')))

  /**
   * Zvýraznenie sa riadi menom trasy, nie porovnaním adries. Prehľad býva
   * na "/" a ako predpona sedí na každú trasu, takže by svietil stále.
   * Detail figúrky otvorený z Figúrok ostane pri Figúrkach (`sectionRoute`).
   */
  function isActive (item: { routes: string[] }): boolean {
    return item.routes.includes(sectionRoute(route.name as string | undefined, route.query))
  }

  const pageTitle = computed(() => {
    const name = route.name as string | undefined
    switch (name) {
      case 'dashboard': { return t('dashboard.title')
      }
      case 'collection': { return t('collection.title')
      }
      case 'add-set': { return t('add.title')
      }
      case 'minifigs':
      case 'minifig-series': { return t('minifigs.title')
      }
      case 'themes':
      case 'theme': { return t('themes.title')
      }
      case 'wishlist': { return t('wishlist.title')
      }
      case 'price-check': { return t('check.title')
      }
      case 'settings': { return t('settings.title')
      }
      default: { return t('app.name')
      }
    }
  })

  /** Tmavý/svetlý režim a zúžené menu sa pamätajú pri účte (preferences.display). */
  const prefs = useDisplayPrefs()
  const displayCurrency = useDisplayCurrency()
  const rail = ref(false)

  function toggleTheme (): void {
    prefs.setTheme(theme.global.name.value === 'dark' ? 'light' : 'dark')
  }

  /** Skryť ceny: pri ukazovaní portfólia niekomu inému, pamätá sa pri účte. */
  function toggleHidePrices (): void {
    setPricesHidden(!pricesHidden.value)
    prefs.setHidePrices(pricesHidden.value)
  }

  function toggleRail (): void {
    rail.value = !rail.value
    prefs.setRail(rail.value)
  }

  function switchLocale (): void {
    const next = locale.value === 'sk' ? 'en' : 'sk'
    locale.value = next
    auth.updateProfile({ locale: next })
  }

  async function logout (): Promise<void> {
    // Odhlásenie načíta stránku nanovo (auth.logout), žiadne dáta účtu neostanú.
    await auth.logout()
  }

  /**
   * Obnovu cien spúšťa len používateľ týmto tlačidlom. Kvóta je 100 volaní
   * na deň a je osobná, takže nemá zmysel ju míňať pri každom prihlásení.
   * Pred spustením dialóg ukáže minuté volania a spýta sa, koľko cien.
   */
  async function refreshPrices (count: number): Promise<void> {
    await prices.refreshEverything(() => {
      collection.refreshAll()
      auth.loadKeys()
    }, count)
  }

  /**
   * Obnoviť stránku: znova načíta dáta otvorenej stránky a súhrn za počtami
   * v ponuke, bez načítania celej stránky (filtre, posunutie aj rozpísaný
   * formulár ostanú). Len GET na vlastný server, nikdy ceny ani Brickset;
   * načítania sa prihlasujú cez `usePageLoad` / `onPageReload`.
   */
  const reloading = ref(false)
  async function reloadCurrent (): Promise<void> {
    if (reloading.value) return
    reloading.value = true
    try {
      await reloadPage(() => collection.loadSummary())
    } finally {
      reloading.value = false
    }
  }

  const refreshHint = computed(() => {
    if (!auth.hasPriceKey) return t('prices.noKey')
    if (prices.quotaExhausted) return t('settings.quotaSpent')
    return t('prices.refreshHint', { count: auth.keys?.calls_left ?? 0 })
  })

  // --- V dnešných peniazoch ---------------------------------------------

  /** Mesiac indexu ako „08/2026“. */
  const realMonth = computed(() => {
    const month = collection.summary?.real_month
    if (!month) return null
    const [year, mm] = month.split('-')
    return `${mm}/${year}`
  })
  /** Zapnuté, súhrn už prišiel, a index predsa chýba (Eurostat nedostupný). */
  const realFailed = computed(() =>
    collection.real && collection.summary !== null && !collection.summary.real_month,
  )
  const realHint = computed(() => {
    if (!collection.real) return t('inflation.hintOff')
    if (realFailed.value) return t('inflation.failed')
    return t('inflation.hintOn', { month: realMonth.value ?? '…' })
  })

  /*
   * Sken z ručnej čítačky na ktorejkoľvek obrazovke: prejsť na Pridať set
   * a kód tam vyhľadať. Pridať set sa prihlási nad layout a ďalšie skeny
   * spracuje samo (počet, automatické uloženie).
   */
  useScanCodes(code => {
    // Otvorený dialóg má neuložené úpravy; sken by ho zavrel.
    if (dialogOpen()) {
      notify.info(t('scan.closeDialogFirst'))
      return
    }
    // Schránka drží poradie aj viacerých skenov, kým sa Pridať set otvára.
    scanner.deliver(code)
    if (route.name !== 'add-set') router.push({ name: 'add-set' })
  }, { fallback: true })

  function toggleReal (): void {
    collection.real = !collection.real
    prefs.setReal(collection.real)
  }

  watch(() => collection.real, () => {
    collection.refreshAll()
  })

  onMounted(async () => {
    // Prepínač sa pamätá pri účte. Zapnutý prenačíta sumy cez watch vyššie.
    // Téma z prehliadača hneď, nech sa nezablyskne; potom platí to, čo je pri účte.
    prefs.applyLocalTheme()
    profile.load().then(() => {
      const saved = prefs.current()
      if (saved.real) collection.real = true
      rail.value = saved.rail
      setPricesHidden(saved.hidePrices)
      if (saved.theme) prefs.applyTheme(saved.theme)
      // Mena zobrazenia: kurz ECB sa pýta len pri inej mene než euro.
      if (saved.currency !== 'EUR') displayCurrency.apply(saved.currency)
    })
    if (auth.user?.locale) locale.value = auth.user.locale

    // Čísla v ponuke potrebujú súhrn hneď, nie až po otvorení Prehľadu či Zbierky.
    if (!collection.summary) collection.loadDashboard()

    // Dávka mohla ostať bežať z predchádzajúcej obrazovky, tu ju dosledujeme.
    prices.watchRefresh(() => {
      collection.refreshAll()
    })
  })
</script>

<template>
  <v-app>
    <!-- Zúžené menu (rail) nechá viac miesta obrazovke; pamätá sa pri účte. -->
    <v-navigation-drawer
      v-if="!mobile"
      permanent
      :rail="rail"
      rail-width="56"
      width="256"
    >
      <!-- Zúžené: len logo v strede, rovnako ako ikony položiek pod ním. -->
      <div class="d-flex align-center ga-3" :class="rail ? 'justify-center' : 'px-4'" style="height: 64px">
        <v-icon color="primary" icon="mdi-toy-brick" size="28" />
        <span v-if="!rail" class="text-title-large font-weight-bold text-no-wrap">{{ t('app.name') }}</span>
      </div>

      <v-list density="comfortable" nav>
        <v-tooltip
          v-for="item in navItems"
          :key="item.label"
          :disabled="!rail"
          location="end"
          :text="item.badge ? `${item.label} · ${item.badge}` : item.label"
        >
          <template #activator="{ props: tip }">
            <v-list-item
              v-bind="tip"
              :active="isActive(item)"
              :prepend-icon="item.icon"
              rounded="xl"
              :title="item.label"
              :to="item.to"
            >
              <template v-if="!rail && (item.badge || item.alert)" #append>
                <v-chip
                  v-if="item.alert"
                  class="me-2"
                  color="positive"
                  prepend-icon="mdi-bell-ring-outline"
                  size="x-small"
                  variant="flat"
                >{{ item.alert }}</v-chip>

                <!-- Odsadené od okraja zvýrazneného riadku, inak sa naň lepí. -->
                <span v-else class="text-body-small text-medium-emphasis me-2">{{ item.badge }}</span>
              </template>
            </v-list-item>
          </template>
        </v-tooltip>
      </v-list>

      <template #append>
        <div v-if="!rail" class="pa-4 d-flex flex-column ga-2">
          <v-card v-if="prices.status" class="pa-3" color="surface-variant" flat>
            <div class="d-flex align-center ga-2">
              <v-icon
                :class="{ 'refresh-spin': prices.running }"
                icon="mdi-refresh"
                size="18"
              />

              <div class="text-body-small">
                <div>{{ prices.running ? t('prices.refreshing') : t('prices.refreshDone') }}</div>

                <div v-if="prices.running" class="font-weight-medium">
                  {{ t('prices.refreshingCount', { count: prices.pending }) }}
                </div>
              </div>
            </div>
          </v-card>

          <v-btn
            prepend-icon="mdi-share-variant-outline"
            :to="{ name: 'settings', query: { tab: 'sharing' } }"
            variant="outlined"
          >{{ t('settings.shareTitle') }}</v-btn>
        </div>

        <div class="pa-2 d-flex" :class="rail ? 'justify-center' : 'justify-end'">
          <v-btn
            :icon="rail ? 'mdi-chevron-double-right' : 'mdi-chevron-double-left'"
            size="small"
            :title="rail ? t('nav.expand') : t('nav.collapse')"
            variant="text"
            @click="toggleRail"
          />
        </div>
      </template>
    </v-navigation-drawer>

    <v-app-bar flat :height="64">
      <v-app-bar-title>
        <div class="d-flex align-center ga-2">
          <v-icon v-if="mobile" color="primary" icon="mdi-toy-brick" size="24" />
          <span class="text-title-large font-weight-medium">{{ pageTitle }}</span>
        </div>
      </v-app-bar-title>

      <v-chip
        v-if="prices.running"
        class="me-2"
        prepend-icon="mdi-refresh"
        size="small"
        variant="tonal"
      >{{ t('prices.refreshing') }}</v-chip>

      <!-- V dnešných peniazoch: kúpne ceny prepočítané infláciou. -->
      <v-tooltip location="bottom" max-width="320" :text="realHint">
        <template #activator="{ props: tipProps }">
          <v-chip
            v-if="collection.real && !mobile"
            v-bind="tipProps"
            class="me-1"
            :color="realFailed ? 'warning' : 'primary'"
            prepend-icon="mdi-cash-clock"
            variant="tonal"
            @click="toggleReal"
          >
            {{ realFailed ? t('inflation.unavailable') : t('inflation.chip', { month: realMonth ?? '…' }) }}
            <v-icon class="ms-1" icon="mdi-close" size="small" />
          </v-chip>

          <v-btn
            v-else
            v-bind="tipProps"
            :color="collection.real ? (realFailed ? 'warning' : 'primary') : undefined"
            icon="mdi-cash-clock"
            @click="toggleReal"
          />
        </template>
      </v-tooltip>

      <!-- Denné limity cudzích služieb a história volaní. -->
      <v-btn icon="mdi-gauge" :title="t('usage.title')" @click="usageOpen = true" />

      <!--
        Znova načíta dáta stránky z vlastného servera; cudzie služby nevolá.
        Na telefóne je v menu účtu, inak by sa názov stránky nezmestil.
      -->
      <v-btn v-if="!mobile" icon :title="t('nav.reload')" @click="reloadCurrent">
        <v-icon :class="{ 'refresh-spin': reloading }" icon="mdi-refresh" />
      </v-btn>

      <!-- Ceny sa neobnovujú samé, iba týmto tlačidlom. Bez zdroja cien sa neukáže. -->
      <v-tooltip v-if="auth.can('brickeconomy.prices')" location="bottom" :text="refreshHint">
        <template #activator="{ props: tipProps }">
          <div v-bind="tipProps">
            <v-btn
              :disabled="!auth.hasPriceKey || prices.quotaExhausted"
              icon="mdi-cloud-refresh-outline"
              :loading="prices.running"
              @click="refreshOpen = true"
            />
          </div>
        </template>
      </v-tooltip>

      <!-- Skryť ceny: aj na telefóne, tam sa portfólio ukazuje najčastejšie. -->
      <v-btn
        :color="pricesHidden ? 'primary' : undefined"
        :icon="pricesHidden ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
        :title="pricesHidden ? t('nav.showPrices') : t('nav.hidePrices')"
        @click="toggleHidePrices"
      />

      <!-- Na telefóne sú režim a jazyk v menu účtu, inak by sa názov stránky nezmestil. -->
      <template v-if="!mobile">
        <v-btn
          :icon="theme.global.name.value === 'dark' ? 'mdi-weather-sunny' : 'mdi-weather-night'"
          @click="toggleTheme"
        />

        <v-btn class="text-body-medium" variant="text" @click="switchLocale">
          {{ locale.toUpperCase() }}
        </v-btn>
      </template>

      <v-menu>
        <template #activator="{ props: menuProps }">
          <v-btn class="me-2" icon v-bind="menuProps">
            <v-avatar color="primary" size="36">
              <span class="text-body-medium">{{ auth.initials }}</span>
            </v-avatar>
          </v-btn>
        </template>

        <v-list density="comfortable">
          <v-list-item :subtitle="auth.user?.email" :title="auth.user?.display_name ?? ''" />
          <v-divider />

          <v-list-item
            v-if="auth.isAdmin"
            prepend-icon="mdi-account-group-outline"
            :title="t('nav.admin')"
            :to="{ name: 'settings', query: { tab: 'users' } }"
          />

          <template v-if="mobile">
            <v-list-item
              :disabled="reloading"
              prepend-icon="mdi-refresh"
              :title="t('nav.reload')"
              @click="reloadCurrent"
            />

            <v-list-item
              :prepend-icon="theme.global.name.value === 'dark' ? 'mdi-weather-sunny' : 'mdi-weather-night'"
              :title="theme.global.name.value === 'dark' ? t('nav.lightMode') : t('nav.darkMode')"
              @click="toggleTheme"
            />

            <v-list-item
              prepend-icon="mdi-translate"
              :title="t('nav.language', { next: locale === 'sk' ? 'English' : 'Slovenčina' })"
              @click="switchLocale"
            />

            <v-divider />
          </template>

          <v-list-item
            prepend-icon="mdi-logout"
            :title="t('nav.logout')"
            @click="logout"
          />
        </v-list>
      </v-menu>

      <!-- Stránka sa načítava znova (filter, Obnoviť stránku): staré dáta ostanú, svieti len pruh. -->
      <v-progress-linear
        absolute
        :active="pageBusy"
        color="primary"
        height="2"
        indeterminate
        location="bottom"
      />
    </v-app-bar>

    <v-main>
      <v-container :class="fitScreen ? 'py-4' : 'pb-16'" fluid>
        <v-alert
          v-if="privacyOutdated"
          class="mb-4"
          density="compact"
          type="info"
          variant="tonal"
        >
          <div class="d-flex align-center ga-2 flex-wrap">
            <span>{{ t('privacy.updated') }}</span>
            <v-btn size="small" to="/sukromie" variant="text">{{ t('privacy.title') }}</v-btn>
            <v-spacer />
            <v-btn color="primary" size="small" variant="flat" @click="acceptPrivacy">{{ t('privacy.understood') }}</v-btn>
          </div>
        </v-alert>

        <router-view />
      </v-container>
    </v-main>

    <v-bottom-navigation v-if="mobile" class="app-bottom-nav" grow :height="64">
      <v-btn v-for="item in navItems" :key="item.label" :active="isActive(item)" :to="item.to">
        <v-icon :icon="item.icon" />
        <span class="app-bottom-nav__label">{{ item.label }}</span>
      </v-btn>
    </v-bottom-navigation>

    <ApiUsageDialog v-model="usageOpen" />
    <RefreshPricesDialog v-model="refreshOpen" @confirm="refreshPrices" />

    <!-- Oznámenia celej appky (stores/notify.ts). -->
    <v-snackbar-queue v-model="notify.queue" total-visible="3">
      <template #actions="{ item, props: close }">
        <v-btn
          v-if="notify.actionFor(item['data-notice'])"
          @click="notify.run(item['data-notice']); close.onClick()"
        >{{ notify.actionFor(item['data-notice'])?.label }}</v-btn>

        <v-btn icon="mdi-close" :title="t('common.close')" v-bind="close" />
      </template>
    </v-snackbar-queue>
  </v-app>
</template>

<style scoped>
/*
 * Šesť položiek sa na telefón nezmestí s najmenšou šírkou Vuetify (80 px,
 * spolu 480 px na 375 px displeji), okraje by vytŕčali. Položky sa preto
 * delia o šírku rovným dielom a dlhý popis sa skráti.
 */
.app-bottom-nav :deep(.v-bottom-navigation__content > .v-btn) {
  min-width: 0;
  padding: 0 2px;
}

.app-bottom-nav :deep(.v-btn__content) {
  min-width: 0;
  max-width: 100%;
}

.app-bottom-nav__label {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.refresh-spin {
  animation: spin 1.4s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
