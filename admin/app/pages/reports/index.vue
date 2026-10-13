<script setup lang="ts">
import type { TableColumn, TableRow } from '@nuxt/ui'
import type { ReportAdminRead, ReportCategory, ReportPage, ReportPriority, ReportSource, ReportStatus, TagCount } from '~/types/api'
import { REPORT_CATEGORIES, REPORT_PRIORITIES, REPORT_SOURCES, REPORT_STATUSES } from '~/types/api'

definePageMeta({ permission: 'reports.manage' })

const { t, locale } = useI18n()
const { request } = useApi()
const route = useRoute()
const router = useRouter()
const apiError = useApiError()
const reportCounts = useReportCounts()

/** Work queues (doc 13). `all` is the plain list with the status filter. */
type View = 'waiting_staff' | 'waiting_user' | 'mine' | 'unassigned' | 'overdue' | 'all'
const VIEWS: View[] = ['waiting_staff', 'waiting_user', 'mine', 'unassigned', 'overdue', 'all']
type StatusFilter = ReportStatus | 'all'
const statusFilters: StatusFilter[] = ['all', ...REPORT_STATUSES]
const queryString = (key: string) => (typeof route.query[key] === 'string' ? route.query[key] as string : '')

// Filters live in the URL so "back" from a ticket returns to the same list. The team's queue comes first; links
// from a user or a ride (with their own filters) open the full list.
const initialView = queryString('view') as View
const linkedFilter = !!(queryString('user_id') || queryString('ride_id'))
const view = ref<View>(VIEWS.includes(initialView) ? initialView : linkedFilter ? 'all' : 'waiting_staff')
const initialStatus = queryString('status') as StatusFilter
const status = ref<StatusFilter>(statusFilters.includes(initialStatus) ? initialStatus : 'all')
const initialCategory = queryString('category') as ReportCategory
const category = ref<ReportCategory | 'all'>(REPORT_CATEGORIES.includes(initialCategory) ? initialCategory : 'all')
const initialPriority = queryString('priority') as ReportPriority
const priority = ref<ReportPriority | 'all'>(REPORT_PRIORITIES.includes(initialPriority) ? initialPriority : 'all')
const initialSource = queryString('source') as ReportSource
const source = ref<ReportSource | 'all'>(REPORT_SOURCES.includes(initialSource) ? initialSource : 'all')
const tag = ref(queryString('tag') || 'all')
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
const filters = [debouncedSearch, view, status, category, priority, source, tag, userId, rideId]
watch(filters, () => {
  page.value = 1
})
watch([...filters, page], () => {
  router.replace({
    query: {
      ...(view.value !== 'waiting_staff' ? { view: view.value } : {}),
      ...(status.value !== 'all' ? { status: status.value } : {}),
      ...(category.value !== 'all' ? { category: category.value } : {}),
      ...(priority.value !== 'all' ? { priority: priority.value } : {}),
      ...(source.value !== 'all' ? { source: source.value } : {}),
      ...(tag.value !== 'all' ? { tag: tag.value } : {}),
      ...(userId.value ? { user_id: userId.value } : {}),
      ...(rideId.value ? { ride_id: rideId.value } : {}),
      ...(debouncedSearch.value ? { q: debouncedSearch.value } : {}),
      ...(page.value > 1 ? { page: String(page.value) } : {}),
    },
  })
})

const viewQuery = (value: View): Record<string, string> => {
  switch (value) {
    case 'waiting_staff':
      return { waiting_on: 'staff' }
    case 'waiting_user':
      return { waiting_on: 'user' }
    case 'mine':
      return { mine: 'true' }
    case 'unassigned':
      return { unassigned: 'true' }
    case 'overdue':
      return { overdue: 'true' }
    default:
      return {}
  }
}

const query = computed(() => ({
  limit,
  offset: (page.value - 1) * limit,
  ...viewQuery(view.value),
  ...(status.value !== 'all' ? { status: status.value } : {}),
  ...(category.value !== 'all' ? { category: category.value } : {}),
  ...(priority.value !== 'all' ? { priority: priority.value } : {}),
  ...(source.value !== 'all' ? { source: source.value } : {}),
  ...(tag.value !== 'all' ? { tag: tag.value } : {}),
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

const { data: tagCounts } = useAsyncData('support-tags', () => request<TagCount[]>('/admin/support/tags').catch(() => [] as TagCount[]))

// New tickets and answers arrive while the inbox is open: refresh quietly every minute (also re-reads the SLA).
const now = ref(Date.now())
let timer: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  timer = setInterval(() => {
    now.value = Date.now()
    if (document.visibilityState === 'visible') refresh()
  }, 60_000)
})
onBeforeUnmount(() => clearInterval(timer))

const counts = computed(() => data.value?.counts ?? reportCounts.counts.value)
const viewCount = (value: View): number | null => {
  if (value === 'waiting_staff') return counts.value?.waiting_staff ?? null
  if (value === 'mine') return counts.value?.mine ?? null
  if (value === 'overdue') return counts.value?.overdue ?? null
  return null
}
const tabs = computed(() =>
  VIEWS.map((value) => {
    const n = viewCount(value)
    return {
      label: t(`support.views.${value}`),
      value,
      ...(n ? { badge: { label: String(n), color: value === 'overdue' ? 'error' as const : 'neutral' as const, variant: value === 'overdue' ? 'solid' as const : 'subtle' as const } } : {}),
    }
  }),
)

const statusItems = computed(() => statusFilters.map(value => ({ label: value === 'all' ? t('reports.allStatuses') : t(`reports.statuses.${value}`), value })))
const categoryItems = computed(() => [
  { label: t('reports.allCategories'), value: 'all' },
  ...REPORT_CATEGORIES.map(value => ({ label: t(`reports.categories.${value}`), value })),
])
const priorityItems = computed(() => [
  { label: t('reports.allPriorities'), value: 'all' },
  ...REPORT_PRIORITIES.map(value => ({ label: t(`reports.priorities.${value}`), value })),
])
const sourceItems = computed(() => [
  { label: t('support.allSources'), value: 'all' },
  ...REPORT_SOURCES.map(value => ({ label: t(`support.sources.${value}`), value })),
])
const tagItems = computed(() => {
  const list = (tagCounts.value ?? []).map(item => ({ label: `${item.tag} (${item.count})`, value: item.tag }))
  if (tag.value !== 'all' && !list.some(item => item.value === tag.value)) list.push({ label: tag.value, value: tag.value })
  return [{ label: t('support.allTags'), value: 'all' }, ...list]
})

const hasFilters = computed(() =>
  status.value !== 'all' || category.value !== 'all' || priority.value !== 'all' || source.value !== 'all' || tag.value !== 'all'
  || !!search.value || !!userId.value || !!rideId.value,
)
function clearFilters() {
  status.value = 'all'
  category.value = 'all'
  priority.value = 'all'
  source.value = 'all'
  tag.value = 'all'
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
    // Urgent open tickets get a red edge on the first cell (borders on <tr> do not render in collapsed tables).
    meta: { class: { td: (cell: { row: TableRow<ReportAdminRead> }) => (isUrgent(cell.row.original) ? 'border-l-4 border-l-error' : 'border-l-4 border-l-transparent') } },
  },
  { accessorKey: 'category', header: t('reports.category') },
  { id: 'people', header: t('reports.people') },
  { accessorKey: 'description', header: t('reports.description') },
  { id: 'waiting', header: t('support.waiting') },
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
        <template #right>
          <UButton
            color="neutral"
            variant="ghost"
            icon="i-lucide-message-square-quote"
            :label="t('nav.cannedReplies')"
            to="/support/canned"
            class="hidden sm:flex"
          />
          <UButton
            color="neutral"
            variant="ghost"
            icon="i-lucide-chart-no-axes-column"
            :label="t('nav.supportMetrics')"
            to="/support/metrics"
            class="hidden sm:flex"
          />
        </template>
      </UDashboardNavbar>
      <UDashboardToolbar>
        <template #left>
          <UTabs
            v-model="view"
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
              v-model="status"
              :items="statusItems"
              class="w-36"
              :aria-label="t('reports.status')"
            />
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
            <USelect
              v-model="source"
              :items="sourceItems"
              class="w-40"
              :aria-label="t('support.source')"
            />
            <USelect
              v-model="tag"
              :items="tagItems"
              class="w-44"
              icon="i-lucide-tag"
              :aria-label="t('support.tags')"
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
          <p
            v-if="row.original.source && row.original.source !== 'app'"
            class="text-xs text-(--ui-text-muted)"
          >
            <UIcon
              :name="sourceIcon[row.original.source]"
              class="mr-0.5 align-middle"
            />{{ t(`support.sources.${row.original.source}`) }}
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
            <p class="flex flex-wrap items-center gap-1">
              <span class="text-xs text-(--ui-text-muted)">{{ t(`reports.reporterRole.${row.original.reporter_role ?? 'general'}`) }}:</span>
              <span class="font-medium">{{ ticketContact(row.original).name }}</span>
              <UBadge
                v-if="ticketContact(row.original).web"
                color="info"
                variant="subtle"
                size="sm"
                icon="i-lucide-globe"
              >
                {{ t('support.web') }}
              </UBadge>
            </p>
            <p
              v-if="!row.original.reporter && row.original.contact_email"
              class="text-xs text-(--ui-text-muted)"
            >
              {{ row.original.contact_email }}
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
          <div class="flex max-w-sm flex-wrap items-center gap-1 text-xs text-(--ui-text-muted)">
            <span v-if="row.original.messages_count">
              <UIcon
                name="i-lucide-messages-square"
                class="mr-0.5 align-middle"
              />{{ t('support.messagesCount', { n: row.original.messages_count }) }}
            </span>
            <span v-if="row.original.notes_count">
              <UIcon
                name="i-lucide-message-square"
                class="mr-0.5 align-middle"
              />{{ t('reports.notesCount', { n: row.original.notes_count }) }}
            </span>
            <UBadge
              v-for="item in row.original.tags ?? []"
              :key="item"
              color="neutral"
              variant="outline"
              size="sm"
            >
              {{ item }}
            </UBadge>
          </div>
        </template>
        <template #waiting-cell="{ row }">
          <UBadge
            v-if="row.original.waiting_on"
            :color="waitingOnColor[row.original.waiting_on]"
            variant="subtle"
            size="sm"
          >
            {{ t(`support.waitingOn.${row.original.waiting_on}`) }}
          </UBadge>
          <div class="mt-1 text-xs whitespace-nowrap">
            <UBadge
              v-if="slaState(row.original, now) === 'overdue'"
              color="error"
              variant="solid"
              size="sm"
              icon="i-lucide-alarm-clock"
            >
              {{ t('support.overdue') }}
            </UBadge>
            <span
              v-else-if="slaState(row.original, now)"
              :class="slaState(row.original, now) === 'soon' ? 'font-medium text-warning' : 'text-(--ui-text-muted)'"
              :title="formatDate(row.original.sla_due_at, locale)"
            >
              <UIcon
                name="i-lucide-hourglass"
                class="mr-0.5 align-middle"
              />{{ t('support.dueIn', { when: formatAgo(row.original.sla_due_at, locale, now) }) }}
            </span>
          </div>
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
            {{ formatAgo(row.original.last_message_at ?? row.original.updated_at, locale, now) }}
          </p>
          <p
            v-if="row.original.csat"
            class="text-xs whitespace-nowrap text-warning"
            :title="row.original.csat_comment ?? undefined"
          >
            <UIcon
              name="i-lucide-star"
              class="mr-0.5 align-middle"
            />{{ t('support.csatShort', { n: row.original.csat }) }}
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
