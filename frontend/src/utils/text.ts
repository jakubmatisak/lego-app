/** Text na porovnanie: bez diakritiky a veľkosti písmen, ako `filters.fold` na serveri. */
export function fold (text: string | null | undefined): string {
  return (text ?? '').normalize('NFKD').replace(/\p{M}/gu, '').toLocaleLowerCase('sk')
}
