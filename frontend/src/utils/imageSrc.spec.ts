import { describe, expect, it } from 'vitest'
import { imageSrc } from './imageSrc'

describe('imageSrc', () => {
  it('fotku z Rebrickable a Brickset pošle cez vlastný server', () => {
    expect(imageSrc('https://cdn.rebrickable.com/media/sets/42141-1/99432.jpg'))
      .toBe('/api/v1/img?u=https%3A%2F%2Fcdn.rebrickable.com%2Fmedia%2Fsets%2F42141-1%2F99432.jpg')
    expect(imageSrc('https://images.brickset.com/sets/images/42141-1.jpg')).toContain('/api/v1/img?u=')
  })

  it('iné adresy nechá tak, prázdnu vráti ako null', () => {
    expect(imageSrc('blob:http://localhost/abc')).toBe('blob:http://localhost/abc')
    expect(imageSrc(imageSrc('https://images.brickset.com/a.jpg'))).toBe(imageSrc('https://images.brickset.com/a.jpg'))
    expect(imageSrc(null)).toBeNull()
  })
})
