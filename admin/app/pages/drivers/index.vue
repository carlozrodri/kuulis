<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { AdminDriver, DriverStatus, Page } from '~/types/api'
import { DRIVER_STATUSES } from '~/types/api'

const { t, locale } = useI18n()
const { request } = useApi()
const route = useRoute()
const router = useRouter()

type StatusFilter = DriverStatus | 'all'
const statusFilters: StatusFilter[] = [...DRIVER_STATUSES, 'all']
const initialStatus = route.query.status as StatusFilter | undefined

const status = ref<StatusFilter>(initialStatus && statusFilters.includes(initialStatus) ? initialStatus : 'pending_review')
const search = ref('')
const debouncedSearch = ref('')
let searchTimer: ReturnType<typeof setTimeout> | undefined
watch(search, (value) => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => (debouncedSearch.value = value.trim()), 300)
})
const page = ref(1)
const limit = 20

watch([debouncedSearch, status], () => {
  page.value = 1
})
// Keep the selected tab in the URL so "back" from a driver returns to the same list.
watch(status, (value) => {
  router.replace({ query: { ...route.query, status: value } })
})

const query = computed(() => ({
  // Same limit/offset envelope as /users; page/size are sent too in case the API pages by number.
  limit,
  offset: (page.value - 1) * limit,
  page: page.value,
  size: limit,
  ...(debouncedSearch.value ? { q: debouncedSearch.value } : {}),
  ...(status.value !== 'all' ? { status: status.value } : {}),
}))

const { data, status: fetchStatus, error } = await useAsyncData(
  'drivers',
  () => request<Page<AdminDriver>>('/admin/drivers', { query: query.value }),
  { watch: [query] },
)

const tabs = computed(() =>
  statusFilters.map(value => ({
    label: value === 'all' ? t('drivers.allStatuses') : t(`drivers.statuses.${value}`),
    value,
  })),
)

const columns = computed<TableColumn<AdminDriver>[]>(() => [
  { id: 'name', header: t('drivers.name') },
  { id: 'email', header: t('drivers.email') },
  { accessorKey: 'national_id', header: t('drivers.nationalId') },
  { id: 'plate', header: t('drivers.plate') },
  { accessorKey: 'status', header: t('drivers.status') },
  { accessorKey: 'submitted_at', header: t('drivers.submittedAt') },
])
</script>

<template>
  <UDashboardPanel id="drivers">
    <template #header>
      <UDashboardNavbar :title="t('nav.drivers')">
        <template #leading>
          <UDashboardSidebarCollapse />
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
        <template #right>
          <UInput
            v-model="search"
            icon="i-lucide-search"
            :placeholder="t('drivers.search')"
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
        :title="t('errors.generic')"
      />
      <UTable
        :data="data?.items ?? []"
        :columns="columns"
        :loading="fetchStatus === 'pending'"
        :empty="t('common.empty')"
        class="cursor-pointer"
        @select="(_e: Event, row: { original: AdminDriver }) => navigateTo(`/drivers/${row.original.id}`)"
      >
        <template #name-cell="{ row }">
          <span class="font-medium">{{ row.original.user?.full_name || '—' }}</span>
        </template>
        <template #email-cell="{ row }">
          {{ row.original.user?.email ?? '—' }}
        </template>
        <template #national_id-cell="{ row }">
          {{ row.original.national_id ?? '—' }}
        </template>
        <template #plate-cell="{ row }">
          <span class="font-mono">{{ row.original.vehicle?.plate ?? '—' }}</span>
        </template>
        <template #status-cell="{ row }">
          <UBadge
            :color="driverStatusColor[row.original.status]"
            variant="subtle"
          >
            {{ t(`drivers.statuses.${row.original.status}`) }}
          </UBadge>
        </template>
        <template #submitted_at-cell="{ row }">
          {{ formatDate(row.original.submitted_at, locale) }}
        </template>
      </UTable>

      <div class="flex items-center justify-between border-t border-(--ui-border) pt-4">
        <span class="text-sm text-(--ui-text-muted)">
          {{ t('drivers.total', { n: data?.total ?? 0 }) }}
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
