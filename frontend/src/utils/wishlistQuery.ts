/**
 * Parametre `GET /wishlist` zo stavu obrazovky Chcem. Krížik v poli
 * hľadania nastaví `null`, nie prázdny text, preto `?? ''`.
 */

export interface WishView {
  q: string | null
  sort: string
  dir: 'asc' | 'desc' | null
  reached: boolean
  retired: boolean
  noPrice: boolean
  /** Séria z katalógu; `__none__` = set bez série. */
  themes: string[]
}

export function wishlistQuery (view: WishView): Record<string, string | boolean | string[]> {
  const out: Record<string, string | boolean | string[]> = { sort: view.sort }
  const q = (view.q ?? '').trim()
  if (view.dir) {
    out.dir = view.dir
  }
  if (q) {
    out.q = q
  }
  if (view.reached) {
    out.reached = true
  }
  if (view.retired) {
    out.retired = true
  }
  if (view.noPrice) {
    out.no_price = true
  }
  if (view.themes.length > 0) {
    out.theme = [...view.themes]
  }
  return out
}

export function hasWishFilter (view: WishView): boolean {
  return Boolean((view.q ?? '').trim() || view.reached || view.retired || view.noPrice || view.themes.length > 0)
}
