/** "$5" or "$7.50": prices are in US dollars everywhere in Kuulis. */
export function usd(value: number): string {
  return Number.isInteger(value) ? `$${value}` : `$${value.toFixed(2)}`
}

/** "11 oct 2026" in the visitor's language. */
export function formatDay(iso: string, locale: string): string {
  return new Intl.DateTimeFormat(locale === 'en' ? 'en-US' : 'es-VE', { dateStyle: 'medium' }).format(new Date(iso))
}
