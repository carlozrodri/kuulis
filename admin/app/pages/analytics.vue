<script setup lang="ts">
import type {
  AppConfig,
  DriverEconomics,
  Funnels,
  FunnelStep,
  PromotionAnalytics,
  Retention,
  RetentionTable,
  SupplyCell,
  SupplyDemand,
} from '~/types/api'
import type { AnalyticsTab, SupplyMetric } from '~/utils/analytics'
import { ANALYTICS_REPORT, ANALYTICS_TABS, RETENTION_WEEKS } from '~/utils/analytics'
import type { DayRange, RangePreset } from '~/utils/dates'

/**
 * Product analytics (doc 19): funnels, weekly retention, supply and demand by ~1 km cell and hour, promotions
 * and the drivers' economics. Aggregated numbers only; the CSV of each tab has no person in it.
 */
definePageMeta({ permission: 'analytics.view' })

const { t, locale } = useI18n()
const { request, download } = useApi()
const { can } = useAuth()
const route = useRoute()
const router = useRouter()
const toast = useToast()
const apiError = useApiError()

const tab = ref<AnalyticsTab>(ANALYTICS_TABS.includes(route.query.tab as AnalyticsTab) ? route.query.tab as AnalyticsTab : 'funnels')
watch(tab, value => router.replace({ query: { ...route.query, tab: value } }))
const tabs = computed(() => ANALYTICS_TABS.map(value => ({ label: t(`analytics.tabs.${value}`), value })))

const presets: Exclude<RangePreset, 'custom'>[] = ['last30', 'last7', 'thisMonth', 'lastMonth']
const preset = ref<RangePreset>('last30')
const range = ref<DayRange>(presetRange('last30'))

const thisMonth = caracasMonth()
const month = ref<string>(thisMonth)
const monthItems = computed(() => monthsBack(thisMonth, 13).map(m => ({ label: formatMonth(m, locale.value), value: m })))

const area = ref<string>('all')
const { data: config } = await useAsyncData('analytics-config', () => request<AppConfig>('/admin/config').catch(() => null))
const areaItems = computed(() => [
  { label: t('dashboard.metrics.allCities'), value: 'all' },
  ...(config.value?.service_areas ?? []).map(a => ({ label: a.name, value: a.name })),
])
const areaQuery = computed(() => (area.value !== 'all' ? { area: area.value } : {}))
const rangeQuery = computed(() => ({ from: range.value.from, to: range.value.to, ...areaQuery.value }))

const int = (value: number | null | undefined) => formatNumber(value, locale.value)
const pct = (rate: number | null | undefined) => formatPercent(rate, locale.value)
const usdt = (value: string | number | null | undefined) => formatUsdt(value, locale.value)

// ---- Data per tab (loaded when the tab opens) ------------------------------------------------------

const lazy = { immediate: false } as const
const funnels = useAsyncData('analytics-funnels', () => request<Funnels>('/admin/analytics/funnels', { query: rangeQuery.value }), lazy)
const retention = useAsyncData('analytics-retention', () => request<Retention>('/admin/analytics/retention', { query: rangeQuery.value }), lazy)
const hour = ref<number | 'all'>('all')
const supplyQuery = computed(() => ({ ...rangeQuery.value, ...(hour.value !== 'all' ? { hour: String(hour.value) } : {}) }))
const supply = useAsyncData('analytics-supply', () => request<SupplyDemand>('/admin/analytics/supply-demand', { query: supplyQuery.value }), lazy)
const promotions = useAsyncData(
  'analytics-promotions',
  () => request<PromotionAnalytics[]>('/admin/analytics/promotions', { query: { from: range.value.from, to: range.value.to } }),
  lazy,
)
const drivers = useAsyncData(
  'analytics-drivers',
  () => request<DriverEconomics>('/admin/analytics/drivers', { query: { month: month.value, ...areaQuery.value } }),
  lazy,
)

const loaders: Record<AnalyticsTab, { execute: () => Promise<void> }> = {
  funnels,
  retention,
  supply,
  promotions,
  drivers,
}
function load() {
  void loaders[tab.value].execute()
}
watch([tab, range, area, month, hour], load)
onMounted(load)

const current = computed(() => loaders[tab.value] as unknown as { status: Ref<string>, error: Ref<unknown> })
const loading = computed(() => current.value.status.value === 'pending')
const loadError = computed(() => current.value.error.value)

// ---- Funnels -----------------------------------------------------------------------------------

const funnelGroups = computed(() => {
  const data = funnels.data.value
  if (!data) return []
  const groups: { key: string, steps: FunnelStep[] }[] = [
    { key: 'passenger', steps: data.passenger },
    { key: 'driver', steps: data.driver },
    { key: 'rides', steps: data.rides },
    { key: 'screens', steps: data.onboarding_screens },
  ]
  return groups.map(g => ({ ...g, rows: funnelRows(g.steps), drop: biggestDrop(funnelRows(g.steps)) }))
})
const computedAt = computed(() => funnels.data.value?.computed_at ?? retention.data.value?.computed_at ?? null)

const refreshing = ref(false)
async function refresh() {
  refreshing.value = true
  try {
    await request('/admin/analytics/refresh', { method: 'POST' })
    toast.add({ title: t('analytics.refreshQueued'), color: 'success' })
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    refreshing.value = false
  }
}

// ---- Retention ---------------------------------------------------------------------------------

const retentionTables = computed(() => {
  const data = retention.data.value
  if (!data) return []
  return ([['passenger', data.passenger], ['driver', data.driver]] as [string, RetentionTable][]).map(([key, table]) => ({ key, table }))
})

// ---- Supply and demand ------------------------------------------------------------------------

const metric = ref<SupplyMetric>('no_drivers')
const metricItems = computed(() => (['no_drivers', 'requests', 'quotes', 'driver_hours'] as const).map(value => ({ label: t(`analytics.supply.metrics.${value}`), value })))
const hourItems = computed(() => [
  { label: t('analytics.supply.allHours'), value: 'all' as const },
  ...Array.from({ length: 24 }, (_, h) => ({ label: `${String(h).padStart(2, '0')}:00`, value: h })),
])
const cellLabel = (c: SupplyCell) => t('analytics.supply.cellTooltip', {
  requests: int(c.requests),
  noDrivers: int(c.no_drivers),
  quotes: int(c.quotes),
  hours: formatNumber(c.driver_hours, locale.value, 1),
})
const rectangles = computed(() => heatRectangles(supply.data.value?.cells ?? [], metric.value, cellLabel))
const hourLabels = Array.from({ length: 24 }, (_, h) => `${String(h).padStart(2, '0')}:00`)
const hourTicks = Array.from({ length: 24 }, (_, h) => (h % 3 === 0 ? String(h) : ''))
const demandSeries = computed(() => {
  const hours = supply.data.value?.hours ?? []
  return [
    { key: 'requests', label: t('analytics.supply.metrics.requests'), values: hours.map(h => h.requests), color: 'var(--chart-1)' },
    { key: 'no_drivers', label: t('analytics.supply.metrics.no_drivers'), values: hours.map(h => h.no_drivers), color: 'var(--chart-2)' },
    { key: 'quotes', label: t('analytics.supply.metrics.quotes'), values: hours.map(h => h.quotes), color: 'var(--chart-3)' },
  ]
})
const supplySeries = computed(() => [{
  key: 'driver_hours',
  label: t('analytics.supply.metrics.driver_hours'),
  values: (supply.data.value?.hours ?? []).map(h => h.driver_hours),
  color: 'var(--chart-2)',
}])
/** Counts on the y-axis (small numbers would repeat "1" with no decimals). */
const axisCount = (v: number) => formatNumber(v, locale.value, 2)
const topCells = computed(() => (supply.data.value?.cells ?? []).slice(0, 10))

// ---- Drivers -----------------------------------------------------------------------------------

const usd = (n: number) => `$${n}`
const earningsSeries = computed(() => [{
  key: 'drivers',
  label: t('analytics.drivers.driversLabel'),
  values: (drivers.data.value?.earnings ?? []).map(b => b.count),
  color: 'var(--chart-1)',
}])
const earningsLabels = computed(() => (drivers.data.value?.earnings ?? []).map(b => bucketLabel(b, usd)))
const utilizationSeries = computed(() => [{
  key: 'drivers',
  label: t('analytics.drivers.driversLabel'),
  values: (drivers.data.value?.utilization_spread ?? []).map(b => b.count),
  color: 'var(--chart-2)',
}])
const utilizationLabels = computed(() => (drivers.data.value?.utilization_spread ?? []).map(b => bucketLabel(b, n => `${n}%`)))

// ---- CSV ---------------------------------------------------------------------------------------

const exporting = ref(false)
async function exportCsv() {
  const report = ANALYTICS_REPORT[tab.value]
  const query: Record<string, string | undefined> = tab.value === 'drivers'
    ? { month: month.value, ...areaQuery.value }
    : tab.value === 'supply'
      ? supplyQuery.value
      : tab.value === 'promotions'
        ? { from: range.value.from, to: range.value.to }
        : rangeQuery.value
  const stamp = tab.value === 'drivers' ? month.value : `${range.value.from}_${range.value.to}`
  exporting.value = true
  try {
    await download(`/admin/analytics/${report}.csv`, `kuulis-analitica-${report}-${stamp}.csv`, query)
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    exporting.value = false
  }
}
</script>

<template>
  <UDashboardPanel id="analytics">
    <template #header>
      <UDashboardNavbar :title="t('nav.analytics')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton
            v-if="can('analytics.export')"
            icon="i-lucide-download"
            color="neutral"
            variant="outline"
            :loading="exporting"
            :label="t('analytics.export')"
            @click="exportCsv"
          />
        </template>
      </UDashboardNavbar>
      <UDashboardToolbar>
        <template #left>
          <UTabs
            v-model="tab"
            :items="tabs"
            :content="false"
            size="sm"
            variant="link"
          />
        </template>
        <template #right>
          <USelect
            v-if="tab === 'drivers'"
            v-model="month"
            :items="monthItems"
            class="w-44"
            :aria-label="t('analytics.month')"
          />
          <DateRangePicker
            v-else
            v-model:preset="preset"
            v-model:range="range"
            :presets="presets"
          />
          <USelect
            v-if="tab !== 'promotions'"
            v-model="area"
            :items="areaItems"
            class="w-40"
            :aria-label="t('analytics.city')"
          />
        </template>
      </UDashboardToolbar>
    </template>

    <template #body>
      <UAlert
        v-if="loadError"
        color="error"
        variant="subtle"
        icon="i-lucide-circle-alert"
        :title="apiError(loadError)"
      />

      <!-- Funnels -->
      <template v-if="tab === 'funnels'">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <p class="max-w-3xl text-sm text-(--ui-text-muted)">
            {{ t('analytics.funnels.help') }}
          </p>
          <div class="flex items-center gap-2">
            <span
              v-if="computedAt"
              class="text-xs text-(--ui-text-muted)"
            >{{ t('analytics.computedAt', { date: formatDate(computedAt, locale) }) }}</span>
            <UButton
              icon="i-lucide-refresh-cw"
              size="sm"
              color="neutral"
              variant="ghost"
              :loading="refreshing"
              :label="t('analytics.refresh')"
              @click="refresh"
            />
          </div>
        </div>
        <USkeleton
          v-if="loading && !funnels.data.value"
          class="h-64"
        />
        <div
          v-else
          class="grid gap-4 lg:grid-cols-2"
          :class="{ 'opacity-60': loading }"
        >
          <UCard
            v-for="group in funnelGroups"
            :key="group.key"
          >
            <template #header>
              <p class="font-medium">
                {{ t(`analytics.funnels.groups.${group.key}.title`) }}
              </p>
              <p class="text-xs text-(--ui-text-muted)">
                {{ t(`analytics.funnels.groups.${group.key}.help`) }}
              </p>
            </template>
            <ul class="space-y-3">
              <li
                v-for="row in group.rows"
                :key="row.step"
              >
                <div class="flex items-baseline justify-between gap-2 text-sm">
                  <span>{{ t(`analytics.funnels.steps.${row.step}`) }}</span>
                  <span class="tabular-nums">
                    <span class="font-medium">{{ int(row.users) }}</span>
                    <span
                      v-if="row.ofPrevious !== null"
                      class="ml-2 text-xs text-(--ui-text-muted)"
                    >{{ t('analytics.funnels.ofPrevious', { pct: pct(row.ofPrevious) }) }}</span>
                  </span>
                </div>
                <div class="mt-1 h-2 rounded-full bg-(--ui-bg-elevated)">
                  <div
                    class="h-2 rounded-full bg-primary"
                    :style="{ width: `${Math.round((row.ofFirst ?? 0) * 100)}%` }"
                  />
                </div>
              </li>
            </ul>
            <p
              v-if="group.drop"
              class="mt-3 text-xs text-warning"
            >
              {{ t('analytics.funnels.biggestDrop', { step: t(`analytics.funnels.steps.${group.drop.step}`), lost: int(group.drop.lost) }) }}
            </p>
          </UCard>
        </div>
      </template>

      <!-- Retention -->
      <template v-else-if="tab === 'retention'">
        <p class="max-w-3xl text-sm text-(--ui-text-muted)">
          {{ t('analytics.retention.help') }}
        </p>
        <USkeleton
          v-if="loading && !retention.data.value"
          class="h-64"
        />
        <div
          v-else
          class="grid gap-4 xl:grid-cols-2"
          :class="{ 'opacity-60': loading }"
        >
          <UCard
            v-for="{ key, table } in retentionTables"
            :key="key"
          >
            <template #header>
              <p class="font-medium">
                {{ t(`analytics.retention.${key}`) }}
              </p>
            </template>
            <div class="overflow-x-auto">
              <table class="w-full text-sm tabular-nums">
                <thead>
                  <tr class="text-left text-xs text-(--ui-text-muted)">
                    <th class="py-1 pr-2 font-medium">
                      {{ t('analytics.retention.cohort') }}
                    </th>
                    <th class="py-1 pr-2 text-right font-medium">
                      {{ t('analytics.retention.people') }}
                    </th>
                    <th
                      v-for="w in RETENTION_WEEKS"
                      :key="w"
                      class="py-1 pr-2 text-right font-medium"
                    >
                      {{ t('analytics.retention.week', { n: w }) }}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr class="border-t border-(--ui-border) font-medium">
                    <td class="py-1 pr-2">
                      {{ t('analytics.retention.average') }}
                    </td>
                    <td />
                    <td
                      v-for="w in RETENTION_WEEKS"
                      :key="w"
                      class="py-1 pr-2 text-right"
                    >
                      {{ table.average[w] === null || table.average[w] === undefined ? '—' : pct((table.average[w] ?? 0) / 100) }}
                    </td>
                  </tr>
                  <tr
                    v-for="row in table.rows"
                    :key="row.cohort"
                    class="border-t border-(--ui-border)"
                  >
                    <td class="py-1 pr-2">
                      {{ t('analytics.retention.weekOf', { date: formatDay(row.cohort, locale) }) }}
                    </td>
                    <td class="py-1 pr-2 text-right">
                      {{ int(row.users) }}
                    </td>
                    <td
                      v-for="w in RETENTION_WEEKS"
                      :key="w"
                      class="py-1 pr-2 text-right"
                      :style="{ background: rateShade(retentionRate(row.users, row.weeks[w])) }"
                    >
                      {{ pct(retentionRate(row.users, row.weeks[w])) }}
                    </td>
                  </tr>
                  <tr v-if="!table.rows.length">
                    <td
                      colspan="6"
                      class="py-4 text-center text-(--ui-text-muted)"
                    >
                      {{ t('analytics.empty') }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </UCard>
        </div>
      </template>

      <!-- Supply and demand -->
      <template v-else-if="tab === 'supply'">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <p class="max-w-3xl text-sm text-(--ui-text-muted)">
            {{ t('analytics.supply.help') }}
          </p>
          <div class="flex flex-wrap gap-2">
            <USelect
              v-model="metric"
              :items="metricItems"
              class="w-52"
              :aria-label="t('analytics.supply.metric')"
            />
            <USelect
              v-model="hour"
              :items="hourItems"
              class="w-36"
              :aria-label="t('analytics.supply.hour')"
            />
          </div>
        </div>
        <div
          class="grid gap-4 xl:grid-cols-3"
          :class="{ 'opacity-60': loading }"
        >
          <UCard
            class="xl:col-span-2"
            :ui="{ body: 'p-0 sm:p-0' }"
          >
            <ClientOnly>
              <div class="h-[28rem]">
                <MapView :rectangles="rectangles" />
              </div>
            </ClientOnly>
          </UCard>
          <UCard>
            <template #header>
              <p class="font-medium">
                {{ t('analytics.supply.topCells') }}
              </p>
            </template>
            <table class="w-full text-sm tabular-nums">
              <thead>
                <tr class="text-left text-xs text-(--ui-text-muted)">
                  <th class="py-1 font-medium">
                    {{ t('analytics.supply.cell') }}
                  </th>
                  <th class="py-1 text-right font-medium">
                    {{ t('analytics.supply.short.requests') }}
                  </th>
                  <th class="py-1 text-right font-medium">
                    {{ t('analytics.supply.short.no_drivers') }}
                  </th>
                  <th class="py-1 text-right font-medium">
                    {{ t('analytics.supply.short.driver_hours') }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="c in topCells"
                  :key="c.cell"
                  class="border-t border-(--ui-border)"
                >
                  <td class="py-1 font-mono text-xs">
                    {{ formatNumber(c.lat, locale, 3) }}, {{ formatNumber(c.lng, locale, 3) }}
                  </td>
                  <td class="py-1 text-right">
                    {{ int(c.requests) }}
                  </td>
                  <td
                    class="py-1 text-right"
                    :class="{ 'text-error font-medium': c.no_drivers > 0 }"
                  >
                    {{ int(c.no_drivers) }}
                  </td>
                  <td class="py-1 text-right">
                    {{ formatNumber(c.driver_hours, locale, 1) }}
                  </td>
                </tr>
                <tr v-if="!topCells.length">
                  <td
                    colspan="4"
                    class="py-4 text-center text-(--ui-text-muted)"
                  >
                    {{ t('analytics.empty') }}
                  </td>
                </tr>
              </tbody>
            </table>
          </UCard>
        </div>
        <div class="grid gap-4 xl:grid-cols-2">
          <UCard>
            <template #header>
              <p class="font-medium">
                {{ t('analytics.supply.demandByHour') }}
              </p>
            </template>
            <SimpleChart
              :labels="hourLabels"
              :ticks="hourTicks"
              :series="demandSeries"
              :title="t('analytics.supply.demandByHour')"
              :format="int"
              :axis-format="axisCount"
            />
          </UCard>
          <UCard>
            <template #header>
              <p class="font-medium">
                {{ t('analytics.supply.supplyByHour') }}
              </p>
            </template>
            <SimpleChart
              :labels="hourLabels"
              :ticks="hourTicks"
              :series="supplySeries"
              :title="t('analytics.supply.supplyByHour')"
              :format="(v: number) => formatNumber(v, locale, 1)"
            />
          </UCard>
        </div>
      </template>

      <!-- Promotions -->
      <template v-else-if="tab === 'promotions'">
        <p class="max-w-3xl text-sm text-(--ui-text-muted)">
          {{ t('analytics.promotions.help') }}
        </p>
        <UCard :class="{ 'opacity-60': loading }">
          <div class="overflow-x-auto">
            <table class="w-full text-sm tabular-nums">
              <thead>
                <tr class="text-left text-xs text-(--ui-text-muted)">
                  <th class="py-1 pr-3 font-medium">
                    {{ t('analytics.promotions.name') }}
                  </th>
                  <th
                    v-for="col in ['rides', 'cost', 'costPerRide', 'newPassengers', 'costPerNew', 'retention']"
                    :key="col"
                    class="py-1 pr-3 text-right font-medium"
                  >
                    {{ t(`analytics.promotions.${col}`) }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="p in promotions.data.value ?? []"
                  :key="p.id"
                  class="border-t border-(--ui-border)"
                >
                  <td class="py-1.5 pr-3">
                    <NuxtLink
                      :to="`/promotions/${p.id}`"
                      class="font-medium text-primary hover:underline"
                    >
                      {{ p.name }}
                    </NuxtLink>
                    <span
                      v-if="p.code"
                      class="ml-2 font-mono text-xs text-(--ui-text-muted)"
                    >{{ p.code }}</span>
                  </td>
                  <td class="py-1.5 pr-3 text-right">
                    {{ int(p.rides) }}
                  </td>
                  <td class="py-1.5 pr-3 text-right">
                    {{ usdt(p.cost) }}
                  </td>
                  <td class="py-1.5 pr-3 text-right">
                    {{ p.cost_per_ride === null ? '—' : usdt(p.cost_per_ride) }}
                  </td>
                  <td class="py-1.5 pr-3 text-right">
                    {{ int(p.new_passengers) }}
                  </td>
                  <td class="py-1.5 pr-3 text-right">
                    {{ p.cost_per_new_passenger === null ? '—' : usdt(p.cost_per_new_passenger) }}
                  </td>
                  <td class="py-1.5 pr-3 text-right">
                    <span>{{ p.eligible_30d ? pct(p.returned_30d / p.eligible_30d) : '—' }}</span>
                    <p class="text-xs text-(--ui-text-muted)">
                      {{ t('analytics.promotions.returned', { n: int(p.returned_30d), of: int(p.eligible_30d) }) }}
                    </p>
                  </td>
                </tr>
                <tr v-if="!(promotions.data.value ?? []).length">
                  <td
                    colspan="7"
                    class="py-4 text-center text-(--ui-text-muted)"
                  >
                    {{ loading ? t('analytics.loading') : t('analytics.empty') }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </UCard>
      </template>

      <!-- Drivers -->
      <template v-else>
        <p class="max-w-3xl text-sm text-(--ui-text-muted)">
          {{ t('analytics.drivers.help') }}
        </p>
        <USkeleton
          v-if="loading && !drivers.data.value"
          class="h-64"
        />
        <template v-else-if="drivers.data.value">
          <div
            class="grid gap-4 sm:grid-cols-3"
            :class="{ 'opacity-60': loading }"
          >
            <UCard>
              <p class="text-sm text-(--ui-text-muted)">
                {{ t('analytics.drivers.withRides') }}
              </p>
              <p class="text-2xl font-semibold tabular-nums">
                {{ int(drivers.data.value.drivers) }}
              </p>
              <p class="text-xs text-(--ui-text-muted)">
                {{ t('analytics.drivers.online', { n: int(drivers.data.value.online_drivers) }) }}
              </p>
            </UCard>
            <UCard>
              <p class="text-sm text-(--ui-text-muted)">
                {{ t('analytics.drivers.median') }}
              </p>
              <p class="text-2xl font-semibold tabular-nums">
                {{ drivers.data.value.median_earnings === null ? '—' : usdt(drivers.data.value.median_earnings) }}
              </p>
              <p class="text-xs text-(--ui-text-muted)">
                {{ t('analytics.drivers.total', { amount: usdt(drivers.data.value.total_earnings) }) }}
              </p>
            </UCard>
            <UCard>
              <p class="text-sm text-(--ui-text-muted)">
                {{ t('analytics.drivers.utilization') }}
              </p>
              <p class="text-2xl font-semibold tabular-nums">
                {{ drivers.data.value.utilization === null ? '—' : pct(drivers.data.value.utilization / 100) }}
              </p>
              <p class="text-xs text-(--ui-text-muted)">
                {{ t('analytics.drivers.hours', { ride: formatNumber(drivers.data.value.ride_hours, locale, 1), online: formatNumber(drivers.data.value.online_hours, locale, 1) }) }}
              </p>
            </UCard>
          </div>
          <div class="grid gap-4 xl:grid-cols-3">
            <UCard>
              <template #header>
                <p class="font-medium">
                  {{ t('analytics.drivers.tiers') }}
                </p>
                <p class="text-xs text-(--ui-text-muted)">
                  {{ t('analytics.drivers.tiersHelp') }}
                </p>
              </template>
              <table class="w-full text-sm tabular-nums">
                <thead>
                  <tr class="text-left text-xs text-(--ui-text-muted)">
                    <th class="py-1 font-medium">
                      {{ t('analytics.drivers.earnedAbove') }}
                    </th>
                    <th class="py-1 text-right font-medium">
                      {{ t('analytics.drivers.fee') }}
                    </th>
                    <th class="py-1 text-right font-medium">
                      {{ t('analytics.drivers.driversLabel') }}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="tier in drivers.data.value.tiers"
                    :key="tier.above"
                    class="border-t border-(--ui-border)"
                  >
                    <td class="py-1">
                      {{ usdt(tier.above) }}
                    </td>
                    <td class="py-1 text-right">
                      {{ usdt(tier.fee) }}
                    </td>
                    <td class="py-1 text-right font-medium">
                      {{ int(tier.drivers) }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </UCard>
            <UCard>
              <template #header>
                <p class="font-medium">
                  {{ t('analytics.drivers.earnings') }}
                </p>
              </template>
              <SimpleChart
                :labels="earningsLabels"
                :series="earningsSeries"
                :title="t('analytics.drivers.earnings')"
                :format="int"
                :axis-format="axisCount"
              />
            </UCard>
            <UCard>
              <template #header>
                <p class="font-medium">
                  {{ t('analytics.drivers.utilizationSpread') }}
                </p>
              </template>
              <SimpleChart
                :labels="utilizationLabels"
                :series="utilizationSeries"
                :title="t('analytics.drivers.utilizationSpread')"
                :format="int"
                :axis-format="axisCount"
              />
            </UCard>
          </div>
        </template>
      </template>
    </template>
  </UDashboardPanel>
</template>
