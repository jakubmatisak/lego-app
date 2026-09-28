import { describe, expect, it } from 'vitest'
import { fold } from './text'

describe('text na hľadanie', () => {
  it('bez diakritiky a veľkých písmen, ako na serveri', () => {
    expect(fold('Hradná Ľadová Šikmá')).toBe('hradna ladova sikma')
    expect(fold(null)).toBe('')
  })
})
