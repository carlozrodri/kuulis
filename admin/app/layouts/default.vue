<script setup lang="ts">
import type { NavigationMenuItem } from '@nuxt/ui'

const { t, locale, locales, setLocale } = useI18n()
const auth = useAuth()
const config = useRuntimeConfig()
const route = useRoute()

// Open reports badge (urgent ones in red), refreshed every minute and on navigation.
const reportCounts = useReportCounts()
const reportsBadge = computed(() => {
  const counts = reportCounts.counts.value
  if (!counts?.open) return undefined
  const urgent = counts.urgent_open > 0
  return {
    label: String(counts.open),
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
function refreshCounts() {
  reportCounts.refresh()
  approvalCount.refresh()
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

const links = computed<NavigationMenuItem[]>(() =>
  NAV.filter(entry => navAllowed(entry, auth.isAdmin.value, auth.can)).map(entry => ({
    label: t(`nav.${entry.key}`),
    icon: entry.icon,
    to: entry.to,
    ...(entry.key === 'reports' ? { badge: reportsBadge.value } : {}),
    ...(entry.key === 'approvals' ? { badge: approvalsBadge.value } : {}),
  })),
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
