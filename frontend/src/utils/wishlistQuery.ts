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
}

export function wishlistQuery (view: WishView): Record<string, string | boolean> {
  const out: Record<string, string | boolean> = { sort: view.sort }
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
  return out
}

export function hasWishFilter (view: WishView): boolean {
  return Boolean((view.q ?? '').trim() || view.reached || view.retired || view.noPrice)
}
