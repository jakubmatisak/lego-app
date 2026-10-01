/**
 * HTTP klient nad vygenerovanými typmi z OpenAPI.
 *
 * Prístupový token žije len v pamäti, nie v localStorage. Obnovovací token
 * je v httpOnly cookie, ku ktorej sa JavaScript nedostane. Pri 401 sa raz
 * skúsi obnova a pôvodná požiadavka sa zopakuje.
 */

import type { paths } from './schema'

import createClient, { type Middleware } from 'openapi-fetch'

export const API_BASE = '/api/v1'

let accessToken: string | null = null
let refreshing: Promise<boolean> | null = null
let onSessionLost: (() => void) | null = null

export function setAccessToken (token: string | null): void {
  accessToken = token
}

export function getAccessToken (): string | null {
  return accessToken
}

export function onSessionExpired (handler: () => void): void {
  onSessionLost = handler
}

/**
 * Nový prístupový token z obnovovacieho cookie. Obnovu spúšťame naraz len
 * raz, aj keď zlyhá viac požiadaviek súčasne alebo sa stránka práve načíta:
 * každá obnova vymení cookie a súbežná so starým by dostala len prístup.
 */
export async function refreshSession (): Promise<boolean> {
  if (!refreshing) {
    refreshing = (async () => {
      try {
        const response = await fetch(`${API_BASE}/auth/refresh`, {
          method: 'POST',
          credentials: 'include',
        })
        if (!response.ok) {
          return false
        }
        const data = await response.json() as { access_token: string }
        accessToken = data.access_token
        return true
      } catch {
        return false
      } finally {
        // Uvoľníme až po vyhodnotení, aby súbežné volania počkali na výsledok.
        setTimeout(() => {
          refreshing = null
        }, 0)
      }
    })()
  }
  return refreshing
}

const NO_RETRY = ['/auth/login', '/auth/register', '/auth/refresh']

/**
 * Kópie odosielaných požiadaviek s telom podľa `id` z openapi-fetch.
 * Odoslaním sa telo minie a po 401 by sa už nedalo zopakovať (TypeError),
 * napríklad uloženie hneď po zmene hesla. Kópia sa preto robí vopred.
 */
const retryCopies = new Map<string, Request>()

const authMiddleware: Middleware = {
  async onRequest ({ request, id }) {
    if (accessToken) {
      request.headers.set('Authorization', `Bearer ${accessToken}`)
    }
    if (request.body !== null) {
      retryCopies.set(id, request.clone())
    }
    return request
  },
  async onResponse ({ request, response, id }) {
    const copy = retryCopies.get(id)
    retryCopies.delete(id)
    if (response.status !== 401) {
      return response
    }
    if (NO_RETRY.some(path => request.url.includes(path))) {
      return response
    }

    const ok = await refreshSession()
    if (!ok) {
      accessToken = null
      onSessionLost?.()
      return response
    }

    const retried = copy ?? request.clone()
    retried.headers.set('Authorization', `Bearer ${accessToken}`)
    return fetch(retried)
  },
  onError ({ id }) {
    retryCopies.delete(id)
  },
}

/**
 * Zmeny, po ktorých neplatia čísla v ponuke (súhrn zbierky): kusy, Chcem
 * a potvrdený či vrátený import. Fotka kusu ani náhľad importu nie.
 */
const COLLECTION_CHANGES = [
  // Fotky a kontrola úplnosti počty v ponuke nemenia.
  /^\/items(\/|$)(?!.*\/(photos|part-checks)$)/,
  /^\/wishlist(\/|$)/,
  /^\/imports\/\{import_id\}\/(commit|undo)$/,
]

const collectionListeners = new Set<() => void>()

/**
 * Odber úspešných zmien zbierky alebo Chcem, nech už ich spravila ktorákoľvek
 * obrazovka. Jediné miesto, odkiaľ sa obnovuje súhrn za počtami v ponuke,
 * takže nová obrazovka na to nemôže zabudnúť. Vráti odhlásenie.
 */
export function onCollectionChanged (listener: () => void): () => void {
  collectionListeners.add(listener)
  return () => collectionListeners.delete(listener)
}

export function changesCollection (method: string, schemaPath: string): boolean {
  return method !== 'GET' && COLLECTION_CHANGES.some(pattern => pattern.test(schemaPath))
}

const changesMiddleware: Middleware = {
  onResponse ({ request, response, schemaPath }) {
    if (response.ok && changesCollection(request.method, schemaPath)) {
      for (const listener of collectionListeners) {
        listener()
      }
    }
    return response
  },
}

export const api = createClient<paths>({
  baseUrl: API_BASE,
  credentials: 'include',
})

// Odpovede prechádzajú middleware od posledného: zmeny vidia až výsledok po
// prípadnom zopakovaní požiadavky s novým tokenom.
api.use(changesMiddleware)
api.use(authMiddleware)

/** Vytiahne zrozumiteľnú hlášku z odpovede FastAPI. */
export function errorMessage (error: unknown, fallback = 'Niečo sa pokazilo'): string {
  if (!error) {
    return fallback
  }
  const detail = (error as { detail?: unknown }).detail
  if (typeof detail === 'string') {
    return detail
  }
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: string }
    if (first?.msg) {
      return first.msg
    }
  }
  return fallback
}

export type Schemas = paths
