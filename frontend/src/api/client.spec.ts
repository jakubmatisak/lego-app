import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

/**
 * Skutočný klient (openapi-fetch a middleware) proti falošnému serveru.
 *
 * Po zmene hesla server odmietne prístupový token vydaný pred ňou (401);
 * prehliadač, ktorý heslo zmenil, má nové cookie, obnoví si token
 * a pokračuje bez prihlasovania.
 */

/** Relatívna adresa ako v prehliadači; Request v Node ju sám nerozloží. */
class PageRequest extends Request {
  constructor (input: RequestInfo | URL, init?: RequestInit) {
    super(typeof input === 'string' && input.startsWith('/') ? `http://localhost${input}` : input, init)
  }
}

interface Seen {
  method: string
  path: string
  auth: string | null
  body: string
  status: number
}

function fakeServer () {
  const state = { valid: 'po-zmene' }
  const seen: Seen[] = []
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const request = input instanceof Request ? input : new PageRequest(input, init)
    const body = request.body ? await request.text() : ''
    const path = new URL(request.url).pathname
    const auth = request.headers.get('Authorization')
    let response: Response
    if (path === '/api/v1/auth/refresh') {
      response = Response.json({ access_token: state.valid, token_type: 'bearer', expires_in: 900 })
    } else if (auth === `Bearer ${state.valid}`) {
      if (path === '/api/v1/auth/me' && request.method === 'PATCH') {
        // Zmena hesla: odteraz platí len token vydaný po nej.
        state.valid = 'po-zmene'
      }
      response = Response.json(body ? JSON.parse(body) : { email: 'a@example.com' })
    } else {
      response = Response.json({ detail: 'Prihlásenie je potrebné' }, { status: 401 })
    }
    seen.push({ method: request.method, path, auth, body, status: response.status })
    return response
  })
  return { state, seen, fetchMock }
}

let server: ReturnType<typeof fakeServer>

beforeEach(() => {
  vi.resetModules()
  server = fakeServer()
  vi.stubGlobal('Request', PageRequest)
  vi.stubGlobal('fetch', server.fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('obnova prístupového tokenu po 401', () => {
  it('požiadavku s telom zopakuje s tým istým telom a novým tokenom', async () => {
    const { api, setAccessToken } = await import('./client')
    setAccessToken('pred-zmenou')

    const { data, response } = await api.PUT('/auth/me/preferences/{key}', {
      params: { path: { key: 'collection' } },
      body: { q: 'hrad' },
    })

    expect(response.status).toBe(200)
    expect(data).toEqual({ q: 'hrad' })
    const puts = server.seen.filter(s => s.method === 'PUT')
    expect(puts.map(s => [s.auth, s.status])).toEqual([
      ['Bearer pred-zmenou', 401],
      ['Bearer po-zmene', 200],
    ])
    expect(puts[1]!.body).toBe('{"q":"hrad"}')
  })

  it('obnovu z viacerých miest naraz pošle serveru len raz', async () => {
    const { refreshSession } = await import('./client')

    const results = await Promise.all([refreshSession(), refreshSession(), refreshSession()])

    expect(results).toEqual([true, true, true])
    expect(server.seen.filter(s => s.path === '/api/v1/auth/refresh')).toHaveLength(1)
  })
})

describe('zmena hesla v tomto prehliadači', () => {
  it('prehliadač si hneď vezme nový token a ostane prihlásený', async () => {
    const { createPinia, setActivePinia } = await import('pinia')
    const { getAccessToken, setAccessToken } = await import('./client')
    const { useAuthStore } = await import('@/stores/auth')
    setActivePinia(createPinia())
    server.state.valid = 'pred-zmenou'
    setAccessToken('pred-zmenou')
    const auth = useAuthStore()

    const ok = await auth.updateProfile({ current_password: 'tajneheslo123', new_password: 'noveheslo123' })
    await auth.loadMe()

    expect(ok).toBe(true)
    expect(getAccessToken()).toBe('po-zmene')
    expect(auth.isLoggedIn).toBe(true)
    // Ďalšia požiadavka ide rovno s novým tokenom, bez 401 a opakovania.
    expect(server.seen.filter(s => s.status === 401)).toEqual([])
  })

  it('pri zmene mena sa token neobnovuje', async () => {
    const { createPinia, setActivePinia } = await import('pinia')
    const { setAccessToken } = await import('./client')
    const { useAuthStore } = await import('@/stores/auth')
    setActivePinia(createPinia())
    setAccessToken('po-zmene')

    await useAuthStore().updateProfile({ display_name: 'Jozef' })

    expect(server.seen.filter(s => s.path === '/api/v1/auth/refresh')).toEqual([])
  })
})
