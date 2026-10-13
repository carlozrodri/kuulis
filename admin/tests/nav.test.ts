import { describe, expect, it } from 'vitest'
import { activeNavEntry, NAV, NAV_GROUPS, navTree } from '../app/utils/nav'

const none = () => false

describe('admin menu', () => {
  it('puts every grouped page in a known section', () => {
    const keys = NAV_GROUPS.map(g => g.key)
    for (const entry of NAV) {
      if (entry.group) expect(keys).toContain(entry.group)
    }
  })

  it('folds pages into sections for an admin, dashboard first and profile last', () => {
    const tree = navTree(true, none)
    expect(tree[0]).toMatchObject({ kind: 'entry', entry: { key: 'dashboard' } })
    expect(tree.at(-1)).toMatchObject({ kind: 'entry', entry: { key: 'profile' } })
    expect(tree.filter(n => n.kind === 'group').map(n => n.kind === 'group' && n.key)).toEqual(NAV_GROUPS.map(g => g.key))
    expect(tree.length).toBe(NAV_GROUPS.length + 2)
  })

  it('shows a lone allowed page on its own and hides empty sections', () => {
    const can = (p: string) => p === 'reports.manage' || p === 'rides.view'
    const tree = navTree(false, can)
    const support = tree.find(n => n.kind === 'group' && n.key === 'support')
    expect(support?.kind === 'group' && support.entries.map(e => e.key)).toEqual(['reports', 'cannedReplies', 'supportMetrics'])
    expect(tree.some(n => n.kind === 'entry' && n.entry.key === 'rides')).toBe(true)
    expect(tree.some(n => n.kind === 'group' && n.key === 'money')).toBe(false)
    // Approvals needs no permission, so staff see it on its own.
    expect(tree.some(n => n.kind === 'entry' && n.entry.key === 'approvals')).toBe(true)
  })

  it('marks the most specific page as active', () => {
    expect(activeNavEntry('/drivers/checks/abc')?.key).toBe('driverChecks')
    expect(activeNavEntry('/drivers/123')?.key).toBe('drivers')
    expect(activeNavEntry('/')?.key).toBe('dashboard')
    expect(activeNavEntry('/support/canned')?.key).toBe('cannedReplies')
  })
})
