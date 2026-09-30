/**
 * Nové načítanie stránky pri zmene účtu.
 *
 * Store-y (zbierka, filtre, Prehľad…) držia dáta v pamäti stránky. Pri
 * odhlásení a prihlásení iného účtu by sa na chvíľu ukázali dáta toho
 * predošlého, kým prídu nové. Nové načítanie pamäť vyprázdni celú; relácia
 * ostáva v cookie, takže sa používateľ nemusí prihlasovať znova.
 */
export function reloadTo (path: string): void {
  window.location.assign(path)
}

/**
 * Kam ísť po prihlásení (`?redirect=`): len cesta v rámci appky.
 *
 * Adresa `//iny.web` alebo `https://…` by po prihlásení poslala
 * používateľa na cudzí web, ktorý môže ukázať falošné prihlásenie.
 */
export function safeRedirect (raw: string | null | undefined): string {
  if (typeof raw !== 'string' || !raw.startsWith('/')) {
    return '/'
  }
  if (raw.startsWith('//') || raw.startsWith('/\\')) {
    return '/'
  }
  return raw
}

/**
 * Trasa, podľa ktorej sa zvýrazní ponuka. Detail setu patrí Zbierke, ale
 * figúrka zo série v Zbierke nie je: odkazy z Figúrok pridajú
 * `?from=minifigs` a ponuka potom ostane na Figúrkach.
 */
export function sectionRoute (name: string | null | undefined, query: Record<string, unknown>): string {
  if (name === 'set-detail' && query.from === 'minifigs') {
    return 'minifig-series'
  }
  return name ?? ''
}
