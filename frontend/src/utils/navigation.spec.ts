import { describe, expect, it } from 'vitest'
import { safeRedirect } from './navigation'

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
