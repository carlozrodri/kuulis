<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { SupportAgentMetrics, SupportMetrics } from '~/types/api'

definePageMeta({ permission: 'reports.manage' })

const { t, locale } = useI18n()
const { request } = useApi()
const apiError = useApiError()

const PERIODS = [7, 30, 90] as const
const days = ref<number>(30)
const periodItems = computed(() => PERIODS.map(value => ({ label: t('supportMetrics.lastDays', { n: value }), value: value as number })))

const { data: metrics, status, error } = await useAsyncData(
  'support-metrics',
  () => request<SupportMetrics>('/admin/support/metrics', { query: { days: days.value } }),
  { watch: [days] },
)

// Every day of the period (days without tickets come as zeros or not at all).
const periodDays = computed(() => {
  const today = caracasToday()
  return listDays(addDays(today, -(days.value - 1)), today)
})
const byDay = computed(() => new Map((metrics.value?.days ?? []).map(d => [d.date, d])))
const dayLabels = computed(() => periodDays.value.map(day => formatDay(day, locale.value)))
const dayTicks = computed(() => periodDays.value.map(day => formatShortDay(day, locale.value)))
const ticketsByDay = computed(() => [
  { key: 'created', label: t('supportMetrics.created'), values: periodDays.value.map(d => byDay.value.get(d)?.created ?? 0), color: 'var(--chart-1)' },
  { key: 'resolved', label: t('supportMetrics.resolved'), values: periodDays.value.map(d => byDay.value.get(d)?.resolved ?? 0), color: 'var(--chart-3)' },
])
const intFormat = (value: number) => formatNumber(value, locale.value)
const totals = computed(() => ({
  created: (metrics.value?.days ?? []).reduce((sum, d) => sum + d.created, 0),
  resolved: (metrics.value?.days ?? []).reduce((sum, d) => sum + d.resolved, 0),
}))

const csatLabel = (value: number | null | undefined) => (value === null || value === undefined ? '—' : `${formatNumber(value, locale.value, 1)} / 5`)

const kpis = computed(() => {
  const m = metrics.value
  if (!m) return []
  return [
    { label: t('supportMetrics.created'), value: intFormat(totals.value.created), hint: t('supportMetrics.resolvedHint', { n: intFormat(totals.value.resolved) }) },
    { label: t('supportMetrics.firstResponse'), value: formatMinutesSpan(m.first_response_minutes_avg), hint: t('supportMetrics.average') },
    { label: t('supportMetrics.resolution'), value: formatMinutesSpan(m.resolution_hours_avg === null ? null : m.resolution_hours_avg * 60), hint: t('supportMetrics.average') },
    { label: t('supportMetrics.csat'), value: csatLabel(m.csat_avg), hint: t('supportMetrics.csatCount', { n: m.csat_count }) },
    { label: t('supportMetrics.waitingStaff'), value: intFormat(m.waiting_staff), hint: t('supportMetrics.now') },
    { label: t('supportMetrics.overdueOpen'), value: intFormat(m.overdue_open), hint: t('supportMetrics.now'), danger: m.overdue_open > 0 },
  ]
})

const agentColumns = computed<TableColumn<SupportAgentMetrics>[]>(() => [
  { id: 'agent', header: t('supportMetrics.agent') },
  { accessorKey: 'resolved', header: t('supportMetrics.resolved') },
  { accessorKey: 'first_response_minutes_avg', header: t('supportMetrics.firstResponse') },
  { accessorKey: 'csat_avg', header: t('supportMetrics.csat') },
])
</script>

<template>
  <UDashboardPanel id="support-metrics">
    <template #header>
      <UDashboardNavbar :title="t('nav.supportMetrics')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <USelect
            v-model="days"
            :items="periodItems"
            class="w-44"
            :aria-label="t('supportMetrics.period')"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <UAlert
        v-if="error"
        color="error"
        variant="subtle"
        icon="i-lucide-circle-alert"
        :title="apiError(error)"
      />
      <USkeleton
        v-else-if="status === 'pending' && !metrics"
        class="h-64"
      />

      <template v-if="metrics">
        <UCard :class="{ 'opacity-60': status === 'pending' }">
          <dl class="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-6">
            <div
              v-for="kpi in kpis"
              :key="kpi.label"
            >
              <dt class="text-xs text-(--ui-text-muted)">
                {{ kpi.label }}
              </dt>
              <dd
                class="text-xl font-semibold tabular-nums"
                :class="kpi.danger ? 'text-error' : ''"
              >
                {{ kpi.value }}
              </dd>
              <dd class="text-xs text-(--ui-text-muted)">
                {{ kpi.hint }}
              </dd>
            </div>
          </dl>
        </UCard>

        <UCard>
          <template #header>
            <h3 class="font-semibold">
              {{ t('supportMetrics.ticketsByDay') }}
            </h3>
          </template>
          <SimpleChart
            :title="t('supportMetrics.ticketsByDay')"
            :labels="dayLabels"
            :ticks="dayTicks"
            :series="ticketsByDay"
            :format="intFormat"
          />
        </UCard>

        <UCard>
          <template #header>
            <h3 class="font-semibold">
              {{ t('supportMetrics.byAgent') }}
            </h3>
          </template>
          <UTable
            :data="metrics.by_agent"
            :columns="agentColumns"
            :empty="t('supportMetrics.noAgents')"
          >
            <template #agent-cell="{ row }">
              <span class="font-medium">{{ row.original.user.name || row.original.user.email || '—' }}</span>
            </template>
            <template #resolved-cell="{ row }">
              {{ intFormat(row.original.resolved) }}
            </template>
            <template #first_response_minutes_avg-cell="{ row }">
              {{ formatMinutesSpan(row.original.first_response_minutes_avg) }}
            </template>
            <template #csat_avg-cell="{ row }">
              {{ csatLabel(row.original.csat_avg) }}
            </template>
          </UTable>
        </UCard>
      </template>
    </template>
  </UDashboardPanel>
</template>
