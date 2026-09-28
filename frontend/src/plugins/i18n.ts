import { createI18n } from 'vue-i18n'

import en from '@/locales/en.json'
import sk from '@/locales/sk.json'

/**
 * Slovenčina má tri tvary množného čísla: 1 set, 2 až 4 sety, 5 a viac setov.
 * Predvolené pravidlo vo vue-i18n pozná len dva, preto vlastné.
 */
function slovakPlural (choice: number, choicesLength: number): number {
  if (choicesLength < 3) {
    return choice === 1 ? 0 : 1
  }
  if (choice === 1) {
    return 0
  }
  if (choice >= 2 && choice <= 4) {
    return 1
  }
  return 2
}

export default createI18n({
  legacy: false,
  locale: 'sk',
  fallbackLocale: 'sk',
  messages: { sk, en },
  pluralRules: { sk: slovakPlural },
})
