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

export const api = createClient<paths>({
  baseUrl: API_BASE,
  credentials: 'include',
})

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
