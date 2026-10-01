/**
 * Načítavanie stránky nie je prázdny stav.
 *
 * Stránka má tri stavy: prvé načítanie (kostra v tvare toho, čo príde),
 * odpoveď servera (dáta alebo skutočne prázdny stav) a chybu („Nepodarilo
 * sa načítať“ so Skúsiť znova). Kým server neodpovedal, prázdny stav sa
 * neukazuje: „Zatiaľ žiadne sety“ by vyzeralo, že zbierka zmizla.
 *
 * Opakované načítanie (zmena filtra, tlačidlo Obnoviť stránku) nechá staré
 * dáta na obrazovke a len rozsvieti tenký pruh pod hornou lištou
 * (`pageBusy`), späť na kostru sa nevracia.
 *
 * Tlačidlo Obnoviť stránku v hornej lište (`reloadPage`) zavolá všetky
 * načítania, ktoré sa prihlásili cez `onPageReload` (každý `usePageLoad`
 * sa prihlási sám). Patria sem len GET na vlastný server, nie úlohy, ktoré
 * siahajú na cudzie služby (ceny, Brickset).
 */
import { computed, getCurrentScope, onScopeDispose, reactive, ref } from 'vue'
import i18n from '@/plugins/i18n'
import { useNotifyStore } from '@/stores/notify'

type Loader = () => Promise<unknown>

interface Entry {
  load: Loader
  /** Načítanie obnoví aj súhrn za ponukou, rozloženie ho potom neťahá druhý raz. */
  summary: boolean
}

const entries = new Set<Entry>()

/** Koľko opakovaných načítaní práve beží (pruh pod hornou lištou). */
const busy = ref(0)
export const pageBusy = computed(() => busy.value > 0)

/**
 * Prihlási načítanie stránky (alebo karty na nej) k tlačidlu Obnoviť
 * stránku. V komponente sa pri jeho zániku samo odhlási.
 */
export function onPageReload (load: Loader, options: { summary?: boolean } = {}): () => void {
  const entry: Entry = { load, summary: options.summary === true }
  entries.add(entry)
  const off = (): void => {
    entries.delete(entry)
  }
  if (getCurrentScope()) {
    onScopeDispose(off)
  }
  return off
}

/**
 * Znova načíta otvorenú stránku. `summary` je súhrn za počtami v ponuke;
 * zavolá sa, len keď ho žiadne prihlásené načítanie neobnovuje samo.
 */
export async function reloadPage (summary?: Loader): Promise<void> {
  const list = [...entries]
  const runs = list.map(entry => entry.load())
  if (summary && !list.some(entry => entry.summary)) {
    runs.push(summary())
  }
  await Promise.allSettled(runs)
}

export interface PageLoad {
  /** Server aspoň raz odpovedal; dáta (aj prázdne) sú platné. */
  readonly loaded: boolean
  readonly loading: boolean
  /** Posledné načítanie zlyhalo. */
  readonly failed: boolean
  /** Ešte nič neprišlo a načítava sa (aj pred prvým spustením): kostra. */
  readonly initial: boolean
  /** Prvé načítanie zlyhalo: „Nepodarilo sa načítať“, nie prázdny stav. */
  readonly error: boolean
  /** Opakované načítanie nad starými dátami. */
  readonly reloading: boolean
  /** Spustí načítanie; `false` = zlyhalo. */
  run: () => Promise<boolean>
  /** Iný obsah (iný set, iná séria): znova kostra, staré dáta neplatia. */
  reset: () => void
}

export interface PageLoadOptions {
  /** Prihlásiť k tlačidlu Obnoviť stránku (predvolene áno). */
  reload?: boolean
  /** Načítanie obnovuje aj súhrn za ponukou (Prehľad). */
  summary?: boolean
  /**
   * Chybu opakovaného načítania ohlási oznámením. Vypnúť, keď ju načítanie
   * hlási samo (`collection.loadItems`), inak by boli dve.
   */
  notify?: boolean
}

/**
 * Stav načítania stránky. `load` vráti `false` alebo vyhodí výnimku, keď
 * sa nepodarilo; čokoľvek iné je úspech. Staršia odpoveď novšiu neprepíše.
 */
export function usePageLoad (load: () => Promise<unknown>, options: PageLoadOptions = {}): PageLoad {
  const loaded = ref(false)
  const loading = ref(false)
  const failed = ref(false)
  let current = 0

  async function run (): Promise<boolean> {
    const mine = ++current
    const again = loaded.value
    loading.value = true
    if (again) {
      busy.value++
    }
    let ok: boolean
    try {
      ok = (await load()) !== false
    } catch {
      ok = false
    } finally {
      if (again) {
        busy.value--
      }
    }
    // Medzitým sa spustilo novšie načítanie (alebo reset): stav patrí jemu.
    if (mine !== current) {
      return ok
    }
    loading.value = false
    failed.value = !ok
    if (ok) {
      loaded.value = true
    } else if (again && options.notify !== false) {
      // Staré dáta ostávajú na obrazovke; chyba nesmie ostať ticho.
      useNotifyStore().error(i18n.global.t('common.loadFailed'))
    }
    return ok
  }

  function reset (): void {
    current++
    loaded.value = false
    failed.value = false
    loading.value = false
  }

  if (options.reload !== false) {
    onPageReload(run, { summary: options.summary })
  }

  return reactive({
    loaded,
    loading,
    failed,
    initial: computed(() => !loaded.value && (loading.value || !failed.value)),
    error: computed(() => !loaded.value && failed.value && !loading.value),
    reloading: computed(() => loaded.value && loading.value),
    run,
    reset,
  })
}
