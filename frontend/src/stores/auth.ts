import type { ApiKeys, ApiKeysUpdate, ProviderStatus, User } from '@/api/types'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api, errorMessage, onSessionExpired, refreshSession, setAccessToken } from '@/api/client'
import { reloadTo } from '@/utils/navigation'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const providers = ref<ProviderStatus | null>(null)
  /** Stav vlastných kľúčov používateľa. Samotné kľúče sem nikdy neprídu. */
  const keys = ref<ApiKeys | null>(null)
  const ready = ref(false)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const isLoggedIn = computed(() => user.value !== null)
  const hasPriceKey = computed(() => keys.value?.brickeconomy.is_set === true)
  const hasBricksetKey = computed(() => keys.value?.brickset.is_set === true)
  const hasCatalogKey = computed(() => keys.value?.rebrickable.is_set === true)
  const isAdmin = computed(() => user.value?.role === 'admin')
  /**
   * Smie účet túto schopnosť (`brickeconomy.prices`, `brickset.themes`…)?
   * Server ju vráti, keď služba má kľúč (alebo ho netreba) a je zapnutá
   * v Nastaveniach → Dáta. Podľa toho rozhranie skrýva, čo nejde.
   */
  function can (cap: string): boolean {
    return keys.value?.capabilities?.includes(cap) ?? false
  }
  const initials = computed(() => {
    const source = user.value?.display_name || user.value?.email || ''
    const parts = source.split(/[\s@.]+/).filter(Boolean)
    return parts.slice(0, 2).map(p => p[0]?.toUpperCase() ?? '').join('') || '?'
  })

  onSessionExpired(() => {
    user.value = null
    keys.value = null
  })

  async function loadKeys (): Promise<void> {
    const { data } = await api.GET('/auth/me/keys', {})
    keys.value = data ?? null
  }

  async function saveKeys (payload: ApiKeysUpdate): Promise<boolean> {
    const { data, error: err } = await api.PUT('/auth/me/keys', { body: payload })
    if (err || !data) {
      error.value = errorMessage(err, 'Uloženie kľúčov zlyhalo')
      return false
    }
    keys.value = data
    return true
  }

  async function loadMe (): Promise<void> {
    const { data } = await api.GET('/auth/me', {})
    user.value = data ?? null
  }

  async function loadProviders (): Promise<void> {
    const { data } = await api.GET('/providers/status', {})
    providers.value = data ?? null
  }

  /** Po načítaní stránky skúsi obnoviť reláciu z cookie. */
  async function restore (): Promise<void> {
    if (ready.value) {
      return
    }
    try {
      // Tá istá obnova ako pri 401 v klientovi, nech nejdú dve so starým cookie.
      if (await refreshSession()) {
        await loadMe()
        await loadKeys()
      }
    } catch {
      // Bez platnej cookie zostaneme odhlásení, to nie je chyba.
    } finally {
      await loadProviders()
      ready.value = true
    }
  }

  /**
   * `remember`: zapamätať si prihlásenie na tomto počítači. Server potom
   * pošle cookie na 30 dní, inak zanikne so zatvorením prehliadača.
   */
  async function login (email: string, password: string, remember = false): Promise<boolean> {
    loading.value = true
    error.value = null
    try {
      const { data, error: err } = await api.POST('/auth/login', {
        body: { email, password, remember },
      })
      if (err || !data) {
        error.value = errorMessage(err, 'Prihlásenie zlyhalo')
        return false
      }
      setAccessToken(data.access_token)
      await loadMe()
      await loadKeys()
      return true
    } finally {
      loading.value = false
    }
  }

  async function register (
    email: string,
    password: string,
    displayName?: string,
    remember = false,
  ): Promise<boolean> {
    // Formulár pustí registráciu len so zaškrtnutým potvrdením zásad.
    loading.value = true
    error.value = null
    try {
      const { data, error: err } = await api.POST('/auth/register', {
        body: { email, password, display_name: displayName || null, accept_privacy: true, remember },
      })
      if (err || !data) {
        error.value = errorMessage(err, 'Registrácia zlyhala')
        return false
      }
      setAccessToken(data.access_token)
      await loadMe()
      await loadKeys()
      return true
    } finally {
      loading.value = false
    }
  }

  async function logout (): Promise<void> {
    await api.POST('/auth/logout', {})
    setAccessToken(null)
    user.value = null
    // Zbierka, filtre aj Prehľad účtu nesmú ostať v pamäti stránky.
    reloadTo('/prihlasenie')
  }

  /**
   * Prihlásenie alebo registrácia a vstup do appky cez nové načítanie
   * stránky: ak v pamäti ostali dáta iného účtu (vypršaná relácia bez
   * odhlásenia), nezobrazia sa ani na chvíľu.
   */
  async function signIn (
    mode: 'login' | 'register',
    email: string,
    password: string,
    displayName: string | undefined,
    target: string,
    remember = false,
  ): Promise<boolean> {
    const ok = mode === 'register'
      ? await register(email, password, displayName, remember)
      : await login(email, password, remember)
    if (ok) {
      reloadTo(target)
    }
    return ok
  }

  async function updateProfile (payload: {
    display_name?: string | null
    locale?: string | null
    current_password?: string | null
    new_password?: string | null
  }): Promise<boolean> {
    error.value = null
    const { data, error: err } = await api.PATCH('/auth/me', { body: payload })
    if (err || !data) {
      error.value = errorMessage(err, 'Uloženie zlyhalo')
      return false
    }
    user.value = data
    if (payload.new_password) {
      // Server odteraz odmieta prístupové tokeny spred zmeny hesla (ostatné
      // zariadenia sú odhlásené). Tento prehliadač dostal nové cookie a hneď
      // si vezme nový token, aby ďalšia požiadavka nešla zbytočne cez 401.
      await refreshSession()
    }
    return true
  }

  return {
    signIn,
    loadMe,
    can,
    user,
    providers,
    keys,
    hasPriceKey,
    hasBricksetKey,
    hasCatalogKey,
    loadKeys,
    saveKeys,
    ready,
    loading,
    error,
    isLoggedIn,
    isAdmin,
    initials,
    restore,
    login,
    register,
    logout,
    updateProfile,
    loadProviders,
  }
})
