<script setup lang="ts">
import type { CurrentRates, UserStats } from '~/types/api'
import { RATE_SOURCES } from '~/types/api'

const { t } = useI18n()
const { request } = useApi()
const { data: stats, status } = await useAsyncData('user-stats', () => request<UserStats>('/users/stats'))

// GET /rates is public; failures (e.g. an API without phase 1C) just hide the warning.
const { data: rates } = await useAsyncData('dashboard-rates', () => request<CurrentRates>('/rates').catch(() => null))
const staleRates = computed(() => RATE_SOURCES.filter(source => rates.value?.[source]?.stale))

const cards = computed(() => [
  { label: t('dashboard.totalUsers'), value: stats.value?.total, icon: 'i-lucide-users' },
  { label: t('dashboard.activeUsers'), value: stats.value?.active, icon: 'i-lucide-user-check' },
  { label: t('dashboard.verifiedUsers'), value: stats.value?.verified, icon: 'i-lucide-badge-check' },
  { label: t('dashboard.staff'), value: (stats.value?.by_role.staff ?? 0) + (stats.value?.by_role.admin ?? 0), icon: 'i-lucide-shield' },
])
</script>

<template>
  <UDashboardPanel id="dashboard">
    <template #header>
      <UDashboardNavbar :title="t('nav.dashboard')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
      </UDashboardNavbar>
    </template>
    <template #body>
      <UAlert
        v-if="staleRates.length"
        color="warning"
        variant="subtle"
        icon="i-lucide-triangle-alert"
        :title="t('dashboard.staleRates', { sources: staleRates.map(s => t(`rates.sources.${s}`)).join(', ') })"
        :description="t('dashboard.staleRatesHelp')"
        :actions="[{ label: t('dashboard.openRates'), to: '/rates', color: 'warning', variant: 'outline' }]"
      />
      <div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <UCard
          v-for="card in cards"
          :key="card.label"
        >
          <div class="flex items-center gap-3">
            <UIcon
              :name="card.icon"
              class="size-8 text-primary"
            />
            <div>
              <p class="text-sm text-(--ui-text-muted)">
                {{ card.label }}
              </p>
              <USkeleton
                v-if="status === 'pending'"
                class="h-7 w-16"
              />
              <p
                v-else
                class="text-2xl font-semibold"
              >
                {{ card.value ?? 0 }}
              </p>
            </div>
          </div>
        </UCard>
      </div>
    </template>
  </UDashboardPanel>
</template>
