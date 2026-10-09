<script setup lang="ts">
import type { AppConfig, CurrentRates, Metrics, Overview, RateSource, UserStats } from '~/types/api'
import { RATE_SOURCES } from '~/types/api'
import type { DayRange, RangePreset } from '~/utils/dates'

const { t, locale } = useI18n()
const { request } = useApi()
const apiError = useApiError()

// ---- Overview (live, refreshed every 30 s) ------------------------------------------------------

const { data: overview, status: overviewStatus, error: overviewError, refresh: refreshOverview } = await useAsyncData(
  'dashboard-overview',
  () => request<Overview>('/admin/overview'),
)
const updatedAt = ref<number | null>(null)
watch(overview, (value) => {
  if (value) updatedAt.value = Date.now()
}, { immediate: true })

let timer: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  timer = setInterval(() => {
    if (document.visibilityState === 'visible') refreshOverview()
  }, 30_000)
})
onBeforeUnmount(() => clearInterval(timer))

// Stale rates come with the overview; GET /rates (public) is the fallback against an older API.
const { data: rates } = await useAsyncData('dashboard-rates', () => request<CurrentRates>('/rates').catch(() => null))
const staleRates = computed<RateSource[]>(() =>
  overview.value?.stale_rates
    ? overview.value.stale_rates.filter(s => RATE_SOURCES.includes(s))
    : RATE_SOURCES.filter(source => rates.value?.[source]?.stale),
)

const liveCards = computed(() => {
  const o = overview.value
  return [
    { label: t('dashboard.overview.onlineDrivers'), value: formatNumber(o?.online_drivers, locale.value), icon: 'i-lucide-radar', to: '/live' },
    { label: t('dashboard.overview.ridesInProgress'), value: formatNumber(o?.rides_in_progress, locale.value), icon: 'i-lucide-bike', to: '/live' },
    { label: t('dashboard.overview.ridesToday'), value: formatNumber(o?.rides_today, locale.value), icon: 'i-lucide-route', to: { path: '/rides', query: { from: caracasToday(), to: caracasToday() } } },
    { label: t('dashboard.overview.completedToday'), value: formatNumber(o?.completed_today, locale.value), icon: 'i-lucide-flag', to: { path: '/rides', query: { status: 'completed', from: caracasToday(), to: caracasToday() } } },
    { label: t('dashboard.overview.gmvToday'), value: formatMoney(o?.gmv_today, locale.value), icon: 'i-lucide-circle-dollar-sign', to: undefined },
  ]
})

const NuxtLink = resolveComponent('NuxtLink')

type Tone = 'error' | 'warning' | 'info' | 'neutral'
interface ActionItem { key: string, label: string, count: number, icon: string, to: string | { path: string, query: Record<string, string> }, tone: Tone }

const actionItems = computed<ActionItem[]>(() => {
  const o = overview.value
  if (!o) return []
  const items: ActionItem[] = [
    { key: 'urgent', label: t('dashboard.actions.urgentReports', { n: o.urgent_reports }), count: o.urgent_reports, icon: 'i-lucide-siren', to: { path: '/reports', query: { priority: 'urgent' } }, tone: 'error' },
    { key: 'reports', label: t('dashboard.actions.openReports', { n: o.open_reports }), count: o.open_reports, icon: 'i-lucide-flag', to: '/reports', tone: 'warning' },
    { key: 'applications', label: t('dashboard.actions.driverApplications', { n: o.pending_driver_applications }), count: o.pending_driver_applications, icon: 'i-lucide-id-card', to: { path: '/drivers', query: { status: 'pending_review' } }, tone: 'info' },
    { key: 'pendingTopUps', label: t('dashboard.actions.pendingTopUps', { n: o.pending_top_ups }), count: o.pending_top_ups, icon: 'i-lucide-wallet', to: '/top-ups', tone: 'warning' },
    { key: 'unmatchedTopUps', label: t('dashboard.actions.unmatchedTopUps', { n: o.unmatched_top_ups }), count: o.unmatched_top_ups, icon: 'i-lucide-circle-help', to: { path: '/top-ups', query: { status: 'unmatched' } }, tone: 'warning' },
    { key: 'overdue', label: t('dashboard.actions.overdueDrivers', { n: o.overdue_drivers }), count: o.overdue_drivers, icon: 'i-lucide-lock', to: { path: '/subscriptions', query: { status: 'pending', month: 'all' } }, tone: 'neutral' },
  ]
  return items.filter(item => item.count > 0)
})
const toneClass: Record<Tone, string> = {
  error: 'bg-error/10 text-error',
  warning: 'bg-warning/10 text-warning',
  info: 'bg-info/10 text-info',
  neutral: 'bg-(--ui-bg-elevated) text-(--ui-text-muted)',
}

// ---- Metrics ------------------------------------------------------------------------------------

const metricPresets: Exclude<RangePreset, 'custom'>[] = ['today', 'last7', 'last30', 'thisMonth']
const metricPreset = ref<RangePreset>('last7')
const metricRange = ref<DayRange>(presetRange('last7'))
const area = ref<string>('all')

const { data: config } = await useAsyncData('dashboard-config', () => request<AppConfig>('/admin/config').catch(() => null))
const areaItems = computed(() => [
  { label: t('dashboard.metrics.allCities'), value: 'all' },
  ...(config.value?.service_areas ?? []).map(a => ({ label: a.name, value: a.name })),
])

const metricsQuery = computed(() => ({
  from: metricRange.value.from,
  to: metricRange.value.to,
  ...(area.value !== 'all' ? { area: area.value } : {}),
}))
const { data: metrics, status: metricsStatus, error: metricsError } = await useAsyncData(
  'dashboard-metrics',
  () => request<Metrics>('/admin/metrics', { query: metricsQuery.value }),
  { watch: [metricsQuery] },
)

const money = (value: string | number | null | undefined) => formatMoney(value, locale.value)
const num = (value: number | null | undefined) => formatNumber(value, locale.value)

interface Kpi { label: string, value: string, hint?: string }
const kpiGroups = computed<{ title: string, items: Kpi[] }[]>(() => {
  const m = metrics.value?.totals
  if (!m) return []
  const cancelled = m.rides_cancelled_passenger + m.rides_cancelled_driver + m.rides_cancelled_admin
  return [
    {
      title: t('dashboard.metrics.groups.rides'),
      items: [
        { label: t('dashboard.metrics.requested'), value: num(m.rides_requested) },
        { label: t('dashboard.metrics.completed'), value: num(m.rides_completed), hint: t('dashboard.metrics.completionRate', { rate: formatPercent(m.completion_rate, locale.value) }) },
        {
          label: t('dashboard.metrics.cancelled'),
          value: num(cancelled),
          hint: t('dashboard.metrics.cancelledSplit', { passenger: m.rides_cancelled_passenger, driver: m.rides_cancelled_driver, admin: m.rides_cancelled_admin }),
        },
        { label: t('dashboard.metrics.noDrivers'), value: num(m.rides_no_drivers) },
      ],
    },
    {
      title: t('dashboard.metrics.groups.money'),
      items: [
        { label: t('dashboard.metrics.gmv'), value: money(m.gmv), hint: t('dashboard.metrics.gmvHelp') },
        { label: t('dashboard.metrics.discounts'), value: money(m.discounts) },
        { label: t('dashboard.metrics.avgFare'), value: money(m.avg_fare) },
        { label: t('dashboard.metrics.avgDistance'), value: formatDistance(m.avg_distance_m, locale.value) },
      ],
    },
    {
      title: t('dashboard.metrics.groups.times'),
      items: [
        { label: t('dashboard.metrics.avgAssign'), value: formatSecondsAsMinutes(m.avg_assign_s, locale.value), hint: t('dashboard.metrics.avgAssignHelp') },
        { label: t('dashboard.metrics.avgPickup'), value: formatSecondsAsMinutes(m.avg_pickup_s, locale.value), hint: t('dashboard.metrics.avgPickupHelp') },
        { label: t('dashboard.metrics.avgTrip'), value: formatSecondsAsMinutes(m.avg_trip_s, locale.value), hint: t('dashboard.metrics.avgTripHelp') },
      ],
    },
    {
      title: t('dashboard.metrics.groups.people'),
      items: [
        { label: t('dashboard.metrics.activeDrivers'), value: num(m.active_drivers) },
        { label: t('dashboard.metrics.activePassengers'), value: num(m.active_passengers) },
        { label: t('dashboard.metrics.newPassengers'), value: num(m.new_passengers) },
        { label: t('dashboard.metrics.newDrivers'), value: num(m.new_drivers) },
        { label: t('dashboard.metrics.ratingDrivers'), value: formatRating(m.avg_rating_drivers) ?? '—' },
        { label: t('dashboard.metrics.ratingPassengers'), value: formatRating(m.avg_rating_passengers) ?? '—' },
      ],
    },
  ]
})

const metricDays = computed(() => (metrics.value ? listDays(metrics.value.from, metrics.value.to) : []))
const dayLabels = computed(() => metricDays.value.map(day => formatDay(day, locale.value)))
const dayTicks = computed(() => metricDays.value.map(day => formatShortDay(day, locale.value)))
const byDay = computed(() => new Map((metrics.value?.by_day ?? []).map(d => [d.date, d])))
const ridesByDay = computed(() => [
  { key: 'requested', label: t('dashboard.metrics.requested'), values: metricDays.value.map(d => byDay.value.get(d)?.requested ?? 0), color: 'var(--chart-1)' },
  { key: 'completed', label: t('dashboard.metrics.completed'), values: metricDays.value.map(d => byDay.value.get(d)?.completed ?? 0), color: 'var(--chart-3)' },
])
const gmvByDay = computed(() => [
  { key: 'gmv', label: t('dashboard.metrics.gmv'), values: metricDays.value.map(d => Number(byDay.value.get(d)?.gmv ?? 0) || 0), color: 'var(--chart-1)' },
])

const hours = Array.from({ length: 24 }, (_, h) => h)
const hourLabels = hours.map(h => `${String(h).padStart(2, '0')}:00–${String(h).padStart(2, '0')}:59`)
const hourTicks = hours.map(h => String(h).padStart(2, '0'))
const byHour = computed(() => new Map((metrics.value?.by_hour ?? []).map(h => [h.hour, h])))
const ridesByHour = computed(() => [
  { key: 'requested', label: t('dashboard.metrics.requested'), values: hours.map(h => byHour.value.get(h)?.requested ?? 0), color: 'var(--chart-1)' },
  { key: 'completed', label: t('dashboard.metrics.completed'), values: hours.map(h => byHour.value.get(h)?.completed ?? 0), color: 'var(--chart-3)' },
])
const peakHour = computed(() => {
  const list = metrics.value?.by_hour ?? []
  const top = list.reduce<(typeof list)[number] | null>((best, h) => (!best || h.requested > best.requested ? h : best), null)
  return top && top.requested > 0 ? top.hour : null
})

const intFormat = (value: number) => formatNumber(value, locale.value)
const compact = (value: number) => new Intl.NumberFormat(locale.value, { notation: 'compact', maximumFractionDigits: 1 }).format(value)

// ---- User stats (kept from the original dashboard) ---------------------------------------------

const { data: stats, status: statsStatus } = await useAsyncData('user-stats', () => request<UserStats>('/users/stats').catch(() => null))
const userCards = computed(() => [
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
        <template #right>
          <span
            v-if="updatedAt"
            class="hidden text-xs text-(--ui-text-muted) sm:inline"
          >{{ t('dashboard.updatedAt', { time: formatTime(new Date(updatedAt).toISOString(), locale) }) }}</span>
          <UButton
            icon="i-lucide-refresh-cw"
            color="neutral"
            variant="ghost"
            :aria-label="t('live.refresh')"
            :loading="overviewStatus === 'pending'"
            @click="refreshOverview()"
          />
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
      <UAlert
        v-if="overviewError && !overview"
        color="error"
        variant="subtle"
        icon="i-lucide-circle-alert"
        :title="apiError(overviewError)"
      />

      <!-- Live -->
      <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <component
          :is="card.to ? NuxtLink : 'div'"
          v-for="card in liveCards"
          :key="card.label"
          :to="card.to"
          class="block rounded-lg"
        >
          <UCard
            class="h-full"
            :class="card.to ? 'transition hover:ring-(--ui-primary)/40' : ''"
          >
            <div class="flex items-center gap-3">
              <UIcon
                :name="card.icon"
                class="size-7 shrink-0 text-primary"
              />
              <div class="min-w-0">
                <p class="text-sm text-(--ui-text-muted)">
                  {{ card.label }}
                </p>
                <USkeleton
                  v-if="overviewStatus === 'pending' && !overview"
                  class="h-7 w-16"
                />
                <p
                  v-else
                  class="text-2xl font-semibold tabular-nums"
                >
                  {{ card.value }}
                </p>
              </div>
            </div>
          </UCard>
        </component>
      </div>

      <!-- To do -->
      <UCard v-if="overview">
        <template #header>
          <h2 class="font-semibold">
            {{ t('dashboard.actions.title') }}
          </h2>
        </template>
        <p
          v-if="!actionItems.length && !staleRates.length"
          class="flex items-center gap-2 text-sm text-(--ui-text-muted)"
        >
          <UIcon
            name="i-lucide-circle-check"
            class="size-4 text-success"
          />
          {{ t('dashboard.actions.none') }}
        </p>
        <ul
          v-else
          class="grid gap-2 sm:grid-cols-2 xl:grid-cols-3"
        >
          <li
            v-for="item in actionItems"
            :key="item.key"
          >
            <NuxtLink
              :to="item.to"
              class="flex items-center gap-3 rounded-md border border-(--ui-border) p-3 text-sm hover:bg-(--ui-bg-elevated)"
            >
              <span
                class="flex size-8 shrink-0 items-center justify-center rounded-full"
                :class="toneClass[item.tone]"
              >
                <UIcon
                  :name="item.icon"
                  class="size-4"
                />
              </span>
              <span class="flex-1">{{ item.label }}</span>
              <UIcon
                name="i-lucide-chevron-right"
                class="size-4 text-(--ui-text-muted)"
              />
            </NuxtLink>
          </li>
          <li v-if="staleRates.length">
            <NuxtLink
              to="/rates"
              class="flex items-center gap-3 rounded-md border border-(--ui-border) p-3 text-sm hover:bg-(--ui-bg-elevated)"
            >
              <span class="flex size-8 shrink-0 items-center justify-center rounded-full bg-warning/10 text-warning">
                <UIcon
                  name="i-lucide-banknote"
                  class="size-4"
                />
              </span>
              <span class="flex-1">{{ t('dashboard.staleRates', { sources: staleRates.map(s => t(`rates.sources.${s}`)).join(', ') }) }}</span>
              <UIcon
                name="i-lucide-chevron-right"
                class="size-4 text-(--ui-text-muted)"
              />
            </NuxtLink>
          </li>
        </ul>
      </UCard>

      <!-- Metrics -->
      <section class="space-y-4">
        <div class="flex flex-wrap items-center justify-between gap-2 border-t border-(--ui-border) pt-6">
          <h2 class="text-lg font-semibold">
            {{ t('dashboard.metrics.title') }}
          </h2>
          <div class="flex flex-wrap items-center gap-2">
            <DateRangePicker
              v-model:preset="metricPreset"
              v-model:range="metricRange"
              :presets="metricPresets"
            />
            <USelect
              v-model="area"
              :items="areaItems"
              class="w-44"
              :aria-label="t('dashboard.metrics.city')"
            />
          </div>
        </div>

        <UAlert
          v-if="metricsError"
          color="error"
          variant="subtle"
          icon="i-lucide-circle-alert"
          :title="apiError(metricsError)"
        />
        <div
          v-if="metricsStatus === 'pending' && !metrics"
          class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"
        >
          <USkeleton
            v-for="n in 8"
            :key="n"
            class="h-20"
          />
        </div>

        <template v-if="metrics">
          <div
            class="grid gap-4 xl:grid-cols-2"
            :class="{ 'opacity-60': metricsStatus === 'pending' }"
          >
            <UCard
              v-for="group in kpiGroups"
              :key="group.title"
            >
              <h3 class="mb-3 text-sm font-medium text-(--ui-text-muted)">
                {{ group.title }}
              </h3>
              <dl class="grid grid-cols-2 gap-4 sm:grid-cols-3">
                <div
                  v-for="kpi in group.items"
                  :key="kpi.label"
                >
                  <dt class="text-xs text-(--ui-text-muted)">
                    {{ kpi.label }}
                  </dt>
                  <dd class="text-xl font-semibold tabular-nums">
                    {{ kpi.value }}
                  </dd>
                  <dd
                    v-if="kpi.hint"
                    class="text-xs text-(--ui-text-muted)"
                  >
                    {{ kpi.hint }}
                  </dd>
                </div>
              </dl>
            </UCard>
          </div>

          <div class="grid gap-4 xl:grid-cols-2">
            <UCard>
              <template #header>
                <h3 class="font-semibold">
                  {{ t('dashboard.metrics.ridesByDay') }}
                </h3>
              </template>
              <SimpleChart
                :title="t('dashboard.metrics.ridesByDay')"
                :labels="dayLabels"
                :ticks="dayTicks"
                :series="ridesByDay"
                :format="intFormat"
                :axis-format="compact"
              />
            </UCard>
            <UCard>
              <template #header>
                <h3 class="font-semibold">
                  {{ t('dashboard.metrics.gmvByDay') }}
                </h3>
              </template>
              <SimpleChart
                :title="t('dashboard.metrics.gmvByDay')"
                :labels="dayLabels"
                :ticks="dayTicks"
                :series="gmvByDay"
                :kind="metricDays.length > 1 ? 'line' : 'bar'"
                :format="money"
                :axis-format="compact"
              />
            </UCard>
            <UCard>
              <template #header>
                <div class="flex flex-wrap items-baseline justify-between gap-2">
                  <h3 class="font-semibold">
                    {{ t('dashboard.metrics.ridesByHour') }}
                  </h3>
                  <span
                    v-if="peakHour !== null"
                    class="text-xs text-(--ui-text-muted)"
                  >{{ t('dashboard.metrics.peakHour', { hour: hourLabels[peakHour] }) }}</span>
                </div>
              </template>
              <SimpleChart
                :title="t('dashboard.metrics.ridesByHour')"
                :labels="hourLabels"
                :ticks="hourTicks"
                :series="ridesByHour"
                :format="intFormat"
                :axis-format="compact"
              />
            </UCard>
            <UCard>
              <template #header>
                <h3 class="font-semibold">
                  {{ t('dashboard.metrics.topDrivers') }}
                </h3>
              </template>
              <p
                v-if="!metrics.top_drivers.length"
                class="text-sm text-(--ui-text-muted)"
              >
                {{ t('common.empty') }}
              </p>
              <div
                v-else
                class="overflow-x-auto"
              >
                <table class="w-full text-left text-sm">
                  <thead class="text-(--ui-text-muted)">
                    <tr>
                      <th class="py-2 pr-2 font-medium">
                        #
                      </th>
                      <th class="py-2 pr-4 font-medium">
                        {{ t('rides.driver') }}
                      </th>
                      <th class="py-2 pr-4 text-right font-medium">
                        {{ t('dashboard.metrics.rides') }}
                      </th>
                      <th class="py-2 pr-4 text-right font-medium">
                        {{ t('dashboard.metrics.earnings') }}
                      </th>
                      <th class="py-2 text-right font-medium">
                        {{ t('drivers.rating') }}
                      </th>
                    </tr>
                  </thead>
                  <tbody class="divide-y divide-(--ui-border)">
                    <tr
                      v-for="(driver, index) in metrics.top_drivers"
                      :key="driver.user_id"
                    >
                      <td class="py-2 pr-2 text-(--ui-text-muted) tabular-nums">
                        {{ index + 1 }}
                      </td>
                      <td class="py-2 pr-4">
                        <NuxtLink
                          :to="`/users/${driver.user_id}`"
                          class="text-primary hover:underline"
                        >
                          {{ driver.name || driver.user_id.slice(0, 8) }}
                        </NuxtLink>
                      </td>
                      <td class="py-2 pr-4 text-right tabular-nums">
                        {{ num(driver.rides) }}
                      </td>
                      <td class="py-2 pr-4 text-right tabular-nums">
                        {{ money(driver.earnings) }}
                      </td>
                      <td class="py-2 text-right tabular-nums">
                        {{ formatRating(driver.rating_avg) ?? '—' }}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </UCard>
          </div>
        </template>
      </section>

      <!-- Users -->
      <section class="space-y-4 border-t border-(--ui-border) pt-6">
        <h2 class="text-lg font-semibold">
          {{ t('dashboard.usersTitle') }}
        </h2>
        <div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <UCard
            v-for="card in userCards"
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
                  v-if="statsStatus === 'pending'"
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
      </section>
    </template>
  </UDashboardPanel>
</template>
