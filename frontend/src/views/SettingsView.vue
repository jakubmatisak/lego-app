<script setup lang="ts">
  /**
   * Nastavenia vrátane správy odkazov na pozretie. Prepínač súm určuje,
   * či server ceny do verejnej odpovede vôbec vloží.
   */
  import type { ShareLink, User } from '@/api/types'
  import { computed, onMounted, ref } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useRoute } from 'vue-router'
  import { useTheme } from 'vuetify'
  import { api } from '@/api/client'
  import AccountDataCard from '@/components/AccountDataCard.vue'
  import AppVersion from '@/components/AppVersion.vue'
  import ExportCsvButton from '@/components/ExportCsvButton.vue'
  import FormMemoryCard from '@/components/FormMemoryCard.vue'
  import ImportPanel from '@/components/ImportPanel.vue'
  import LoadFailed from '@/components/LoadFailed.vue'
  import PageSkeleton from '@/components/PageSkeleton.vue'
  import ShareDialog from '@/components/ShareDialog.vue'
  import SourcesPanel from '@/components/SourcesPanel.vue'
  import { currencyApplying, useDisplayCurrency } from '@/composables/useDisplayCurrency'
  import { useDisplayPrefs } from '@/composables/useDisplayPrefs'
  import { onPageReload, usePageLoad } from '@/composables/usePageLoad'
  import { useAuthStore } from '@/stores/auth'
  import { useNotifyStore } from '@/stores/notify'
  import { usePriceStore } from '@/stores/prices'
  import { CURRENCIES, type CurrencyCode, dateTime, displayCurrency, rateText, shortDate } from '@/utils/format'

  const { t, locale } = useI18n()
  const notify = useNotifyStore()
  const route = useRoute()
  const theme = useTheme()
  const auth = useAuthStore()
  const prices = usePriceStore()

  const tab = ref((route.query.tab as string) || 'account')

  const displayName = ref(auth.user?.display_name ?? '')
  const currentPassword = ref('')
  const newPassword = ref('')

  const display = useDisplayPrefs()
  const links = ref<ShareLink[]>([])
  const users = ref<User[]>([])

  const isDark = computed({
    get: () => theme.global.name.value === 'dark',
    // Pri účte, nie len v prehliadači: platí aj na telefóne.
    set: (value: boolean) => display.setTheme(value ? 'dark' : 'light'),
  })

  // --- mena zobrazenia ---------------------------------------------------

  /*
   * Ukladá sa všetko v eurách, mena je len prepočet dnešným kurzom ECB
   * (`utils/format.ts`). Bez schopnosti ecb.rates ostáva euro.
   */
  const currencyPrefs = useDisplayCurrency()
  const currencyCode = computed(() => display.current().currency)
  const currencyItems = computed(() => CURRENCIES.map(code => ({ value: code, title: t(`currency.names.${code}`) })))
  const ratesBlocked = computed(() => auth.keys !== null && !auth.can('ecb.rates'))
  const currencyLoading = ref(false)
  const currencyLine = computed(() => {
    const code = currencyCode.value
    if (ratesBlocked.value && code !== 'EUR') return t('currency.blocked')
    if (code === 'EUR') return t('currency.euroHint')
    if (currencyLoading.value || currencyApplying.value) return t('currency.loading')
    const shown = displayCurrency.value
    if (shown.code !== code) return t('currency.rateFailed')
    return t('currency.rate', { rate: rateText(code, shown.rate), day: shortDate(shown.day) })
  })

  async function chooseCurrency (code: CurrencyCode): Promise<void> {
    currencyLoading.value = true
    try {
      await currencyPrefs.choose(code)
    } finally {
      currencyLoading.value = false
    }
  }

  const foreignEntry = computed({
    get: () => display.current().foreignEntry,
    set: (value: boolean) => display.setForeignEntry(value),
  })

  function publicUrl (token: string): string {
    return `${window.location.origin}/z/${token}`
  }

  async function loadLinks (): Promise<boolean> {
    const { data, error } = await api.GET('/share', {})
    if (error || !data) return false
    links.value = data
    return true
  }

  async function loadUsers (): Promise<boolean> {
    if (!auth.isAdmin) return true
    const { data, error } = await api.GET('/admin/users', {})
    if (error || !data) return false
    users.value = data
    return true
  }

  /*
   * Zoznamy odkazov a používateľov: kým server neodpovedal, kostra riadkov,
   * nie „Zatiaľ žiadny odkaz“ (usePageLoad). Obnoviť stránku ich načíta znova.
   */
  const linksPage = usePageLoad(loadLinks)
  const usersPage = usePageLoad(loadUsers)

  // --- nastavenia appky (len správca) ---------------------------------------

  const appSettings = ref<{ allow_registration: boolean, env_default: boolean } | null>(null)
  const savingApp = ref(false)
  /** Prevádzkovateľ pre zásady ochrany súkromia (GDPR): meno a kontakt. */
  const operatorName = ref('')
  const operatorEmail = ref('')

  async function loadAppSettings (): Promise<void> {
    if (!auth.isAdmin) return
    const { data } = await api.GET('/admin/settings', {})
    appSettings.value = data ?? null
    operatorName.value = data?.operator_name ?? ''
    operatorEmail.value = data?.operator_email ?? ''
  }

  async function saveOperator (): Promise<void> {
    const { error: err } = await api.PATCH('/admin/settings', {
      body: { operator_name: operatorName.value.trim(), operator_email: operatorEmail.value.trim() },
    })
    if (err) {
      notify.error(err, t('notice.saveFailed'))
      return
    }
    notify.success(t('settings.operatorSaved'))
    auth.loadProviders()
  }

  /** Platí hneď: prihlasovacia stránka podľa toho ukáže alebo skryje „Nový účet“. */
  async function setRegistration (allowed: boolean): Promise<void> {
    savingApp.value = true
    const { data, error: err } = await api.PATCH('/admin/settings', {
      body: { allow_registration: allowed },
    })
    savingApp.value = false
    if (err) {
      notify.error(err, t('notice.saveFailed'))
      return
    }
    notify.success(t('notice.registrationSaved'))
    appSettings.value = data ?? null
    auth.loadProviders()
  }

  /** Odkaz na zbierku, alebo na zoznam Chcem (napríklad pre rodinu). */
  /** Dialóg: zdieľať všetko, alebo vybrané sety. */
  const shareKind = ref<'collection' | 'wishlist'>('collection')
  const shareDialog = ref(false)
  function startLink (kind: 'collection' | 'wishlist'): void {
    shareKind.value = kind
    shareDialog.value = true
  }

  async function createLink (kind: 'collection' | 'wishlist', catalogNums: string[] | null = null): Promise<void> {
    const { error: err } = await api.POST('/share', {
      body: { show_values: false, kind, catalog_nums: catalogNums },
    })
    if (err) {
      notify.error(err, t('notice.saveFailed'))
      return
    }
    notify.success(t('notice.linkCreated'))
    await loadLinks()
  }

  async function toggleValues (link: ShareLink, value: boolean): Promise<void> {
    const { error: err } = await api.PATCH('/share/{link_id}', {
      params: { path: { link_id: link.id } },
      body: { show_values: value },
    })
    if (err) {
      notify.error(err, t('notice.saveFailed'))
      return
    }
    notify.success(t('notice.saved'))
    await loadLinks()
  }

  async function revokeLink (link: ShareLink): Promise<void> {
    const { error: err } = await api.DELETE('/share/{link_id}', {
      params: { path: { link_id: link.id } },
    })
    if (err) {
      notify.error(err, t('notice.deleteFailed'))
      return
    }
    notify.success(t('notice.linkRevoked'))
    await loadLinks()
  }

  async function copyLink (link: ShareLink): Promise<void> {
    try {
      await navigator.clipboard.writeText(publicUrl(link.token))
      notify.success(t('settings.shareCopied'))
    } catch {
      // Schránka nie je dostupná (http): adresa aspoň na očiach, dá sa odpísať.
      notify.info(publicUrl(link.token))
    }
  }

  async function saveProfile (): Promise<void> {
    const ok = await auth.updateProfile({
      display_name: displayName.value || null,
      locale: locale.value,
      current_password: currentPassword.value || null,
      new_password: newPassword.value || null,
    })
    if (ok) {
      notify.success(t('notice.profileSaved'))
      currentPassword.value = ''
      newPassword.value = ''
    } else {
      notify.error(auth.error, t('notice.saveFailed'))
    }
  }

  async function toggleUser (user: User, active: boolean): Promise<void> {
    const { error: err } = await api.PATCH('/admin/users/{user_id}', {
      params: { path: { user_id: user.id } },
      body: { is_active: active },
    })
    if (err) {
      notify.error(err, t('notice.saveFailed'))
      return
    }
    notify.success(t('notice.userSaved'))
    await loadUsers()
  }

  // Nastavenia appky (správca) aj pri Obnoviť stránku.
  onPageReload(loadAppSettings)

  onMounted(() => {
    linksPage.run()
    usersPage.run()
    loadAppSettings()
    prices.fetchStatus()
  })
</script>

<template>
  <!--
    Jedna šírka pre všetky záložky, inak by sa menu pri prepnutí posúvalo.
    Formuláre sú v nej užšie (settings-narrow) a zarovnané doľava pod menu,
    širokú tabuľku potrebuje len náhľad importu.
  -->
  <div class="mx-auto settings-page">
    <v-tabs v-model="tab" class="mb-4">
      <v-tab value="account">{{ t('settings.tabs.account') }}</v-tab>
      <v-tab value="sharing">{{ t('settings.tabs.sharing') }}</v-tab>
      <v-tab value="language">{{ t('settings.tabs.language') }}</v-tab>
      <v-tab value="data">{{ t('settings.tabs.data') }}</v-tab>
      <v-tab value="forms">{{ t('settings.tabs.forms') }}</v-tab>
      <v-tab value="import">{{ t('settings.tabs.import') }}</v-tab>
      <v-tab v-if="auth.isAdmin" value="users">{{ t('settings.tabs.users') }}</v-tab>
      <v-tab v-if="auth.isAdmin" value="app">{{ t('settings.tabs.app') }}</v-tab>
    </v-tabs>

    <v-window v-model="tab">
      <v-window-item class="settings-narrow" value="account">
        <v-card border class="pa-4 d-flex flex-column ga-3" flat>
          <v-text-field v-model="displayName" :label="t('settings.displayName')" />
          <v-text-field :label="t('auth.email')" :model-value="auth.user?.email" readonly />
          <v-divider class="my-2" />
          <div class="text-title-small">{{ t('settings.changePassword') }}</div>

          <v-text-field
            v-model="currentPassword"
            autocomplete="current-password"
            :label="t('settings.currentPassword')"
            type="password"
          />

          <v-text-field
            v-model="newPassword"
            autocomplete="new-password"
            :hint="t('auth.passwordHint')"
            :label="t('settings.newPassword')"
            type="password"
          />

          <v-btn class="align-self-start" color="primary" @click="saveProfile">
            {{ t('settings.save') }}
          </v-btn>
        </v-card>

        <AccountDataCard class="mt-4" />
      </v-window-item>

      <v-window-item class="settings-narrow" value="sharing">
        <div class="d-flex flex-column ga-4">
          <div class="d-flex align-start ga-4 flex-wrap">
            <div class="flex-grow-1" style="min-width: 260px">
              <div class="text-title-large font-weight-medium">{{ t('settings.shareTitle') }}</div>
              <div class="text-body-medium text-medium-emphasis">{{ t('settings.shareIntro') }}</div>
            </div>

            <v-menu>
              <template #activator="{ props: menu }">
                <v-btn v-bind="menu" append-icon="mdi-menu-down" color="primary" prepend-icon="mdi-plus">
                  {{ t('settings.shareCreate') }}
                </v-btn>
              </template>

              <v-list density="compact">
                <v-list-item
                  prepend-icon="mdi-layers-outline"
                  :subtitle="t('settings.shareKindCollectionHint')"
                  :title="t('settings.shareKindCollection')"
                  @click="startLink('collection')"
                />

                <v-list-item
                  prepend-icon="mdi-heart-outline"
                  :subtitle="t('settings.shareKindWishlistHint')"
                  :title="t('settings.shareKindWishlist')"
                  @click="startLink('wishlist')"
                />
              </v-list>
            </v-menu>
          </div>

          <PageSkeleton v-if="linksPage.initial" :count="2" kind="rows" />

          <LoadFailed v-else-if="linksPage.error" :loading="linksPage.loading" @retry="linksPage.run()" />

          <v-empty-state
            v-else-if="links.length === 0"
            icon="mdi-share-variant-outline"
            :title="t('settings.shareEmpty')"
          />

          <v-card
            v-for="link in links"
            :key="link.id"
            border
            class="pa-4"
            flat
          >
            <div class="d-flex align-center ga-3 flex-wrap">
              <v-icon :icon="link.kind === 'wishlist' ? 'mdi-heart-outline' : 'mdi-layers-outline'" />

              <v-chip label size="small" variant="outlined">
                {{ link.kind === 'wishlist' ? t('settings.shareKindWishlist') : t('settings.shareKindCollection') }}
              </v-chip>

              <v-chip v-if="link.catalog_nums" label size="small" variant="tonal">
                {{ t('share.chosenCount', { sets: t('collection.setsPlural', link.catalog_nums.length, { named: { count: link.catalog_nums.length } }) }) }}
              </v-chip>

              <code class="text-body-medium">{{ publicUrl(link.token) }}</code>

              <v-chip
                :color="link.show_values ? 'secondary' : undefined"
                label
                :prepend-icon="link.show_values ? 'mdi-eye-outline' : 'mdi-eye-off-outline'"
                size="small"
                variant="tonal"
              >
                {{ link.show_values ? t('settings.shareValuesOn').split(',')[0] : t('settings.shareValuesOff').split(',')[0] }}
              </v-chip>

              <v-spacer />

              <v-btn
                prepend-icon="mdi-content-copy"
                size="small"
                variant="outlined"
                @click="copyLink(link)"
              >{{ t('settings.shareCopy') }}</v-btn>

              <v-btn color="negative" size="small" variant="text" @click="revokeLink(link)">
                {{ t('settings.shareRevoke') }}
              </v-btn>
            </div>

            <v-divider class="my-3" />

            <div class="d-flex align-center ga-4 flex-wrap">
              <v-switch
                color="primary"
                density="compact"
                hide-details
                :label="t('settings.shareShowValues')"
                :model-value="link.show_values"
                @update:model-value="value => toggleValues(link, Boolean(value))"
              />

              <span class="text-body-medium text-medium-emphasis">
                {{ link.show_values ? t('settings.shareValuesOn') : t('settings.shareValuesOff') }}
              </span>

              <span class="ms-auto text-body-medium text-medium-emphasis">
                {{ link.last_viewed_at
                  ? t('settings.shareLastViewed', { when: dateTime(link.last_viewed_at) })
                  : t('settings.shareNeverViewed') }}
              </span>
            </div>
          </v-card>

          <v-alert density="comfortable" icon="mdi-shield-lock-outline" variant="tonal">
            <span class="text-body-medium">{{ t('settings.shareNote') }}</span>
          </v-alert>
        </div>
      </v-window-item>

      <v-window-item class="settings-narrow" value="language">
        <v-card border class="pa-4 d-flex flex-column ga-4" flat>
          <v-select
            v-model="locale"
            item-title="title"
            item-value="value"
            :items="[{ value: 'sk', title: 'Slovenčina' }, { value: 'en', title: 'English' }]"
            :label="t('settings.language')"
            @update:model-value="auth.updateProfile({ locale })"
          />

          <div>
            <v-select
              :disabled="ratesBlocked && currencyCode === 'EUR'"
              hide-details
              item-title="title"
              item-value="value"
              :items="currencyItems"
              :label="t('currency.label')"
              :loading="currencyLoading"
              :model-value="currencyCode"
              @update:model-value="(code: CurrencyCode) => chooseCurrency(code)"
            />

            <div class="text-body-medium text-medium-emphasis mt-2" data-test="currency-rate">{{ currencyLine }}</div>
          </div>

          <v-switch
            v-model="foreignEntry"
            color="primary"
            :disabled="ratesBlocked"
            :hint="t('currency.foreignEntryHint')"
            :label="t('currency.foreignEntry')"
            persistent-hint
          />

          <v-switch
            v-model="isDark"
            color="primary"
            hide-details
            :label="isDark ? t('settings.themeDark') : t('settings.themeLight')"
          />
        </v-card>
      </v-window-item>

      <v-window-item class="settings-narrow" value="data">
        <SourcesPanel />
      </v-window-item>

      <v-window-item class="settings-narrow" value="forms">
        <FormMemoryCard />
      </v-window-item>

      <v-window-item value="import">
        <div class="d-flex flex-column ga-4">
          <ImportPanel />

          <v-card border class="pa-4" flat>
            <div class="text-title-large font-weight-medium mb-1">{{ t('settings.exportTitle') }}</div>
            <div class="text-body-medium text-medium-emphasis mb-3">{{ t('settings.exportHint') }}</div>

            <div class="d-flex ga-2 flex-wrap">
              <ExportCsvButton variant="outlined" />

              <v-btn
                prepend-icon="mdi-shield-check-outline"
                :to="{ name: 'inventory' }"
                variant="outlined"
              >{{ t('insights.inventoryLink') }}</v-btn>
            </div>
          </v-card>
        </div>
      </v-window-item>

      <v-window-item v-if="auth.isAdmin" class="settings-narrow" value="app">
        <v-card border class="pa-4 d-flex flex-column ga-3" flat>
          <div class="text-title-large font-weight-medium">{{ t('settings.appTitle') }}</div>

          <v-switch
            color="primary"
            hide-details
            inset
            :label="t('settings.allowRegistration')"
            :loading="savingApp"
            :model-value="appSettings?.allow_registration ?? false"
            @update:model-value="value => setRegistration(Boolean(value))"
          />

          <div class="text-body-medium text-medium-emphasis">
            {{ appSettings?.allow_registration ? t('settings.registrationOpenHint') : t('settings.registrationClosedHint') }}
          </div>

          <div class="text-body-small text-medium-emphasis">{{ t('settings.registrationFirstHint') }}</div>

          <v-divider class="my-2" />
          <div class="text-title-small">{{ t('settings.operatorTitle') }}</div>
          <div class="text-body-medium text-medium-emphasis">{{ t('settings.operatorHint') }}</div>
          <v-text-field v-model="operatorName" hide-details :label="t('settings.operatorName')" />
          <v-text-field v-model="operatorEmail" hide-details :label="t('settings.operatorEmail')" type="email" />

          <v-btn class="align-self-start" color="primary" variant="tonal" @click="saveOperator">
            {{ t('settings.save') }}
          </v-btn>

          <AppVersion class="mt-2" />
        </v-card>
      </v-window-item>

      <v-window-item v-if="auth.isAdmin" class="settings-narrow" value="users">
        <PageSkeleton v-if="usersPage.initial" :count="3" kind="rows" />

        <LoadFailed v-else-if="usersPage.error" :loading="usersPage.loading" @retry="usersPage.run()" />

        <v-card v-else border flat>
          <v-list lines="two">
            <v-list-item v-for="user in users" :key="user.id" :subtitle="user.email">
              <v-list-item-title>
                {{ user.display_name || user.email }}
                <v-chip class="ms-2" label size="x-small" variant="tonal">{{ user.role }}</v-chip>
              </v-list-item-title>

              <template #append>
                <v-switch
                  color="primary"
                  density="compact"
                  hide-details
                  :label="t('settings.userActive')"
                  :model-value="user.is_active"
                  @update:model-value="value => toggleUser(user, Boolean(value))"
                />
              </template>
            </v-list-item>
          </v-list>
        </v-card>
      </v-window-item>
    </v-window>

    <ShareDialog v-model="shareDialog" :kind="shareKind" @create="nums => createLink(shareKind, nums)" />
  </div>
</template>

<style scoped>
.settings-page {
  max-width: 1280px;
}

.settings-narrow {
  max-width: 900px;
}
</style>
