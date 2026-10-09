<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { AppConfig, Page, PromotionPairAlert } from '~/types/api'

const { t, locale } = useI18n()
const { request } = useApi()
const apiError = useApiError()

// The contract returns a plain list; accept a page envelope too in case the API paginates it later.
const { data, status, error, refresh } = await useAsyncData(
  'promotion-alerts',
  () => request<PromotionPairAlert[] | Page<PromotionPairAlert>>('/admin/promotions/alerts'),
)
const alerts = computed(() => {
  const value = data.value
  const list = !value ? [] : Array.isArray(value) ? value : value.items ?? []
  return [...list].sort((a, b) => b.rides - a.rides || b.last_ride_at.localeCompare(a.last_ride_at))
})

// Only used to explain the rule; defaults from the contract otherwise.
const { data: config } = await useAsyncData('promotion-alerts-config', () => request<AppConfig>('/admin/config').catch(() => null))
const threshold = computed(() => config.value?.promo_pair_alert_threshold ?? 3)
const days = computed(() => config.value?.promo_pair_alert_days ?? 30)

const columns = computed<TableColumn<PromotionPairAlert>[]>(() => [
  { id: 'passenger', header: t('rides.passenger') },
  { id: 'driver', header: t('rides.driver') },
  { accessorKey: 'rides', header: t('promotions.alerts.rides') },
  { accessorKey: 'discount_total', header: t('promotions.alerts.discountTotal') },
  { accessorKey: 'last_ride_at', header: t('promotions.alerts.lastRide') },
])
</script>

<template>
  <UDashboardPanel id="promotion-alerts">
    <template #header>
      <UDashboardNavbar :title="t('promotions.alerts.title')">
        <template #leading>
          <UButton
            icon="i-lucide-arrow-left"
            color="neutral"
            variant="ghost"
            :aria-label="t('common.back')"
            to="/promotions"
          />
        </template>
        <template #right>
          <UButton
            icon="i-lucide-refresh-cw"
            color="neutral"
            variant="outline"
            :label="t('promotions.alerts.refresh')"
            :loading="status === 'pending'"
            @click="refresh()"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <UAlert
        color="neutral"
        variant="subtle"
        icon="i-lucide-info"
        :title="t('promotions.alerts.rule', { n: threshold, days })"
        :description="t('promotions.alerts.help')"
      />
      <UAlert
        v-if="error"
        color="error"
        variant="subtle"
        icon="i-lucide-circle-alert"
        :title="apiError(error)"
      />
      <UTable
        :data="alerts"
        :columns="columns"
        :loading="status === 'pending'"
        :empty="t('promotions.alerts.empty')"
      >
        <template #passenger-cell="{ row }">
          <NuxtLink
            :to="`/users/${row.original.passenger.id}`"
            class="font-medium text-primary hover:underline"
          >
            {{ row.original.passenger.name || row.original.passenger.email || row.original.passenger.id.slice(0, 8) }}
          </NuxtLink>
          <p
            v-if="row.original.passenger.email"
            class="text-xs text-(--ui-text-muted)"
          >
            {{ row.original.passenger.email }}
          </p>
        </template>
        <template #driver-cell="{ row }">
          <NuxtLink
            :to="driverLink(row.original.driver.id, row.original.driver.profile_id)"
            class="font-medium text-primary hover:underline"
          >
            {{ row.original.driver.name || row.original.driver.email || row.original.driver.id.slice(0, 8) }}
          </NuxtLink>
          <p
            v-if="row.original.driver.email"
            class="text-xs text-(--ui-text-muted)"
          >
            {{ row.original.driver.email }}
          </p>
        </template>
        <template #rides-cell="{ row }">
          <UBadge
            color="warning"
            variant="subtle"
          >
            {{ row.original.rides }}
          </UBadge>
        </template>
        <template #discount_total-cell="{ row }">
          <span class="font-medium tabular-nums">{{ formatMoney(row.original.discount_total, locale) }}</span>
        </template>
        <template #last_ride_at-cell="{ row }">
          <span class="whitespace-nowrap">{{ formatDate(row.original.last_ride_at, locale) }}</span>
        </template>
      </UTable>
    </template>
  </UDashboardPanel>
</template>
