<script setup lang="ts">
import type { TableColumn, TableRow } from '@nuxt/ui'
import type { ReportAdminRead, ReportCategory, ReportPage, ReportPriority, ReportStatus } from '~/types/api'
import { REPORT_CATEGORIES, REPORT_PRIORITIES, REPORT_STATUSES } from '~/types/api'

const { t, locale } = useI18n()
const { request } = useApi()
const route = useRoute()
const router = useRouter()
const apiError = useApiError()
const reportCounts = useReportCounts()

type StatusFilter = ReportStatus | 'all'
const statusFilters: StatusFilter[] = [...REPORT_STATUSES, 'all']
const queryString = (key: string) => (typeof route.query[key] === 'string' ? route.query[key] as string : '')

// Filters live in the URL so "back" from a report returns to the same list. Open first: that is the work queue.
const initialStatus = queryString('status') as StatusFilter
const status = ref<StatusFilter>(statusFilters.includes(initialStatus) ? initialStatus : 'open')
const initialCategory = queryString('category') as ReportCategory
const category = ref<ReportCategory | 'all'>(REPORT_CATEGORIES.includes(initialCategory) ? initialCategory : 'all')
const initialPriority = queryString('priority') as ReportPriority
const priority = ref<ReportPriority | 'all'>(REPORT_PRIORITIES.includes(initialPriority) ? initialPriority : 'all')
// From the user / ride pages ("see all"): removable filters.
const userId = ref(queryString('user_id'))
const rideId = ref(queryString('ride_id'))
const search = ref(queryString('q'))
const debouncedSearch = ref(search.value.trim())
const page = ref(Math.max(1, Number(queryString('page')) || 1))
const limit = 25

let searchTimer: ReturnType<typeof setTimeout> | undefined
watch(search, (value) => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => (debouncedSearch.value = value.trim()), 300)
})
watch([debouncedSearch, status, category, priority, userId, rideId], () => {
  page.value = 1
})
watch([debouncedSearch, status, category, priority, userId, rideId, page], () => {
  router.replace({
    query: {
      ...(status.value !== 'open' ? { status: status.value } : {}),
      ...(category.value !== 'all' ? { category: category.value } : {}),
      ...(priority.value !== 'all' ? { priority: priority.value } : {}),
      ...(userId.value ? { user_id: userId.value } : {}),
      ...(rideId.value ? { ride_id: rideId.value } : {}),
      ...(debouncedSearch.value ? { q: debouncedSearch.value } : {}),
      ...(page.value > 1 ? { page: String(page.value) } : {}),
    },
  })
})

const query = computed(() => ({
  limit,
  offset: (page.value - 1) * limit,
  ...(status.value !== 'all' ? { status: status.value } : {}),
  ...(category.value !== 'all' ? { category: category.value } : {}),
  ...(priority.value !== 'all' ? { priority: priority.value } : {}),
  ...(userId.value ? { user_id: userId.value } : {}),
  ...(rideId.value ? { ride_id: rideId.value } : {}),
  ...(debouncedSearch.value ? { q: debouncedSearch.value } : {}),
}))

const { data, status: fetchStatus, error, refresh } = await useAsyncData(
  'reports',
  () => request<ReportPage>('/admin/reports', { query: query.value }),
  { watch: [query] },
)
watch(data, value => reportCounts.set(value?.counts), { immediate: true })

// New reports arrive while the inbox is open: refresh quietly every minute.
let timer: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  timer = setInterval(() => {
    if (document.visibilityState === 'visible') refresh()
  }, 60_000)
})
onBeforeUnmount(() => clearInterval(timer))

const counts = computed(() => data.value?.counts ?? reportCounts.counts.value)
const tabCount = (value: StatusFilter): number | null => {
  if (value === 'open') return counts.value?.open ?? null
  if (value === 'in_review') return counts.value?.in_review ?? null
  return null
}
const tabs = computed(() =>
  statusFilters.map((value) => {
    const n = tabCount(value)
    return {
      label: value === 'all' ? t('reports.allStatuses') : t(`reports.statuses.${value}`),
      value,
      ...(n ? { badge: { label: String(n), color: 'neutral' as const, variant: 'subtle' as const } } : {}),
    }
  }),
)

const categoryItems = computed(() => [
  { label: t('reports.allCategories'), value: 'all' },
  ...REPORT_CATEGORIES.map(value => ({ label: t(`reports.categories.${value}`), value })),
])
const priorityItems = computed(() => [
  { label: t('reports.allPriorities'), value: 'all' },
  ...REPORT_PRIORITIES.map(value => ({ label: t(`reports.priorities.${value}`), value })),
])

const hasFilters = computed(() => category.value !== 'all' || priority.value !== 'all' || !!search.value || !!userId.value || !!rideId.value)
function clearFilters() {
  category.value = 'all'
  priority.value = 'all'
  search.value = ''
  debouncedSearch.value = ''
  userId.value = ''
  rideId.value = ''
}

const isUrgent = (report: ReportAdminRead) => report.priority === 'urgent' && !isClosedReport(report.status)

const columns = computed<TableColumn<ReportAdminRead>[]>(() => [
  {
    accessorKey: 'created_at',
    header: t('reports.createdAt'),
    // Urgent open reports get a red edge on the first cell (borders on <tr> do not render in collapsed tables).
    meta: { class: { td: (cell: { row: TableRow<ReportAdminRead> }) => (isUrgent(cell.row.original) ? 'border-l-4 border-l-error' : 'border-l-4 border-l-transparent') } },
  },
  { accessorKey: 'category', header: t('reports.category') },
  { id: 'people', header: t('reports.people') },
  { accessorKey: 'description', header: t('reports.description') },
  { id: 'assigned', header: t('reports.assignedTo') },
  { accessorKey: 'status', header: t('reports.status') },
])

const rowClass = (row: TableRow<ReportAdminRead>) => (isUrgent(row.original) ? 'bg-error/5' : '')
</script>

<template>
  <UDashboardPanel id="reports">
    <template #header>
      <UDashboardNavbar :title="t('nav.reports')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #trailing>
          <UBadge
            v-if="counts?.urgent_open"
            color="error"
            variant="solid"
            icon="i-lucide-siren"
          >
            {{ t('reports.urgentOpen', { n: counts.urgent_open }) }}
          </UBadge>
        </template>
      </UDashboardNavbar>
      <UDashboardToolbar>
        <template #left>
          <UTabs
            v-model="status"
            :items="tabs"
            :content="false"
            size="sm"
            variant="link"
          />
        </template>
      </UDashboardToolbar>
      <UDashboardToolbar>
        <template #left>
          <div class="flex flex-wrap items-center gap-2">
            <USelect
              v-model="category"
              :items="categoryItems"
              class="w-52"
              :aria-label="t('reports.category')"
            />
            <USelect
              v-model="priority"
              :items="priorityItems"
              class="w-40"
              :aria-label="t('reports.priority')"
            />
            <UBadge
              v-if="userId"
              color="neutral"
              variant="outline"
              class="gap-1"
            >
              {{ t('reports.filterUser', { id: userId.slice(0, 8) }) }}
              <UButton
                icon="i-lucide-x"
                size="xs"
                color="neutral"
                variant="link"
                :aria-label="t('reports.removeFilter')"
                @click="userId = ''"
              />
            </UBadge>
            <UBadge
              v-if="rideId"
              color="neutral"
              variant="outline"
              class="gap-1"
            >
              {{ t('reports.filterRide', { id: rideId.slice(0, 8) }) }}
              <UButton
                icon="i-lucide-x"
                size="xs"
                color="neutral"
                variant="link"
                :aria-label="t('reports.removeFilter')"
                @click="rideId = ''"
              />
            </UBadge>
            <UButton
              v-if="hasFilters"
              icon="i-lucide-x"
              color="neutral"
              variant="ghost"
              size="sm"
              :label="t('rides.clearFilters')"
              @click="clearFilters"
            />
          </div>
        </template>
        <template #right>
          <UInput
            v-model="search"
            icon="i-lucide-search"
            :placeholder="t('reports.search')"
            maxlength="100"
            class="w-72 max-w-full"
          />
        </template>
      </UDashboardToolbar>
    </template>

    <template #body>
      <UAlert
        v-if="error"
        color="error"
        variant="subtle"
        icon="i-lucide-circle-alert"
        :title="apiError(error)"
      />

      <UTable
        :data="data?.items ?? []"
        :columns="columns"
        :loading="fetchStatus === 'pending'"
        :empty="t('reports.empty')"
        :ui="{ tr: 'cursor-pointer' }"
        :meta="{ class: { tr: rowClass } }"
        @select="(_e: Event, row: TableRow<ReportAdminRead>) => navigateTo(`/reports/${row.original.id}`)"
      >
        <template #created_at-cell="{ row }">
          <span class="whitespace-nowrap">{{ formatDate(row.original.created_at, locale) }}</span>
          <p
            v-if="row.original.ride_id"
            class="text-xs text-(--ui-text-muted)"
          >
            <UIcon
              name="i-lucide-route"
              class="mr-0.5 align-middle"
            />{{ t('reports.ride', { id: row.original.ride_id.slice(0, 8) }) }}
          </p>
          <p
            v-else
            class="text-xs text-(--ui-text-muted)"
          >
            {{ t('reports.general') }}
          </p>
        </template>
        <template #category-cell="{ row }">
          <div class="flex items-center gap-1.5">
            <UIcon
              :name="reportCategoryIcon[row.original.category] ?? 'i-lucide-flag'"
              class="size-4 shrink-0"
              :class="isUrgent(row.original) ? 'text-error' : 'text-(--ui-text-muted)'"
            />
            <span class="whitespace-nowrap">{{ t(`reports.categories.${row.original.category}`, row.original.category) }}</span>
          </div>
          <UBadge
            v-if="row.original.priority === 'urgent'"
            color="error"
            :variant="isUrgent(row.original) ? 'solid' : 'subtle'"
            size="sm"
            class="mt-1"
          >
            {{ t('reports.priorities.urgent') }}
          </UBadge>
        </template>
        <template #people-cell="{ row }">
          <div class="text-sm">
            <p>
              <span class="text-xs text-(--ui-text-muted)">{{ t(`reports.reporterRole.${row.original.reporter_role ?? 'general'}`) }}:</span>
              <span class="font-medium">{{ row.original.reporter?.name || row.original.reporter?.email || '—' }}</span>
            </p>
            <p v-if="row.original.reported">
              <span class="text-xs text-(--ui-text-muted)">{{ t('reports.reported') }}:</span>
              {{ row.original.reported.name || row.original.reported.email }}
            </p>
          </div>
        </template>
        <template #description-cell="{ row }">
          <p
            class="max-w-sm truncate text-sm"
            :title="row.original.description"
          >
            {{ row.original.description }}
          </p>
          <p
            v-if="row.original.notes_count"
            class="text-xs text-(--ui-text-muted)"
          >
            <UIcon
              name="i-lucide-message-square"
              class="mr-0.5 align-middle"
            />{{ t('reports.notesCount', { n: row.original.notes_count }) }}
          </p>
        </template>
        <template #assigned-cell="{ row }">
          <span
            v-if="row.original.assigned_to"
            class="text-sm"
          >{{ row.original.assigned_to.name || row.original.assigned_to.email }}</span>
          <span
            v-else
            class="text-sm text-(--ui-text-muted)"
          >{{ t('reports.unassigned') }}</span>
        </template>
        <template #status-cell="{ row }">
          <UBadge
            :color="reportStatusColor[row.original.status] ?? 'neutral'"
            variant="subtle"
          >
            {{ t(`reports.statuses.${row.original.status}`, row.original.status) }}
          </UBadge>
          <p class="text-xs whitespace-nowrap text-(--ui-text-muted)">
            {{ formatAgo(row.original.updated_at, locale) }}
          </p>
        </template>
      </UTable>

      <div class="flex items-center justify-between border-t border-(--ui-border) pt-4">
        <span class="text-sm text-(--ui-text-muted)">
          {{ t('reports.total', { n: data?.total ?? 0 }) }}
        </span>
        <UPagination
          v-model:page="page"
          :total="data?.total ?? 0"
          :items-per-page="limit"
        />
      </div>
    </template>
  </UDashboardPanel>
</template>
