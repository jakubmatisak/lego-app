import { describe, expect, it } from 'vitest'
import {
  compareSeries,
  matchesState,
  memberDefaultDir,
  memberShowFrom,
  seriesHeaderDir,
  seriesSortFromHeader,
  seriesState,
  sortMembers,
} from './seriesList'

function row (name: string, owned: number, total: number, year = 2024) {
  return ({ name, owned, total, year, series_num: name }) as never
}
const collator = new Intl.Collator('sk', { numeric: true })

describe('figúrky: stav a zoradenie sérií', () => {
  it('skoro kompletná: niečo mám a chýbajú najviac dve', () => {
    expect(matchesState(row('A', 10, 12), 'almost')).toBe(true)
    expect(matchesState(row('B', 9, 12), 'almost')).toBe(false)
    expect(matchesState(row('C', 12, 12), 'almost')).toBe(false)
    expect(matchesState(row('D', 0, 2), 'almost')).toBe(false)
    // Skoro kompletná je aj „zbieram“, čipy sa neprekrývajú zle.
    expect(seriesState(row('A', 10, 12))).toBe('collecting')
    expect(matchesState(row('A', 10, 12), 'collecting')).toBe(true)
  })

  it('najmenej chýba: rozbehnuté podľa chýbajúcich, potom kompletné, nezačaté na konci', () => {
    const rows = [row('Nová', 0, 12), row('Hotová', 12, 12), row('Skoro', 11, 12), row('Polovica', 6, 12)]
    const sorted = rows.toSorted((a, b) => compareSeries(a, b, 'leastMissing', collator))
    expect(sorted.map((r: { name: string }) => r.name)).toEqual(['Skoro', 'Polovica', 'Hotová', 'Nová'])
  })

  it('séria 2 pred sériou 10 aj pri zoradení podľa názvu', () => {
    const rows = [row('Series 10', 1, 12), row('Series 2', 1, 12)]
    const sorted = rows.toSorted((a, b) => compareSeries(a, b, 'nameAsc', collator))
    expect(sorted.map((r: { name: string }) => r.name)).toEqual(['Series 2', 'Series 10'])
  })

  it('odkaz „Ukázať chýbajúce“ otvorí sériu rovno na chýbajúcich', () => {
    expect(memberShowFrom('missing')).toBe('missing')
    expect(memberShowFrom('owned')).toBe('owned')
    expect(memberShowFrom('nesmysel')).toBe('all')
    expect(memberShowFrom(undefined)).toBe('all')
  })
})

describe('figúrky: zoradenie tabuľky sérií klikom na hlavičku', () => {
  const sortBy = (rows: never[], sort: Parameters<typeof compareSeries>[2]) =>
    rows.toSorted((a, b) => compareSeries(a, b, sort, collator)).map((r: { name: string }) => r.name)

  it('prvý klik dá predvolený smer stĺpca, druhý ho otočí', () => {
    expect(seriesSortFromHeader('name', 'leastMissing')).toBe('nameAsc')
    expect(seriesSortFromHeader('name', 'nameAsc')).toBe('nameDesc')
    expect(seriesSortFromHeader('name', 'nameDesc')).toBe('nameAsc')
    expect(seriesSortFromHeader('year', 'nameAsc')).toBe('yearDesc')
    expect(seriesSortFromHeader('year', 'yearDesc')).toBe('yearAsc')
    expect(seriesSortFromHeader('owned', 'yearAsc')).toBe('ownedDesc')
    expect(seriesSortFromHeader('missing', 'ownedDesc')).toBe('missingAsc')
    expect(seriesSortFromHeader('progress', 'missingAsc')).toBe('progressDesc')
    expect(seriesSortFromHeader('progress', 'progressDesc')).toBe('progressAsc')
  })

  it('šípka svieti pri stĺpci, podľa ktorého sa radí; najmenej chýba nemá stĺpec', () => {
    expect(seriesHeaderDir('year', 'yearAsc')).toBe('asc')
    expect(seriesHeaderDir('progress', 'progressDesc')).toBe('desc')
    expect(seriesHeaderDir('name', 'yearAsc')).toBeNull()
    expect(seriesHeaderDir('missing', 'leastMissing')).toBeNull()
  })

  it('mám, chýba a kompletnosť; nestiahnutá séria je na konci v oboch smeroch', () => {
    const rows = [row('Pol', 6, 12), row('Nestiahnutá', 0, 0), row('Skoro', 11, 12), row('Malá', 2, 2)] as never[]
    expect(sortBy(rows, 'ownedDesc')).toEqual(['Skoro', 'Pol', 'Malá', 'Nestiahnutá'])
    expect(sortBy(rows, 'ownedAsc')).toEqual(['Malá', 'Pol', 'Skoro', 'Nestiahnutá'])
    expect(sortBy(rows, 'missingAsc')).toEqual(['Malá', 'Skoro', 'Pol', 'Nestiahnutá'])
    expect(sortBy(rows, 'missingDesc')).toEqual(['Pol', 'Skoro', 'Malá', 'Nestiahnutá'])
    expect(sortBy(rows, 'progressDesc')).toEqual(['Malá', 'Skoro', 'Pol', 'Nestiahnutá'])
    expect(sortBy(rows, 'progressAsc')).toEqual(['Pol', 'Skoro', 'Malá', 'Nestiahnutá'])
  })

  it('séria bez roka je na konci v oboch smeroch', () => {
    const rows = [row('Bez roka', 1, 12, null as never), row('Stará', 1, 12, 2010), row('Nová', 1, 12, 2024)] as never[]
    expect(sortBy(rows, 'yearDesc')).toEqual(['Nová', 'Stará', 'Bez roka'])
    expect(sortBy(rows, 'yearAsc')).toEqual(['Stará', 'Nová', 'Bez roka'])
  })
})

describe('figúrky jednej série: zoradenie tabuľky', () => {
  const m = (num: string, name: string, owned: number, wanted = false) =>
    ({ catalog: { catalog_num: num, name }, owned, wanted }) as never
  const members = [m('71046-10', 'Zombie', 0, true), m('71046-2', 'Alien', 1), m('71046-1', 'Astronaut', 2), m('71046-3', 'Čarodej', 0)]
  const nums = (rows: Array<{ catalog: { catalog_num: string } }>) => rows.map(r => r.catalog.catalog_num)

  it('číslo prirodzene: -2 pred -10', () => {
    expect(nums(sortMembers(members, 'number', 'asc'))).toEqual(['71046-1', '71046-2', '71046-3', '71046-10'])
    expect(nums(sortMembers(members, 'number', 'desc'))).toEqual(['71046-10', '71046-3', '71046-2', '71046-1'])
  })

  it('názov podľa abecedy s diakritikou', () => {
    expect(nums(sortMembers(members, 'name', 'asc'))).toEqual(['71046-2', '71046-1', '71046-3', '71046-10'])
  })

  it('stav: predvolene vlastnené navrchu, otočené chýbajúce; pri zhode číslo', () => {
    expect(memberDefaultDir('state')).toBe('desc')
    expect(nums(sortMembers(members, 'state', 'desc'))).toEqual(['71046-1', '71046-2', '71046-3', '71046-10'])
    expect(nums(sortMembers(members, 'state', 'asc'))).toEqual(['71046-3', '71046-10', '71046-2', '71046-1'])
  })

  it('Chcem: predvolene želané navrchu', () => {
    expect(memberDefaultDir('wanted')).toBe('desc')
    expect(nums(sortMembers(members, 'wanted', 'desc'))[0]).toBe('71046-10')
    expect(nums(sortMembers(members, 'wanted', 'asc')).at(-1)).toBe('71046-10')
  })

  it('vstup nemení', () => {
    sortMembers(members, 'name', 'desc')
    expect(nums(members as never)).toEqual(['71046-10', '71046-2', '71046-1', '71046-3'])
  })
})
