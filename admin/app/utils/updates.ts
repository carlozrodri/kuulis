import type { AdminUpdate, ReleaseChannel } from '~/types/api'

/** The APK's own code in the usage table. */
export const EMBEDDED_UPDATE = 'embedded'

/** First 8 characters of an update id or runtime fingerprint. */
export function shortId(id: string, length = 8): string {
  return id.slice(0, length)
}

/** Key of the slot an update competes in: platform, channel and native runtime. */
export function updateSlot(update: Pick<AdminUpdate, 'platform' | 'channel' | 'runtime_version'>): string {
  return `${update.platform}:${update.channel}:${update.runtime_version}`
}

/** Update each channel+runtime serves now: the newest not withdrawn, as the API picks it. */
export function currentUpdates(updates: AdminUpdate[]): Map<string, AdminUpdate> {
  const current = new Map<string, AdminUpdate>()
  for (const update of updates) {
    if (update.withdrawn_at) continue
    const key = updateSlot(update)
    const best = current.get(key)
    if (!best || Date.parse(update.created_at) > Date.parse(best.created_at)) current.set(key, update)
  }
  return current
}

export function isCurrentUpdate(current: Map<string, AdminUpdate>, update: AdminUpdate): boolean {
  return current.get(updateSlot(update))?.id === update.id
}

/**
 * Channels whose current update is this one (for the usage table). For 'embedded', the channels
 * whose current entry sends the apps back to the APK's code.
 */
export function channelsServingUpdate(current: Map<string, AdminUpdate>, updateId: string): ReleaseChannel[] {
  const channels = [...current.values()]
    .filter(u => (updateId === EMBEDDED_UPDATE ? u.kind === 'rollback' : u.id === updateId))
    .map(u => u.channel)
  return [...new Set(channels)]
}

export type RolloutState = 'paused' | 'partial' | 'full'

export function rolloutState(percent: number): RolloutState {
  if (percent <= 0) return 'paused'
  if (percent >= 100) return 'full'
  return 'partial'
}

/** Whole percentage within 0..100 (null when it is not a number). */
export function clampPercent(value: unknown): number | null {
  const n = typeof value === 'string' ? Number(value.trim()) : value
  if (typeof n !== 'number' || !Number.isFinite(n) || (typeof value === 'string' && value.trim() === '')) return null
  return Math.min(100, Math.max(0, Math.round(n)))
}
