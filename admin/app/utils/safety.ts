import type { AlertKind, AlertStatus, SafetyAlert, SafetySummary } from '~/types/api'
import type { LatLng } from '~/utils/geo'

/** How often the admin asks for the safety summary (doc 11: an SOS shows in under 5 s). */
export const SAFETY_POLL_MS = 4000

export const ALERT_COLORS: Record<AlertKind, string> = {
  sos: '#dc2626',
  stop: '#d97706',
  deviation: '#d97706',
  overtime: '#d97706',
}

export function alertStatusColor(status: AlertStatus): 'error' | 'warning' | 'info' | 'success' | 'neutral' {
  return ({ open: 'error', acknowledged: 'warning', checking: 'info', resolved: 'success', dismissed: 'neutral' } as const)[status]
}

export const isAlertActive = (status: AlertStatus) => status === 'open' || status === 'acknowledged'

/**
 * Whether a new summary should ring: there is an open alert the panel had not seen yet. The first
 * summary after loading rings too when something is open (someone has to look at it).
 */
export function shouldRing(previous: SafetySummary | null, next: SafetySummary): boolean {
  if (!next.open || !next.latest_id) return false
  return previous?.latest_id !== next.latest_id
}

/** Best known position of an alert: the SOS position, else the driver's live location. */
export function alertPosition(alert: SafetyAlert): LatLng | null {
  if (alert.lat !== null && alert.lng !== null) return [alert.lat, alert.lng]
  if (alert.driver_location) return [alert.driver_location.lat, alert.driver_location.lng]
  return null
}

/** Track points ([lat, lng, ts]) as map coordinates. */
export function trackLine(track: [number, number, number][] | undefined | null): LatLng[] {
  return (track ?? []).map(([lat, lng]) => [lat, lng] as LatLng)
}

/** Short reading of an anomaly's details ("12 min", "840 m"). */
export function alertDetail(alert: Pick<SafetyAlert, 'kind' | 'details'>): string {
  const d = alert.details ?? {}
  if (alert.kind === 'stop' && typeof d.minutes === 'number') return `${d.minutes} min`
  if (alert.kind === 'deviation' && typeof d.distance_m === 'number') return `${d.distance_m} m`
  if (alert.kind === 'overtime' && typeof d.minutes === 'number') {
    return typeof d.estimated_minutes === 'number' ? `${d.minutes} / ${d.estimated_minutes} min` : `${d.minutes} min`
  }
  return ''
}

let audio: AudioContext | null = null

/** Three short beeps (no audio file to ship). Browsers allow it after the first click on the page. */
export function playAlarm(): void {
  try {
    audio ??= new AudioContext()
    const ctx = audio
    void ctx.resume()
    for (let i = 0; i < 3; i++) {
      const start = ctx.currentTime + i * 0.35
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      osc.type = 'square'
      osc.frequency.value = 880
      gain.gain.setValueAtTime(0.0001, start)
      gain.gain.exponentialRampToValueAtTime(0.2, start + 0.02)
      gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.25)
      osc.connect(gain).connect(ctx.destination)
      osc.start(start)
      osc.stop(start + 0.3)
    }
  }
  catch {
    // No Web Audio (old browser, tests): the badge still shows.
  }
}
