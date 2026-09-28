/**
 * Je otvorený dialóg? Sken z čítačky by inak prešiel na Pridať set
 * a dialóg s neuloženými úpravami by zmizol.
 */
export function dialogOpen (): boolean {
  return document.querySelector('.v-overlay.v-overlay--active.v-dialog') !== null
}
