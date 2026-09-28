import { describe, expect, it } from 'vitest'

import { count, exactMoney, money, percent, shortDate, toNumber, trendColor } from './format'

const NBSP = ' '

describe('toNumber', () => {
  it('prevedie reťazec aj číslo', () => {
    expect(toNumber('590')).toBe(590)
    expect(toNumber(590)).toBe(590)
    expect(toNumber('1180.50')).toBe(1180.5)
  })

  it('vráti null pre prázdnu alebo nezmyselnú hodnotu', () => {
    expect(toNumber('')).toBeNull()
    expect(toNumber(null)).toBeNull()
    expect(toNumber(undefined)).toBeNull()
    expect(toNumber('nie je číslo')).toBeNull()
  })
})

describe('money', () => {
  it('oddeľuje tisíce nezlomiteľnou medzerou', () => {
    // Bez nej by sa suma mohla zlomiť do dvoch riadkov.
    expect(money('1180')).toBe(`1${NBSP}180${NBSP}€`)
    expect(money('8930')).toBe(`8${NBSP}930${NBSP}€`)
  })

  it('malé sumy ukazuje na dve desatinné miesta', () => {
    expect(money('679.99')).toBe(`679,99${NBSP}€`)
  })

  it('pri znamienku pridá plus, záporné číslo má mínus', () => {
    expect(money('355', { sign: true, decimals: 0 })).toBe(`+355${NBSP}€`)
    expect(money('-120', { sign: true, decimals: 0 })).toBe(`−120${NBSP}€`)
  })

  it('bez zadaných desatinných miest rozhoduje veľkosť sumy', () => {
    // Tisícové sumy sa čítajú lepšie bez centov, malé s nimi.
    expect(money('355')).toBe(`355,00${NBSP}€`)
    expect(money('1180')).toBe(`1${NBSP}180${NBSP}€`)
  })

  it('neznámu hodnotu ukáže ako pomlčku', () => {
    expect(money(null)).toBe('—')
    expect(money('')).toBe('—')
  })

  it('exactMoney vždy drží dve desatinné miesta', () => {
    expect(exactMoney('1180')).toBe(`1${NBSP}180,00${NBSP}€`)
  })
})

describe('percent', () => {
  it('formátuje s desatinnou čiarkou a medzerou pred znakom', () => {
    expect(percent(60.2)).toBe(`+60,2${NBSP}%`)
    expect(percent(-2.6)).toBe(`−2,6${NBSP}%`)
  })

  it('vie potlačiť znamienko', () => {
    expect(percent(22, { decimals: 0, sign: false })).toBe(`22${NBSP}%`)
  })

  it('neznámu hodnotu ukáže ako pomlčku', () => {
    expect(percent(null)).toBe('—')
    expect(percent(Number.NaN)).toBe('—')
  })
})

describe('count', () => {
  it('oddeľuje tisíce', () => {
    expect(count(9090)).toBe(`9${NBSP}090`)
    expect(count(68_420)).toBe(`68${NBSP}420`)
  })
})

describe('shortDate', () => {
  it('formátuje slovenský dátum', () => {
    expect(shortDate('2024-03-14')).toContain('2024')
  })

  it('zvládne chýbajúcu alebo pokazenú hodnotu', () => {
    expect(shortDate(null)).toBe('—')
    expect(shortDate('nie je dátum')).toBe('—')
  })
})

describe('trendColor', () => {
  it('rozlíši zisk, stratu a nulu', () => {
    expect(trendColor('355')).toBe('positive')
    expect(trendColor('-21')).toBe('negative')
    expect(trendColor('0')).toBe('medium-emphasis')
    expect(trendColor(null)).toBe('medium-emphasis')
  })
})

describe('skryté ceny', () => {
  it('sumy nahradí zástupným znakom, percentá a počty ostanú', async () => {
    const { setPricesHidden } = await import('./format')
    setPricesHidden(true)
    try {
      expect(money('1180.5')).toBe(`•••${NBSP}€`)
      expect(exactMoney(12)).toBe(`•••${NBSP}€`)
      // Bez ceny ostáva pomlčka: skrytá nula by vyzerala ako cena.
      expect(money(null)).toBe('—')
      expect(percent(12)).not.toContain('•')
      expect(count(1500)).not.toContain('•')
    } finally {
      setPricesHidden(false)
    }
    expect(money('10')).toBe(`10,00${NBSP}€`)
  })
})

describe('skryté ceny pri štarte', () => {
  it('pamätajú sa v prehliadači, aby sa sumy neukázali pred načítaním účtu', async () => {
    const { setPricesHidden, storedPricesHidden } = await import('./format')
    setPricesHidden(true)
    expect(storedPricesHidden()).toBe(true)
    setPricesHidden(false)
    expect(storedPricesHidden()).toBe(false)
  })
})
