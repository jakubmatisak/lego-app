import { describe, expect, it } from 'vitest'
import { arrangeThemes } from './themeList'

function theme (name: string, owned: number, sets: number, followed = false) {
  return ({ theme: name, owned, set_count: sets, followed, year_from: null, year_to: null }) as never
}

const ROWS = [
  theme('Technic', 12, 400),
  theme('Icons', 5, 10),
  theme('Ideas', 0, 90, true),
  theme('Speed Champions', 20, 20),
]
const names = (rows: Array<{ theme: string }>) => rows.map(r => r.theme)

describe('témy: zoradenie a filtre', () => {
  it('podľa počtu mojich setov, potom názvu', () => {
    expect(names(arrangeThemes(ROWS, 'mine', {}))).toEqual(['Speed Champions', 'Technic', 'Icons', 'Ideas'])
  })

  it('podľa úplnosti; téma bez známeho počtu na koniec', () => {
    const rows = [...ROWS, theme('Neznáma', 3, 0)]
    expect(names(arrangeThemes(rows, 'completeness', {}))).toEqual([
      'Speed Champions', 'Icons', 'Technic', 'Ideas', 'Neznáma',
    ])
  })

  it('podľa názvu', () => {
    expect(names(arrangeThemes(ROWS, 'name', {}))).toEqual(['Icons', 'Ideas', 'Speed Champions', 'Technic'])
  })

  it('filtre sa skladajú', () => {
    expect(names(arrangeThemes(ROWS, 'name', { followed: true }))).toEqual(['Ideas'])
    expect(names(arrangeThemes(ROWS, 'name', { withSets: true }))).toEqual(['Icons', 'Speed Champions', 'Technic'])
    expect(names(arrangeThemes(ROWS, 'name', { withSets: true, incomplete: true }))).toEqual(['Icons', 'Technic'])
  })
})
