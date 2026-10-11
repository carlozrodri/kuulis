/** Admin menu: each entry shows only to accounts whose role allows it (doc 06). */
export interface NavEntry {
  key: string
  icon: string
  to: string
  /** Staff permission needed; admins see everything. */
  permission?: string
  adminOnly?: boolean
}

export const NAV: NavEntry[] = [
  { key: 'dashboard', icon: 'i-lucide-layout-dashboard', to: '/', permission: 'dashboard.view' },
  { key: 'users', icon: 'i-lucide-users', to: '/users', permission: 'users.view' },
  { key: 'drivers', icon: 'i-lucide-bike', to: '/drivers', permission: 'drivers.view' },
  { key: 'rides', icon: 'i-lucide-route', to: '/rides', permission: 'rides.view' },
  { key: 'live', icon: 'i-lucide-radar', to: '/live', permission: 'live.view' },
  { key: 'reports', icon: 'i-lucide-flag', to: '/reports', permission: 'reports.manage' },
  { key: 'rates', icon: 'i-lucide-banknote', to: '/rates', permission: 'rates.view' },
  { key: 'promotions', icon: 'i-lucide-ticket-percent', to: '/promotions', permission: 'promotions.view' },
  { key: 'topUps', icon: 'i-lucide-wallet', to: '/top-ups', permission: 'top_ups.view' },
  { key: 'transfers', icon: 'i-lucide-arrow-left-right', to: '/transfers', permission: 'transfers.view' },
  { key: 'subscriptions', icon: 'i-lucide-calendar-check', to: '/subscriptions', permission: 'subscriptions.view' },
  { key: 'finance', icon: 'i-lucide-landmark', to: '/finance', permission: 'finance.view' },
  { key: 'system', icon: 'i-lucide-activity', to: '/system', permission: 'system.view' },
  { key: 'notifications', icon: 'i-lucide-bell', to: '/notifications', permission: 'notifications.send' },
  { key: 'approvals', icon: 'i-lucide-stamp', to: '/approvals' },
  { key: 'team', icon: 'i-lucide-users-round', to: '/team', adminOnly: true },
  { key: 'roles', icon: 'i-lucide-shield-check', to: '/roles', adminOnly: true },
  { key: 'privacy', icon: 'i-lucide-user-x', to: '/privacy', permission: 'users.view' },
  { key: 'versions', icon: 'i-lucide-smartphone', to: '/versions', permission: 'releases.view' },
  { key: 'legal', icon: 'i-lucide-scale', to: '/legal', adminOnly: true },
  { key: 'audit', icon: 'i-lucide-scroll-text', to: '/audit', adminOnly: true },
  { key: 'settings', icon: 'i-lucide-settings', to: '/settings', permission: 'config.view' },
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
