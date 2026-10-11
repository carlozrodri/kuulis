import type { AdminRelease, ReleaseChannel } from '~/types/api'

/** Bytes as megabytes for the tables: 52_428_800 → "50 MB". */
export function formatMegabytes(bytes: number | null | undefined, locale: string): string {
  if (bytes === null || bytes === undefined || !Number.isFinite(bytes)) return '—'
  return `${new Intl.NumberFormat(locale, { maximumFractionDigits: 1 }).format(bytes / 1_000_000)} MB`
}

/** "ab12cd34…9f0e" for long hashes. */
export function shortHash(hash: string, head = 8, tail = 4): string {
  return hash.length > head + tail + 1 ? `${hash.slice(0, head)}…${hash.slice(-tail)}` : hash
}

/** Release each channel offers now (per platform): the highest build not withdrawn, as the API picks it. */
export function latestByChannel(releases: AdminRelease[]): Map<string, AdminRelease> {
  const latest = new Map<string, AdminRelease>()
  for (const release of releases) {
    if (release.withdrawn_at) continue
    const key = `${release.platform}:${release.channel}`
    const current = latest.get(key)
    if (!current || release.build > current.build) latest.set(key, release)
  }
  return latest
}

/** Channels whose current release is this build (for the usage table). */
export function channelsOfferingBuild(latest: Map<string, AdminRelease>, platform: string, build: number): ReleaseChannel[] {
  return [...latest.values()]
    .filter(r => r.platform === platform && r.build === build)
    .map(r => r.channel)
}
