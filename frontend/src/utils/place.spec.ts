import { describe, expect, it } from 'vitest'
import { boxesFor, placeLabel } from './place'

describe('umiestnenie s krabicou', () => {
  it('popis ako na serveri', () => {
    expect(placeLabel('Povala', '3')).toBe('Povala · krabica 3')
    expect(placeLabel('Povala', null)).toBe('Povala')
    expect(placeLabel(null, '3')).toBe('krabica 3')
    expect(placeLabel('Povala', 'Krabica 3')).toBe('Povala · Krabica 3')
    expect(placeLabel('', ' ')).toBeNull()
  })

  it('našepkávač ponúkne krabice z vybranej miestnosti, bez nej všetky', () => {
    const boxes = [
      { location: 'Pivnica', box: '1' },
      { location: 'Povala', box: '1' },
      { location: 'Povala', box: '3' },
    ]
    expect(boxesFor(boxes, 'povala ')).toEqual(['1', '3'])
    expect(boxesFor(boxes, '')).toEqual(['1', '3'])
    expect(boxesFor(boxes, 'Chata')).toEqual([])
  })
})
