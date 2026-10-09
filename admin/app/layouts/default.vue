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
let countsTimer: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  reportCounts.refresh()
  countsTimer = setInterval(() => {
    if (document.visibilityState === 'visible') reportCounts.refresh()
  }, 60_000)
})
onBeforeUnmount(() => clearInterval(countsTimer))
watch(() => route.path, () => reportCounts.refresh())

const links = computed<NavigationMenuItem[]>(() => [
  { label: t('nav.dashboard'), icon: 'i-lucide-layout-dashboard', to: '/' },
  { label: t('nav.users'), icon: 'i-lucide-users', to: '/users' },
  { label: t('nav.drivers'), icon: 'i-lucide-bike', to: '/drivers' },
  { label: t('nav.rides'), icon: 'i-lucide-route', to: '/rides' },
  { label: t('nav.live'), icon: 'i-lucide-radar', to: '/live' },
  { label: t('nav.reports'), icon: 'i-lucide-flag', to: '/reports', badge: reportsBadge.value },
  { label: t('nav.rates'), icon: 'i-lucide-banknote', to: '/rates' },
  { label: t('nav.promotions'), icon: 'i-lucide-ticket-percent', to: '/promotions' },
  { label: t('nav.topUps'), icon: 'i-lucide-wallet', to: '/top-ups' },
  { label: t('nav.transfers'), icon: 'i-lucide-arrow-left-right', to: '/transfers' },
  { label: t('nav.subscriptions'), icon: 'i-lucide-calendar-check', to: '/subscriptions' },
  { label: t('nav.finance'), icon: 'i-lucide-landmark', to: '/finance' },
  { label: t('nav.notifications'), icon: 'i-lucide-bell', to: '/notifications' },
  { label: t('nav.settings'), icon: 'i-lucide-settings', to: '/settings' },
  { label: t('nav.profile'), icon: 'i-lucide-user-cog', to: '/profile' },
])

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
  </UDashboardGroup>
</template>
