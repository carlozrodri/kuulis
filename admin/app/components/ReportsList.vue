<script setup lang="ts">
import type { ReportAdminRead, ReportPage } from '~/types/api'

/**
 * Compact list of reports for a user (as reporter or reported) or a ride, on their detail pages.
 * Links to the inbox filtered the same way when there are more.
 */
const props = defineProps<{ userId?: string, rideId?: string, limit?: number }>()

const { t, locale } = useI18n()
const { request } = useApi()
const apiError = useApiError()

const pageSize = computed(() => props.limit ?? 10)
const filter = computed(() => (props.userId ? { user_id: props.userId } : props.rideId ? { ride_id: props.rideId } : {}))

const { data, status, error } = useAsyncData(
  `reports-of-${props.userId ?? ''}-${props.rideId ?? ''}`,
  () => request<ReportPage>('/admin/reports', { query: { ...filter.value, limit: pageSize.value, offset: 0 } }),
)

const items = computed(() => data.value?.items ?? [])
const inboxLink = computed(() => ({ path: '/reports', query: { status: 'all', ...filter.value } }))

/** For a user's list: whether they reported or were reported. */
function side(report: ReportAdminRead): 'reporter' | 'reported' | null {
  if (!props.userId) return null
  if (report.reporter?.id === props.userId) return 'reporter'
  if (report.reported?.id === props.userId) return 'reported'
  return null
}
</script>

<template>
  <UCard>
    <template #header>
      <div class="flex items-center justify-between gap-2">
        <h2 class="font-semibold">
          {{ t('reports.title') }}
          <span
            v-if="data"
            class="font-normal text-(--ui-text-muted)"
          >({{ data.total }})</span>
        </h2>
        <UButton
          v-if="data && data.total > items.length"
          color="neutral"
          variant="ghost"
          size="sm"
          icon="i-lucide-list"
          :label="t('reports.seeAll')"
          :to="inboxLink"
        />
      </div>
    </template>

    <UAlert
      v-if="error"
      color="error"
      variant="subtle"
      icon="i-lucide-circle-alert"
      :title="apiError(error)"
    />
    <USkeleton
      v-else-if="status === 'pending' && !data"
      class="h-16"
    />
    <p
      v-else-if="!items.length"
      class="text-sm text-(--ui-text-muted)"
    >
      {{ t('reports.none') }}
    </p>
    <ul
      v-else
      class="divide-y divide-(--ui-border)"
    >
      <li
        v-for="report in items"
        :key="report.id"
      >
        <NuxtLink
          :to="`/reports/${report.id}`"
          class="-mx-2 flex flex-wrap items-start justify-between gap-2 rounded-md px-2 py-2 text-sm hover:bg-(--ui-bg-elevated)"
          :class="report.priority === 'urgent' && !isClosedReport(report.status) ? 'border-l-2 border-error' : ''"
        >
          <span class="min-w-0 flex-1">
            <span class="flex flex-wrap items-center gap-1.5 font-medium">
              <UIcon
                :name="reportCategoryIcon[report.category] ?? 'i-lucide-flag'"
                class="size-4 shrink-0"
              />
              {{ t(`reports.categories.${report.category}`, report.category) }}
              <UBadge
                v-if="side(report)"
                :color="side(report) === 'reported' ? 'warning' : 'neutral'"
                variant="outline"
                size="sm"
              >
                {{ t(`reports.side.${side(report)}`) }}
              </UBadge>
            </span>
            <span class="block truncate text-xs text-(--ui-text-muted)">
              {{ report.reporter?.name || report.reporter?.email }}
              <template v-if="report.reported"> → {{ report.reported.name || report.reported.email }}</template>
              · {{ formatDate(report.created_at, locale) }}
            </span>
          </span>
          <span class="flex items-center gap-1">
            <UBadge
              v-if="report.priority === 'urgent'"
              color="error"
              variant="subtle"
              size="sm"
            >
              {{ t('reports.priorities.urgent') }}
            </UBadge>
            <UBadge
              :color="reportStatusColor[report.status] ?? 'neutral'"
              variant="subtle"
              size="sm"
            >
              {{ t(`reports.statuses.${report.status}`, report.status) }}
            </UBadge>
          </span>
        </NuxtLink>
      </li>
    </ul>
  </UCard>
</template>
