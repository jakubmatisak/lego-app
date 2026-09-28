import type * as Client from '@/api/client'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useAuthStore } from './auth'

const reloadTo = vi.fn()
vi.mock('@/utils/navigation', () => ({ reloadTo: (path: string) => reloadTo(path) }))
vi.mock('@/api/client', async original => ({
  ...(await original<typeof Client>()),
  api: {
    POST: vi.fn(async (url: string) => (url === '/auth/logout' ? {} : { data: { access_token: 't' } })),
    GET: vi.fn(async () => ({ data: null })),
  },
}))

describe('zmena účtu v tom istom prehliadači', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    reloadTo.mockReset()
  })

  it('odhlásenie načíta stránku nanovo, v pamäti neostane zbierka predošlého účtu', async () => {
    await useAuthStore().logout()
    expect(reloadTo).toHaveBeenCalledWith('/prihlasenie')
  })

  it('prihlásenie aj registrácia vedú do appky cez nové načítanie stránky', async () => {
    const auth = useAuthStore()
    await auth.signIn('login', 'a@b.sk', 'heslo', undefined, '/zbierka')
    expect(reloadTo).toHaveBeenCalledWith('/zbierka')
    await auth.signIn('register', 'c@d.sk', 'heslo1234', 'C', '/')
    expect(reloadTo).toHaveBeenLastCalledWith('/')
  })
})
