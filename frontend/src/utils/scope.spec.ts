import { describe, expect, it } from 'vitest'
import { scopeFromCategory, scopeFromPurpose, scopeFromTheme, scopeFromView } from './scope'

describe('rozsah Prehľadu', () => {
  it('uložený pohľad je presne uložený filter Zbierky, bez zoskupenia a chýbajúcich', () => {
    const scope = scopeFromView({ id: 3, name: 'Investícia', query: { purpose: ['investment'], group: 'series', missing: '1', theme: ['Icons'] } } as never)
    expect(scope).toEqual({ kind: 'view', id: '3', label: 'Investícia', query: { purpose: ['investment'], theme: ['Icons'] } })
  })

  it('kategória, zoznam a téma sú jeden filter', () => {
    expect(scopeFromCategory({ id: 7, name: 'Formula 1' } as never).query).toEqual({ category: [7] })
    expect(scopeFromPurpose('for_sale', 'Na predaj').query).toEqual({ purpose: ['for_sale'] })
    expect(scopeFromTheme('Star Wars').query).toEqual({ theme: ['Star Wars'] })
  })
})

describe('uložený rozsah', () => {
  it('pokazený alebo starý tvar znamená celú zbierku', async () => {
    const { restoreScope } = await import('./scope')
    expect(restoreScope(null)).toBeNull()
    expect(restoreScope({ kind: 'nieco', label: 'x', query: {} })).toBeNull()
    expect(restoreScope({ kind: 'theme', label: 'Icons' })).toBeNull()
    expect(restoreScope({ kind: 'theme', id: 'Icons', label: 'Icons', query: { theme: ['Icons'] } }))
      .toEqual({ kind: 'theme', id: 'Icons', label: 'Icons', query: { theme: ['Icons'] } })
  })
})

describe('rozsah proti aktuálnym pohľadom a kategóriám', () => {
  it('premenovaný pohľad a zmenený filter sa prevezmú, zmazaný rozsah zruší', async () => {
    const { refreshScope, scopeFromView } = await import('./scope')
    const old = scopeFromView({ id: 3, name: 'Investícia', query: { purpose: ['investment'] } } as never)
    const views = [{ id: 3, name: 'Na neskôr', query: { purpose: ['for_sale'] } }] as never
    expect(refreshScope(old, views, [])).toEqual({ kind: 'view', id: '3', label: 'Na neskôr', query: { purpose: ['for_sale'] } })
    expect(refreshScope(old, [] as never, [])).toBeNull()
  })

  it('séria bez mena má kľúč __none__ a vlastný popis', async () => {
    const { scopeFromTheme } = await import('./scope')
    expect(scopeFromTheme('__none__', 'Bez série')).toEqual({ kind: 'theme', id: '__none__', label: 'Bez série', query: { theme: ['__none__'] } })
  })
})
