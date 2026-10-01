import { describe, expect, it } from 'vitest'
import { defaultDir } from '@/stores/collection'
import { COLUMNS, rowFromGroup, rowFromItem, sortFromHeader } from './tableColumns'

const column = (key: string) => COLUMNS.find(c => c.key === key)!

describe('zoradenie hlavičkou tabuľky', () => {
  it('klik na iný stĺpec nastaví jeho kľúč s predvoleným smerom', () => {
    expect(sortFromHeader(column('value'), { sort: 'name', dir: null })).toEqual({ sort: 'value', dir: null })
  })

  it('druhý klik na ten istý stĺpec otočí smer, tretí ho vráti', () => {
    const once = sortFromHeader(column('value'), { sort: 'value', dir: null })
    expect(once).toEqual({ sort: 'value', dir: 'asc' })
    // Späť na predvolený smer sa ukladá ako null, nech adresa ostane čistá.
    expect(sortFromHeader(column('value'), once!)).toEqual({ sort: 'value', dir: null })
  })

  it('fotka sa zoradiť nedá, nič nerobí', () => {
    expect(sortFromHeader(column('image'), { sort: 'name', dir: null })).toBeNull()
  })

  it('každý stĺpec okrem fotky radí kľúčom z registra servera', () => {
    expect(COLUMNS.filter(c => !c.sort).map(c => c.key)).toEqual(['image'])
    expect(COLUMNS.map(c => c.sort).filter(Boolean)).toEqual([
      'number', 'name', 'theme', 'year', 'quantity', 'condition', 'location',
      'purchase', 'value', 'price_at', 'profit', 'profit_pct', 'cagr',
    ])
  })

  it('číslo, téma, stav a miesto začínajú od A, počet a dátum ceny od najväčšieho', () => {
    for (const key of ['number', 'theme', 'condition', 'location'] as const) {
      expect(defaultDir(key)).toBe('asc')
    }
    expect(defaultDir('quantity')).toBe('desc')
    expect(defaultDir('price_at')).toBe('desc')
    expect(sortFromHeader(column('number'), { sort: 'number', dir: null })).toEqual({ sort: 'number', dir: 'desc' })
  })
})

describe('riadky tabuľky', () => {
  const group = (over: Record<string, unknown> = {}) => ({
    catalog: { catalog_num: '10294-1', name: 'Titanic', theme: 'Icons', year: 2021, image_url: null },
    quantity: 2,
    sold_quantity: 0,
    locations: ['Povala'],
    conditions: { new_sealed: 2 },
    purchase_total: '1200.00',
    market_total: '1500.00',
    sold_total: '0.00',
    unrealized: '300.00',
    unrealized_pct: 25,
    realized: '0.00',
    price_missing: 0,
    price_approx: 0,
    cagr_pct: 8.2,
    ...over,
  }) as never

  it('bez trhovej ceny je hodnota aj zisk pomlčka, nie nula', () => {
    const row = rowFromGroup(group({ price_missing: 2, market_total: '0.00', unrealized: '-1200.00', unrealized_pct: null }), false)
    expect([row.value, row.profit, row.profitPct]).toEqual(['—', '—', '—'])
  })

  it('odvodená cena má znak ≈', () => {
    expect(rowFromGroup(group({ price_approx: 1 }), false).value.startsWith('≈ ')).toBe(true)
  })

  it('predaný pohľad ukazuje predajnú sumu a realizovaný zisk', () => {
    const row = rowFromGroup(group({ sold_quantity: 1, sold_total: '800.00', realized: '200.00' }), true)
    expect(row.quantity).toBe(1)
    expect(row.value).toContain('800')
    expect(row.profit).toContain('+200')
  })

  it('kus bez ceny: percento sa nepočíta z nuly', () => {
    const row = rowFromItem({
      id: 5, catalog_num: '10294-1', status: 'owned', condition: 'built', location: null,
      catalog: { catalog_num: '10294-1', name: 'Titanic', theme: null, year: 2021, image_url: null },
      purchase_price_eur: '600.00', market_value: '0.00', price_source: 'missing',
      unrealized: '-600.00', realized: '0.00', sold_price_eur: null, cagr_pct: null,
    } as never)
    expect([row.value, row.profitPct, row.selectKey]).toEqual(['—', '—', 5])
  })
})
