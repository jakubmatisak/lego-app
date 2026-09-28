/**
 * Oznámenia v celej appke: jedna fronta pre `<v-snackbar-queue>` v layoute.
 *
 * Každé pridanie, úprava a zmazanie ohlási výsledok cez `success` alebo
 * `error`, nie vlastným snackbarom v komponente. Chyba, ktorá patrí k poľu
 * vo formulári, ostáva pri poli; sem ide výsledok akcie.
 *
 * Správa môže mať jedno tlačidlo (napríklad Späť po automatickom uložení).
 * Fronta Vuetify dá vlastnosti správy rovno do `v-snackbar`, funkcia by
 * skončila ako atribút v HTML. Preto správa nesie len `data-notice` s id
 * a akciu drží store; po zatvorení správy ju zabudne.
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import { errorMessage } from '@/api/client'

export interface NoticeAction {
  label: string
  run: () => void | Promise<void>
}

export interface Notice {
  'text': string
  'color': 'positive' | 'negative' | 'info' | 'warning'
  'timeout': number
  'data-notice': string
  'onDismiss'?: (reason: string) => void
}

const TIMEOUT = { positive: 3000, negative: 6000, info: 4000, warning: 6000, action: 8000 } as const

export const useNotifyStore = defineStore('notify', () => {
  const queue = ref<Notice[]>([])
  const actions = new Map<string, NoticeAction>()
  let lastId = 0

  function push (text: string, color: Notice['color'], action?: NoticeAction): void {
    const id = String(++lastId)
    if (action) {
      actions.set(id, action)
    }
    queue.value.push({
      text,
      color,
      'timeout': action ? TIMEOUT.action : TIMEOUT[color],
      'data-notice': id,
      'onDismiss': () => actions.delete(id),
    })
  }

  function success (text: string, action?: NoticeAction): void {
    push(text, 'positive', action)
  }

  function info (text: string, action?: NoticeAction): void {
    push(text, 'info', action)
  }

  /** Niečo sa neurobilo, ale nie je to chyba (séria bez vybraných figúrok). */
  function warn (text: string): void {
    push(text, 'warning')
  }

  /** Text, výnimka alebo chyba z API; `fallback`, keď z nej nič nevyčítame. */
  function error (reason: unknown, fallback = 'Niečo sa pokazilo'): void {
    let text: string
    if (typeof reason === 'string') {
      text = reason
    } else if (reason instanceof Error) {
      text = reason.message || fallback
    } else {
      text = errorMessage(reason, fallback)
    }
    push(text, 'negative')
  }

  function actionFor (id: string | undefined): NoticeAction | null {
    return (id && actions.get(id)) || null
  }

  /** Spustí akciu správy raz; druhé ťuknutie už nič neurobí. */
  async function run (id: string | undefined): Promise<void> {
    const action = actionFor(id)
    if (!action || !id) {
      return
    }
    actions.delete(id)
    await action.run()
  }

  return { queue, success, info, warn, error, actionFor, run }
})
