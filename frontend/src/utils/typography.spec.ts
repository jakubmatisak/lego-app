import { describe, expect, it } from 'vitest'

/**
 * Vuetify 4 nemá triedy písma z Vuetify 3 (nadpisy h4 až h6, subtitle, body-1
 * a body-2, caption, overline). Trieda bez štýlu nič nehlási, text má len
 * veľkosť rodiča, preto to stráži test. Náhrady: body-small, body-medium,
 * body-large, title-small, title-large, headline-small, headline-large
 * a label-medium.
 */
const sources = import.meta.glob<string>(['../**/*.vue', '../**/*.ts', '!../api/schema.d.ts'], {
  query: '?raw',
  import: 'default',
  eager: true,
})

const pattern = /(?<![\w-])text-(h[4-6]|subtitle-[12]|body-[12]|caption|overline)(?![\w-])/g

describe('triedy písma', () => {
  it('nepoužívajú triedy z Vuetify 3', () => {
    const found = Object.entries(sources).flatMap(([file, text]) =>
      [...text.matchAll(pattern)].map(m => `${file}: ${m[0]}`),
    )
    expect(Object.keys(sources).length).toBeGreaterThan(50)
    expect(found).toEqual([])
  })
})
