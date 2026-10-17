/** Doc 22: the web invite page (/i/{code}) and the app link that opens "Invita y gana" with the code typed. */
export interface InviteProgram {
  active: boolean
  reward_usd: string
  required_trips: number
  window_days: number
  referred_free_month: boolean
  ends_at: string | null
}

export interface PublicInvite {
  code: string
  name: string | null
  program: InviteProgram
}

/** "ab3-k7q" → "AB3K7Q" (codes are typed by hand and shared in messages). */
export const normalizeInviteCode = (code: string) => code.toUpperCase().replace(/[^A-Z0-9]/g, '')

/** "AB3K7Q" → "AB3 K7Q", easy to read aloud. */
export function formatInviteCode(code: string): string {
  const clean = normalizeInviteCode(code)
  return clean.length === 6 ? `${clean.slice(0, 3)} ${clean.slice(3)}` : clean
}

/** Opens the installed app on Perfil → Invita y gana with the code already typed. */
export const appInviteLink = (code: string) => `kuulis://profile/invite?code=${encodeURIComponent(normalizeInviteCode(code))}`
