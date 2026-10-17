/** Admin menu: each entry shows only to accounts whose role allows it (doc 06). */
export interface NavEntry {
  key: string
  icon: string
  to: string
  /** Staff permission needed; admins see everything. */
  permission?: string
  adminOnly?: boolean
  /** Section the entry sits in; entries without one stay at the top level. */
  group?: NavGroupKey
  /** i18n key used inside its section when the page name would repeat the section's (nav.reports is "Soporte"). */
  shortLabel?: string
}

export type NavGroupKey = 'operations' | 'people' | 'support' | 'money' | 'messaging' | 'platform' | 'administration'

/** Sections in menu order, each folding its pages. */
export const NAV_GROUPS: { key: NavGroupKey, icon: string }[] = [
  { key: 'operations', icon: 'i-lucide-radar' },
  { key: 'people', icon: 'i-lucide-users' },
  { key: 'support', icon: 'i-lucide-life-buoy' },
  { key: 'money', icon: 'i-lucide-landmark' },
  { key: 'messaging', icon: 'i-lucide-megaphone' },
  { key: 'platform', icon: 'i-lucide-smartphone' },
  { key: 'administration', icon: 'i-lucide-shield-check' },
]

export const NAV: NavEntry[] = [
  { key: 'dashboard', icon: 'i-lucide-layout-dashboard', to: '/', permission: 'dashboard.view' },
  { key: 'rides', icon: 'i-lucide-route', to: '/rides', permission: 'rides.view', group: 'operations' },
  { key: 'live', icon: 'i-lucide-radar', to: '/live', permission: 'live.view', group: 'operations' },
  { key: 'zones', icon: 'i-lucide-map', to: '/zones', permission: 'zones.view', group: 'operations' },
  { key: 'safety', icon: 'i-lucide-siren', to: '/safety', permission: 'safety.view', group: 'operations' },
  { key: 'quality', icon: 'i-lucide-gauge', to: '/quality', permission: 'quality.view', group: 'operations' },
  { key: 'risk', icon: 'i-lucide-shield-alert', to: '/risk', permission: 'risk.view', group: 'operations' },
  { key: 'analytics', icon: 'i-lucide-chart-pie', to: '/analytics', permission: 'analytics.view', group: 'operations' },
  { key: 'users', icon: 'i-lucide-users', to: '/users', permission: 'users.view', group: 'people' },
  { key: 'drivers', icon: 'i-lucide-bike', to: '/drivers', permission: 'drivers.view', group: 'people' },
  { key: 'driverChecks', icon: 'i-lucide-scan-face', to: '/drivers/checks', permission: 'drivers.view', group: 'people' },
  { key: 'privacy', icon: 'i-lucide-user-x', to: '/privacy', permission: 'users.view', group: 'people' },
  { key: 'reports', icon: 'i-lucide-inbox', to: '/reports', permission: 'reports.manage', group: 'support', shortLabel: 'navShort.reports' },
  { key: 'cannedReplies', icon: 'i-lucide-message-square-quote', to: '/support/canned', permission: 'reports.manage', group: 'support' },
  { key: 'supportMetrics', icon: 'i-lucide-chart-no-axes-column', to: '/support/metrics', permission: 'reports.manage', group: 'support' },
  { key: 'help', icon: 'i-lucide-book-open', to: '/help', permission: 'help.manage', group: 'support' },
  { key: 'finance', icon: 'i-lucide-chart-line', to: '/finance', permission: 'finance.view', group: 'money', shortLabel: 'navShort.finance' },
  { key: 'closings', icon: 'i-lucide-book-lock', to: '/closings', permission: 'finance.view', group: 'money' },
  { key: 'topUps', icon: 'i-lucide-wallet', to: '/top-ups', permission: 'top_ups.view', group: 'money' },
  { key: 'transfers', icon: 'i-lucide-arrow-left-right', to: '/transfers', permission: 'transfers.view', group: 'money' },
  { key: 'subscriptions', icon: 'i-lucide-calendar-check', to: '/subscriptions', permission: 'subscriptions.view', group: 'money' },
  { key: 'rates', icon: 'i-lucide-banknote', to: '/rates', permission: 'rates.view', group: 'money' },
  { key: 'promotions', icon: 'i-lucide-ticket-percent', to: '/promotions', permission: 'promotions.view', group: 'money' },
  { key: 'campaigns', icon: 'i-lucide-send', to: '/campaigns', permission: 'notifications.send', group: 'messaging' },
  { key: 'notifications', icon: 'i-lucide-bell', to: '/notifications', permission: 'notifications.send', group: 'messaging' },
  { key: 'announcements', icon: 'i-lucide-megaphone', to: '/announcements', permission: 'announcements.view', group: 'messaging' },
  { key: 'emailTemplates', icon: 'i-lucide-mail', to: '/email-templates', permission: 'notifications.send', group: 'messaging' },
  { key: 'appStatus', icon: 'i-lucide-power', to: '/app-status', permission: 'app_status.view', group: 'platform' },
  { key: 'flags', icon: 'i-lucide-toggle-right', to: '/flags', permission: 'flags.view', group: 'platform' },
  { key: 'versions', icon: 'i-lucide-smartphone', to: '/versions', permission: 'releases.view', group: 'platform' },
  { key: 'system', icon: 'i-lucide-activity', to: '/system', permission: 'system.view', group: 'platform' },
  { key: 'settings', icon: 'i-lucide-settings', to: '/settings', permission: 'config.view', group: 'platform' },
  { key: 'approvals', icon: 'i-lucide-stamp', to: '/approvals', group: 'administration' },
  { key: 'team', icon: 'i-lucide-users-round', to: '/team', adminOnly: true, group: 'administration' },
  { key: 'roles', icon: 'i-lucide-shield-check', to: '/roles', adminOnly: true, group: 'administration' },
  { key: 'audit', icon: 'i-lucide-scroll-text', to: '/audit', adminOnly: true, group: 'administration' },
  { key: 'legal', icon: 'i-lucide-scale', to: '/legal', adminOnly: true, group: 'administration' },
  { key: 'profile', icon: 'i-lucide-user-cog', to: '/profile' },
]

export function navAllowed(entry: Pick<NavEntry, 'permission' | 'adminOnly'>, isAdmin: boolean, can: (p: string) => boolean): boolean {
  if (isAdmin) return true
  if (entry.adminOnly) return false
  return !entry.permission || can(entry.permission)
}

/** First page an account may open (staff without the dashboard land elsewhere). */
export function homePath(isAdmin: boolean, can: (p: string) => boolean): string {
  return NAV.find(entry => navAllowed(entry, isAdmin, can))?.to ?? '/profile'
}

export type NavNode
  = | { kind: 'entry', entry: NavEntry }
    | { kind: 'group', key: NavGroupKey, icon: string, entries: NavEntry[] }

/**
 * The menu this account sees: top-level entries in place, the rest folded into their sections.
 * NAV lists sections in order. Sections with nothing allowed disappear, and a section with one page
 * shows that page on its own.
 */
export function navTree(isAdmin: boolean, can: (p: string) => boolean): NavNode[] {
  const allowed = NAV.filter(entry => navAllowed(entry, isAdmin, can))
  const nodes: NavNode[] = []
  const placed = new Set<NavGroupKey>()
  for (const entry of allowed) {
    if (!entry.group) {
      nodes.push({ kind: 'entry', entry })
      continue
    }
    if (placed.has(entry.group)) continue
    placed.add(entry.group)
    const entries = allowed.filter(e => e.group === entry.group)
    const group = NAV_GROUPS.find(g => g.key === entry.group)!
    nodes.push(entries.length === 1 ? { kind: 'entry', entry: entries[0]! } : { kind: 'group', key: group.key, icon: group.icon, entries })
  }
  return nodes
}

/** Longest entry path that contains the current route (/drivers/checks/1 is Reverificaciones, not Motorizados). */
export function activeNavEntry(path: string, entries: NavEntry[] = NAV): NavEntry | undefined {
  return entries
    .filter(e => e.to === '/' ? path === '/' : path === e.to || path.startsWith(`${e.to}/`))
    .sort((a, b) => b.to.length - a.to.length)[0]
}
