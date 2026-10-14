<script setup lang="ts">
import type { NavigationMenuItem } from '@nuxt/ui'
import type { NavEntry } from '~/utils/nav'

const { t, locale, locales, setLocale } = useI18n()
const auth = useAuth()
const config = useRuntimeConfig()
const route = useRoute()

// Support badge: tickets waiting on the team (open ones on an older API), red when an urgent one is open.
// Refreshed every minute and on navigation.
const reportCounts = useReportCounts()
const reportsBadge = computed(() => {
  const counts = reportCounts.counts.value
  const waiting = counts?.waiting_staff ?? counts?.open
  if (!counts || !waiting) return undefined
  const urgent = counts.urgent_open > 0
  return {
    label: String(waiting),
    color: urgent ? 'error' as const : 'neutral' as const,
    variant: urgent ? 'solid' as const : 'subtle' as const,
    ...(urgent ? { title: t('reports.urgentOpen', { n: counts.urgent_open }) } : {}),
  }
})
// Requests waiting for this account's approval.
const approvalCount = useApprovalCount()
const approvalsBadge = computed(() =>
  approvalCount.pending.value ? { label: String(approvalCount.pending.value), color: 'warning' as const, variant: 'solid' as const } : undefined,
)
// Safety center (doc 11): polled every few seconds; a new open alert rings and shows in red.
const safety = useSafetySummary()
const safetyBadge = computed(() => {
  const s = safety.summary.value
  const total = (s?.open ?? 0) + (s?.acknowledged ?? 0)
  if (!total) return undefined
  return { label: String(total), color: s?.open ? 'error' as const : 'warning' as const, variant: 'solid' as const }
})
// Risk (doc 16): open alerts plus held payments.
const risk = useRiskSummary()
const riskBadge = computed(() => {
  const total = riskBadgeTotal(risk.summary.value)
  return total ? { label: String(total), color: 'warning' as const, variant: 'subtle' as const } : undefined
})
let safetyTimer: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  safety.refresh()
  // Keeps polling in a background tab too: the team must hear an SOS while working elsewhere.
  safetyTimer = setInterval(safety.refresh, SAFETY_POLL_MS)
})
onBeforeUnmount(() => clearInterval(safetyTimer))

function refreshCounts() {
  reportCounts.refresh()
  approvalCount.refresh()
  risk.refresh()
}
let countsTimer: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  refreshCounts()
  countsTimer = setInterval(() => {
    if (document.visibilityState === 'visible') refreshCounts()
  }, 60_000)
})
onBeforeUnmount(() => clearInterval(countsTimer))
watch(() => route.path, refreshCounts)

type NavBadge = { label: string, color: 'error' | 'warning' | 'neutral', variant: 'solid' | 'subtle', title?: string }
const badges = computed<Record<string, NavBadge | undefined>>(() => ({
  reports: reportsBadge.value,
  approvals: approvalsBadge.value,
  safety: safetyBadge.value,
  risk: riskBadge.value,
}))

// A folded section carries its pages' counts, coloured by the most urgent one, so an SOS still shows.
const SEVERITY = { neutral: 0, warning: 1, error: 2 } as const
function sectionBadge(entries: NavEntry[]): NavBadge | undefined {
  const found = entries.map(e => badges.value[e.key]).filter((b): b is NavBadge => !!b)
  if (!found.length) return undefined
  const worst = found.reduce((a, b) => (SEVERITY[b.color] > SEVERITY[a.color] ? b : a))
  const total = found.reduce((sum, b) => sum + Number(b.label), 0)
  return { label: String(total), color: worst.color, variant: worst.color === 'neutral' ? 'subtle' : 'solid' }
}

const tree = computed(() => navTree(auth.isAdmin.value, auth.can))
const activeEntry = computed(() => activeNavEntry(route.path))

// Open sections are remembered per browser; the section of the page in view always opens.
const OPEN_KEY = 'kuulis.admin.nav.open'
const openSections = ref<string[]>([])
onMounted(() => {
  try {
    const saved = JSON.parse(localStorage.getItem(OPEN_KEY) ?? '[]')
    if (Array.isArray(saved)) openSections.value = [...new Set([...openSections.value, ...saved.map(String)])]
  }
  catch { /* storage blocked or corrupt: start folded */ }
})
function setOpenSections(value: string[] | string | undefined) {
  openSections.value = Array.isArray(value) ? value : value ? [value] : []
  try {
    localStorage.setItem(OPEN_KEY, JSON.stringify(openSections.value))
  }
  catch { /* not persisted */ }
}
watch(() => activeEntry.value?.group, (group) => {
  if (group && !openSections.value.includes(group)) openSections.value = [...openSections.value, group]
}, { immediate: true })

function entryItem(entry: NavEntry, inSection: boolean): NavigationMenuItem {
  return {
    label: t(inSection && entry.shortLabel ? entry.shortLabel : `nav.${entry.key}`),
    icon: entry.icon,
    to: entry.to,
    active: activeEntry.value?.key === entry.key,
    badge: badges.value[entry.key],
  }
}

const links = computed<NavigationMenuItem[]>(() =>
  tree.value.map((node) => {
    if (node.kind === 'entry') return entryItem(node.entry, false)
    const open = openSections.value.includes(node.key)
    return {
      label: t(`navGroups.${node.key}`),
      icon: node.icon,
      value: node.key,
      type: 'trigger' as const,
      active: node.entries.some(e => e.key === activeEntry.value?.key),
      badge: open ? undefined : sectionBadge(node.entries),
      children: node.entries.map(entry => entryItem(entry, true)),
    }
  }),
)

const localeItems = computed(() =>
  locales.value.map(l => ({ label: l.name ?? l.code, value: l.code })),
)
</script>

<template>
  <UDashboardGroup>
    <UDashboardSidebar
      collapsible
      resizable
      :default-size="18"
      :min-size="14"
      :max-size="25"
    >
      <template #header="{ collapsed }">
        <div class="flex items-center gap-2 font-semibold">
          <UIcon
            name="i-lucide-shield-check"
            class="size-5 text-primary"
          />
          <span v-if="!collapsed">Kuulis Admin</span>
          <UBadge
            v-if="!collapsed && config.public.appEnv !== 'production'"
            color="warning"
            variant="subtle"
            size="sm"
          >
            {{ config.public.appEnv }}
          </UBadge>
        </div>
      </template>

      <template #default="{ collapsed }">
        <UNavigationMenu
          :items="links"
          orientation="vertical"
          :collapsed="collapsed"
          :model-value="openSections"
          popover
          tooltip
          @update:model-value="setOpenSections"
        />
      </template>

      <template #footer="{ collapsed }">
        <div class="flex w-full flex-col gap-2">
          <USelect
            v-if="!collapsed"
            :model-value="locale"
            :items="localeItems"
            size="sm"
            @update:model-value="(v) => setLocale(v as 'es' | 'en')"
          />
          <UButton
            :label="collapsed ? undefined : t('auth.logout')"
            icon="i-lucide-log-out"
            color="neutral"
            variant="ghost"
            block
            @click="auth.logout()"
          />
        </div>
      </template>
    </UDashboardSidebar>

    <slot />
    <ReauthModal />
  </UDashboardGroup>
</template>
