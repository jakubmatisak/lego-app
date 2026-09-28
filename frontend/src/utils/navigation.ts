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
