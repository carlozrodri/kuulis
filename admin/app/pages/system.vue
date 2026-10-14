<script setup lang="ts">
import type { HealthStatus, SystemHealth } from '~/types/api'

definePageMeta({ permission: 'system.view' })

const { t, locale } = useI18n()
const { request } = useApi()
const apiError = useApiError()
const auth = useAuth()

const { data: health, status, error, refresh } = await useAsyncData(
  'system-health',
  () => request<SystemHealth>('/admin/system/health'),
)

let timer: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  timer = setInterval(() => {
    if (document.visibilityState === 'visible') refresh()
  }, 30_000)
})
onBeforeUnmount(() => clearInterval(timer))

const statusColor: Record<HealthStatus, 'success' | 'warning' | 'error' | 'neutral'> = {
  ok: 'success',
  warning: 'warning',
  down: 'error',
  off: 'neutral',
}

const label = (group: 'serviceNames' | 'loopNames', name: string) => {
  const key = `system.${group}.${name}`
  return t(key) === key ? name : t(key)
}

const backupRows = computed(() => {
  const b = health.value?.backups
  if (!b?.configured) return []
  const when = (value?: string | null) => (value ? formatDate(value, locale.value) : t('system.backups.never'))
  return [
    { label: t('system.backups.database'), value: when(b.last_backup_at), detail: b.last_backup_bytes ? `${formatNumber(b.last_backup_bytes / 1048576, locale.value, 1)} MB` : '', bad: Boolean(b.errors.database) },
    { label: t('system.backups.ledger'), value: when(b.last_ledger_at), detail: '', bad: Boolean(b.errors.ledger) },
    { label: t('system.backups.files'), value: when(b.last_files_mirror_at), detail: '', bad: Boolean(b.errors.files) },
    {
      label: t('system.backups.restore'),
      value: when(b.last_restore_check_at),
      detail: b.last_restore_ok === null || b.last_restore_ok === undefined ? '' : t(b.last_restore_ok ? 'system.backups.restoreOk' : 'system.backups.restoreFailed'),
      bad: b.last_restore_ok === false,
    },
  ]
})

const numbers = computed(() => {
  const h = health.value
  if (!h) return []
  return [
    {
      title: t('system.queues'),
      rows: [
        { label: t('system.tasksPending'), value: h.queues.taskiq_pending === null ? '—' : formatNumber(h.queues.taskiq_pending, locale.value) },
        { label: t('system.dispatchDue'), value: formatNumber(h.queues.dispatch_due, locale.value) },
        { label: t('system.dispatchOverdue'), value: formatNumber(h.queues.dispatch_overdue, locale.value), bad: h.queues.dispatch_overdue > 0 },
      ],
    },
    {
      title: t('system.traffic'),
      rows: [
        { label: t('system.requests'), value: formatNumber(h.traffic.requests_5m, locale.value) },
        { label: t('system.errors'), value: `${formatNumber(h.traffic.errors_5m, locale.value)} (${formatPercent(h.traffic.error_rate_5m, locale.value)})`, bad: h.traffic.error_rate_5m > 0.02 },
        { label: t('system.avgLatency'), value: `${formatNumber(h.traffic.avg_ms_5m, locale.value, 1)} ms` },
      ],
    },
    {
      title: t('system.rides'),
      rows: [
        { label: t('system.searching'), value: formatNumber(h.rides.searching, locale.value) },
        { label: t('system.requestedLastHour'), value: formatNumber(h.rides.requested_last_hour, locale.value) },
        { label: t('system.noDriversLastHour'), value: formatNumber(h.rides.no_drivers_last_hour, locale.value) },
        { label: t('system.disk'), value: h.disk_used_percent === null ? '—' : `${formatNumber(h.disk_used_percent, locale.value, 1)} %`, bad: (h.disk_used_percent ?? 0) > 85 },
      ],
    },
  ]
})
</script>

<template>
  <UDashboardPanel id="system">
    <template #header>
      <UDashboardNavbar :title="t('system.title')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <span
            v-if="health"
            class="hidden text-sm text-(--ui-text-muted) sm:inline"
          >
            {{ t('system.checkedAt', { time: formatDate(health.checked_at, locale) }) }}
          </span>
          <UButton
            icon="i-lucide-refresh-cw"
            color="neutral"
            variant="outline"
            :label="t('system.refresh')"
            :loading="status === 'pending'"
            @click="refresh()"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <UAlert
        v-if="error && !health"
        color="error"
        variant="subtle"
        icon="i-lucide-circle-alert"
        :title="apiError(error)"
      />
      <USkeleton
        v-if="status === 'pending' && !health"
        class="h-64"
      />

      <template v-if="health">
        <UCard>
          <template #header>
            <div class="flex items-center justify-between gap-2">
              <h2 class="font-semibold">
                {{ t('system.alerts') }}
              </h2>
              <span class="text-xs text-(--ui-text-muted)">
                {{ t('system.version', { commit: health.commit ?? '—', env: health.env }) }} · {{ t('system.autoRefresh') }}
              </span>
            </div>
          </template>
          <p
            v-if="!health.alerts.length"
            class="text-sm text-(--ui-text-muted)"
          >
            {{ t('system.noAlerts') }}
          </p>
          <ul
            v-else
            class="space-y-2"
          >
            <li
              v-for="alert in health.alerts"
              :key="alert.key"
              class="flex flex-wrap items-center gap-2 text-sm"
            >
              <UIcon
                name="i-lucide-circle-alert"
                class="size-4 text-(--ui-error)"
              />
              <span class="font-medium">{{ alert.message }}</span>
              <span class="text-(--ui-text-muted)">{{ t('system.since', { time: formatDate(alert.since, locale) }) }}</span>
            </li>
          </ul>
        </UCard>

        <div class="grid gap-6 lg:grid-cols-2">
          <UCard>
            <template #header>
              <h2 class="font-semibold">
                {{ t('system.services') }}
              </h2>
            </template>
            <ul class="divide-y divide-(--ui-border)">
              <li
                v-for="service in health.services"
                :key="service.name"
                class="flex items-center justify-between gap-2 py-2 text-sm"
              >
                <span>{{ label('serviceNames', service.name) }}</span>
                <span class="flex items-center gap-2">
                  <span
                    v-if="service.latency_ms !== null"
                    class="tabular-nums text-(--ui-text-muted)"
                  >{{ formatNumber(service.latency_ms, locale, 1) }} ms</span>
                  <UBadge
                    :color="statusColor[service.status]"
                    variant="subtle"
                    size="sm"
                  >
                    {{ t(`system.statuses.${service.status}`) }}
                  </UBadge>
                </span>
              </li>
            </ul>
          </UCard>

          <UCard>
            <template #header>
              <h2 class="font-semibold">
                {{ t('system.loops') }}
              </h2>
            </template>
            <ul class="divide-y divide-(--ui-border)">
              <li
                v-for="loop in health.loops"
                :key="loop.name"
                class="flex items-center justify-between gap-2 py-2 text-sm"
              >
                <span>
                  {{ label('loopNames', loop.name) }}
                  <span class="block text-xs text-(--ui-text-muted)">
                    {{ loop.last_beat_at ? t('system.lastBeat', { time: formatDate(loop.last_beat_at, locale) }) : t('system.neverBeat') }}
                    · {{ t('system.maxAge', { minutes: Math.round(loop.max_age_seconds / 60) }) }}
                  </span>
                </span>
                <UBadge
                  :color="statusColor[loop.status]"
                  variant="subtle"
                  size="sm"
                >
                  {{ t(`system.statuses.${loop.status}`) }}
                </UBadge>
              </li>
            </ul>
          </UCard>
        </div>

        <UCard>
          <template #header>
            <h2 class="font-semibold">
              {{ t('system.backups.title') }}
            </h2>
          </template>
          <p
            v-if="!health.backups.configured"
            class="text-sm text-(--ui-text-muted)"
          >
            {{ t('system.backups.notConfigured') }}
          </p>
          <dl
            v-else
            class="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4"
          >
            <div
              v-for="row in backupRows"
              :key="row.label"
            >
              <dt class="text-(--ui-text-muted)">
                {{ row.label }}
              </dt>
              <dd :class="row.bad ? 'font-semibold text-(--ui-error)' : ''">
                {{ row.value }}
                <span
                  v-if="row.detail"
                  class="block text-xs text-(--ui-text-muted)"
                >{{ row.detail }}</span>
              </dd>
            </div>
          </dl>
          <ul
            v-if="Object.keys(health.backups.errors).length"
            class="mt-3 space-y-1 text-xs text-(--ui-error)"
          >
            <li
              v-for="(message, job) in health.backups.errors"
              :key="job"
            >
              {{ job }}: {{ message }}
            </li>
          </ul>
        </UCard>

        <!-- Doc 17: daily wallet ledger invariants -->
        <UCard>
          <template #header>
            <div class="flex flex-wrap items-center justify-between gap-2">
              <div class="flex items-center gap-2">
                <h2 class="font-semibold">
                  {{ t('system.ledger.title') }}
                </h2>
                <UBadge
                  v-if="health.ledger"
                  :color="health.ledger.ok ? 'success' : 'error'"
                  variant="subtle"
                  size="sm"
                >
                  {{ t(health.ledger.ok ? 'system.ledger.ok' : 'system.ledger.issues') }}
                </UBadge>
              </div>
              <UButton
                v-if="auth.can('finance.view')"
                to="/closings"
                size="xs"
                color="neutral"
                variant="ghost"
                trailing-icon="i-lucide-arrow-right"
                :label="t('system.ledger.open')"
              />
            </div>
          </template>
          <p
            v-if="!health.ledger"
            class="text-sm text-(--ui-text-muted)"
          >
            {{ t('system.ledger.never') }}
          </p>
          <div
            v-else
            class="space-y-1 text-sm"
          >
            <p class="text-(--ui-text-muted)">
              {{ t('system.ledger.checkedAt', { time: formatDate(health.ledger.checked_at, locale) }) }}
              · {{ t('system.ledger.wallets', { n: formatNumber(health.ledger.wallets, locale) }) }}
            </p>
            <p
              v-if="!health.ledger.ok"
              class="font-semibold text-(--ui-error)"
            >
              {{ t('system.ledger.issueCount', { n: health.ledger.issues }) }}
              <span
                v-if="health.ledger.first_issue"
                class="block font-normal"
              >
                {{ t('system.ledger.firstIssue', { issue: t(`closings.invariants.kinds.${health.ledger.first_issue.kind}`, health.ledger.first_issue.kind) }) }}
              </span>
            </p>
            <p
              v-else
              class="text-(--ui-text-muted)"
            >
              {{ t('system.ledger.help') }}
            </p>
          </div>
        </UCard>

        <div class="grid gap-6 lg:grid-cols-3">
          <UCard
            v-for="block in numbers"
            :key="block.title"
          >
            <template #header>
              <h2 class="font-semibold">
                {{ block.title }}
              </h2>
            </template>
            <dl class="space-y-2 text-sm">
              <div
                v-for="row in block.rows"
                :key="row.label"
                class="flex justify-between gap-2"
              >
                <dt class="text-(--ui-text-muted)">
                  {{ row.label }}
                </dt>
                <dd
                  class="tabular-nums"
                  :class="row.bad ? 'font-semibold text-(--ui-error)' : ''"
                >
                  {{ row.value }}
                </dd>
              </div>
            </dl>
          </UCard>
        </div>
      </template>
    </template>
  </UDashboardPanel>
</template>
