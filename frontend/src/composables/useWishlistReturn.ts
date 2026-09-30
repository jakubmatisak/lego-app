/**
 * Kúpené vypadlo z Chcem: oznámenie a Späť.
 *
 * Server vyradí set z Chcem pri každom pridaní kusu (`POST /items`,
 * `/items/bulk`) a v odpovedi pošle pôvodnú položku (`removed_from_wishlist`).
 * Späť ju vráti cez `POST /wishlist` s cieľovou cenou, poznámkou aj dátumom
 * pridania, takže v Chcem ostane na svojom mieste.
 */

import type { RemovedWish } from '@/api/types'
import { useI18n } from 'vue-i18n'
import { api } from '@/api/client'
import { useCollectionStore } from '@/stores/collection'
import { useNotifyStore } from '@/stores/notify'

/** Výsledok vrátenia: koľko zlyhalo a čo ostalo mimo Chcem, lebo set ešte mám. */
export interface Restored {
  failed: number
  kept: RemovedWish[]
}

export function useWishlistReturn () {
  const { t } = useI18n()
  const notify = useNotifyStore()
  const collection = useCollectionStore()

  /** Názov jednej položky, pri viacerých ich počet („2 položky“). */
  function what (wishes: RemovedWish[]): string {
    const [only] = wishes
    return wishes.length === 1 && only
      ? only.name
      : t('wishlist.itemsPlural', wishes.length, { named: { count: wishes.length } })
  }

  /**
   * Vráti položky do Chcem s pôvodnými údajmi; povie, koľko sa nepodarilo.
   * `unlessOwned`: set, ktorý účet ešte má, server nevráti (204) a položka
   * je v `kept`. Tak Späť po automatickom uložení, keď ďalší sken uložil
   * ten istý set znova; kúpený set v Chcem nie je.
   */
  async function restore (wishes: RemovedWish[], options: { unlessOwned?: boolean } = {}): Promise<Restored> {
    const result: Restored = { failed: 0, kept: [] }
    for (const wish of wishes) {
      const { error, response } = await api.POST('/wishlist', {
        ...(options.unlessOwned ? { params: { query: { unless_owned: true } } } : {}),
        body: {
          catalog_num: wish.catalog_num,
          target_price_eur: wish.target_price_eur,
          note: wish.note,
          created_at: wish.created_at,
        },
      })
      if (response.status === 204) {
        result.kept.push(wish)
      } else if (error && response.status !== 409) {
        // 409: v Chcem už je (vrátil sa inak), Späť je splnené.
        result.failed += 1
      }
    }
    return result
  }

  /**
   * Oznámenie po uložení tlačidlom, vedľa oznámenia o pridaní. Späť vráti
   * len Chcem, kusy ostanú: kúpa platí, zmysel má len pri omyle v Chcem.
   */
  function announce (wishes: RemovedWish[]): void {
    if (wishes.length === 0) {
      return
    }
    const label = what(wishes)
    notify.success(t('notice.wishDropped', { what: label }), {
      label: t('notice.undo'),
      run: async () => {
        const { failed } = await restore(wishes)
        if (failed > 0) {
          notify.error(t('notice.undoFailed'))
        } else {
          notify.success(t('notice.wishRestored', { what: label }))
        }
        // Počet Chcem v ponuke je zo súhrnu.
        collection.refreshAll()
      },
    })
  }

  return { announce, restore, what }
}
