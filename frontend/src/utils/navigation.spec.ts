import { describe, expect, it } from 'vitest'
import { safeRedirect, sectionRoute } from './navigation'

describe('safeRedirect', () => {
  it('pustí len cestu v rámci appky', () => {
    expect(safeRedirect('/zbierka?sort=name')).toBe('/zbierka?sort=name')
    expect(safeRedirect('/')).toBe('/')
  })

  it('cudziu adresu po prihlásení nahradí úvodnou stránkou', () => {
    expect(safeRedirect('//evil.example')).toBe('/')
    expect(safeRedirect(String.raw`/\evil.example`)).toBe('/')
    expect(safeRedirect('https://evil.example/')).toBe('/')
    expect(safeRedirect('javascript:alert(1)')).toBe('/')
    expect(safeRedirect(undefined)).toBe('/')
  })
})

describe('sekcia ponuky pre trasu', () => {
  it('detail figúrky otvorený z Figúrok svieti na Figúrkach, nie na Zbierke', () => {
    expect(sectionRoute('set-detail', { from: 'minifigs' })).toBe('minifig-series')
  })

  it('detail setu inak patrí Zbierke, ostatné trasy sa nemenia', () => {
    expect(sectionRoute('set-detail', {})).toBe('set-detail')
    expect(sectionRoute('collection', { from: 'minifigs' })).toBe('collection')
    expect(sectionRoute(undefined, {})).toBe('')
  })
})
