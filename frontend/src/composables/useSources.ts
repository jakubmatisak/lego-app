/**
 * Stav kariet služieb v Nastaveniach → Dáta a ukladanie pravidiel.
 *
 * Prepínač sa prepne hneď (nečaká na server) a zmeny sa ukladajú po jednej,
 * v poradí. Každá požiadavka nesie celý zoznam vypnutých aj zapnutých volaní
 * z aktuálneho stavu (UPCitemdb a Eurostat sú predvolene vypnuté, zapnutie
 * treba povedať výslovne), takže dva rýchle kliky za sebou sa nepobijú: druhý neprepíše
 * prvý starou hodnotou. Keď uloženie zlyhá, stav sa vráti na posledný
 * potvrdený serverom.
 */

import type { Source } from '@/api/types'
import { ref, toRaw } from 'vue'

export interface SourcesUpdate {
  disabled?: string[]
  /** Zapnuté volania; potrebné pri predvolene vypnutých (UPCitemdb, Eurostat). */
  enabled?: string[]
  reserve?: Record<string, number>
  price_batch?: number
  auto_purchase_price?: boolean
}

/** Uloží pravidlá; vráti nový stav zo servera, alebo null (stav ostane lokálny). */
export type SaveSources = (body: SourcesUpdate) => Promise<Source[] | null>

/**
 * Hlboká kópia stavu. `structuredClone` reaktívny objekt Vue (Proxy)
 * klonovať nevie a vyhodí výnimku, preto najprv `toRaw`.
 */
function snapshot (list: Source[]): Source[] {
  return structuredClone(toRaw(list))
}

export function createSources (send: SaveSources) {
  const sources = ref<Source[]>([])
  const error = ref<string | null>(null)
  /** Posledný stav, ktorý potvrdil server; na návrat po chybe. */
  let confirmed: Source[] = []
  let queue: Promise<void> = Promise.resolve()

  function disabledNow (): string[] {
    return sources.value
      .flatMap(s => s.capabilities)
      .filter(c => !c.enabled && !c.required)
      .map(c => c.key)
  }

  function enabledNow (): string[] {
    return sources.value
      .flatMap(s => s.capabilities)
      .filter(c => c.enabled && !c.required)
      .map(c => c.key)
  }

  function reservesNow (): Record<string, number> {
    return Object.fromEntries(
      sources.value
        .filter(s => s.reserve !== null && s.reserve !== undefined)
        .map(s => [s.provider, s.reserve as number]),
    )
  }

  function set (list: Source[]): void {
    sources.value = list
    confirmed = snapshot(list)
  }

  /** Zaradí uloženie za predchádzajúce; telo sa zostaví až pri odoslaní. */
  function save (body: () => SourcesUpdate): Promise<void> {
    queue = queue.then(async () => {
      error.value = null
      try {
        const fresh = await send(body())
        if (fresh) {
          set(fresh)
        } else {
          confirmed = snapshot(sources.value)
        }
      } catch (error_) {
        error.value = error_ instanceof Error ? error_.message : String(error_)
        sources.value = snapshot(confirmed)
      }
    })
    return queue
  }

  function toggle (cap: string, enabled: boolean): Promise<void> {
    for (const s of sources.value) {
      for (const c of s.capabilities) {
        if (c.key === cap) {
          c.enabled = enabled
        }
      }
    }
    return save(() => ({ disabled: disabledNow(), enabled: enabledNow() }))
  }

  function setReserve (provider: string, value: number): Promise<void> {
    const target = sources.value.find(s => s.provider === provider)
    if (target) {
      target.reserve = value
    }
    return save(() => ({ reserve: reservesNow() }))
  }

  function setBatch (value: number): Promise<void> {
    const target = sources.value.find(s => s.provider === 'brickeconomy')
    if (target) {
      target.price_batch = value
    }
    return save(() => ({ price_batch: value }))
  }

  /** Doplnenie kúpnej ceny z odporúčanej (karta BrickEconomy). */
  function setAutoPurchase (on: boolean): Promise<void> {
    const target = sources.value.find(s => s.provider === 'brickeconomy')
    if (target) {
      target.auto_purchase_price = on
    }
    return save(() => ({ auto_purchase_price: on }))
  }

  return { sources, error, set, toggle, setReserve, setBatch, setAutoPurchase }
}
