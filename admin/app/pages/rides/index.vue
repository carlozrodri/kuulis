<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { Page, Ride, RideStatus } from '~/types/api'
import { RIDE_STATUSES } from '~/types/api'

const { t, locale } = useI18n()
const { request } = useApi()
const route = useRoute()
const router = useRouter()

type StatusFilter = RideStatus | 'all'
const statusFilters: StatusFilter[] = ['all', ...RIDE_STATUSES]
const queryString = (key: string) => (typeof route.query[key] === 'string' ? route.query[key] as string : '')
const isDay = (value: string) => /^\d{4}-\d{2}-\d{2}$/.test(value)

// Filters live in the URL so "back" from a ride returns to the same list.
const initialStatus = queryString('status') as StatusFilter
const status = ref<StatusFilter>(statusFilters.includes(initialStatus) ? initialStatus : 'all')
const search = ref(queryString('q'))
const debouncedSearch = ref(search.value.trim())
const dateFrom = ref(isDay(queryString('from')) ? queryString('from') : '')
const dateTo = ref(isDay(queryString('to')) ? queryString('to') : '')
const page = ref(Math.max(1, Number(queryString('page')) || 1))
const limit = 25

let searchTimer: ReturnType<typeof setTimeout> | undefined
watch(search, (value) => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => (debouncedSearch.value = value.trim()), 300)
})
watch([debouncedSearch, status, dateFrom, dateTo], () => {
  page.value = 1
})
watch([debouncedSearch, status, dateFrom, dateTo, page], () => {
  router.replace({
    query: {
      ...(status.value !== 'all' ? { status: status.value } : {}),
      ...(debouncedSearch.value ? { q: debouncedSearch.value } : {}),
      ...(dateFrom.value ? { from: dateFrom.value } : {}),
      ...(dateTo.value ? { to: dateTo.value } : {}),
      ...(page.value > 1 ? { page: String(page.value) } : {}),
    },
  })
})

const invalidRange = computed(() => !!dateFrom.value && !!dateTo.value && dateFrom.value > dateTo.value)

const query = computed(() => ({
  limit,
  offset: (page.value - 1) * limit,
  ...(debouncedSearch.value ? { q: debouncedSearch.value } : {}),
  ...(status.value !== 'all' ? { status: status.value } : {}),
  // Calendar days (YYYY-MM-DD), both inclusive; the API interprets them in Caracas time.
  ...(dateFrom.value && !invalidRange.value ? { date_from: dateFrom.value } : {}),
  ...(dateTo.value && !invalidRange.value ? { date_to: dateTo.value } : {}),
}))

const { data, status: fetchStatus, error } = await useAsyncData(
  'rides',
  () => request<Page<Ride>>('/admin/rides', { query: query.value }),
  { watch: [query] },
)

const statusItems = computed(() =>
  statusFilters.map(value => ({
    label: value === 'all' ? t('rides.allStatuses') : t(`rides.statuses.${value}`),
    value,
  })),
)

const hasFilters = computed(() => status.value !== 'all' || !!search.value || !!dateFrom.value || !!dateTo.value)
function clearFilters() {
  status.value = 'all'
  search.value = ''
  debouncedSearch.value = ''
  dateFrom.value = ''
  dateTo.value = ''
}

const columns = computed<TableColumn<Ride>[]>(() => [
  { accessorKey: 'requested_at', header: t('rides.requestedAt') },
  { id: 'passenger', header: t('rides.passenger') },
  { id: 'driver', header: t('rides.driver') },
  { id: 'route', header: t('rides.route') },
  { accessorKey: 'fare', header: t('rides.fare') },
  { accessorKey: 'payment_method', header: t('rides.paymentMethod') },
  { accessorKey: 'status', header: t('rides.status') },
])

const apiError = useApiError()
</script>

<template>
  <UDashboardPanel id="rides">
    <template #header>
      <UDashboardNavbar :title="t('nav.rides')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton
            icon="i-lucide-radar"
            color="neutral"
            variant="outline"
            :label="t('nav.live')"
            to="/live"
          />
        </template>
      </UDashboardNavbar>
      <UDashboardToolbar>
        <template #left>
          <div class="flex flex-wrap items-center gap-2">
            <USelect
              v-model="status"
              :items="statusItems"
              class="w-52"
              :aria-label="t('rides.status')"
            />
            <UInput
              v-model="dateFrom"
              type="date"
              :max="dateTo || undefined"
              :aria-label="t('rides.dateFrom')"
              class="w-40"
            >
              <template #leading>
                <span class="text-xs text-(--ui-text-muted)">{{ t('rides.from') }}</span>
              </template>
            </UInput>
            <UInput
              v-model="dateTo"
              type="date"
              :min="dateFrom || undefined"
              :aria-label="t('rides.dateTo')"
              class="w-40"
            >
              <template #leading>
                <span class="text-xs text-(--ui-text-muted)">{{ t('rides.to') }}</span>
              </template>
            </UInput>
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
            :placeholder="t('rides.search')"
            class="w-72 max-w-full"
          />
        </template>
      </UDashboardToolbar>
    </template>

    <template #body>
      <UAlert
        v-if="invalidRange"
        color="warning"
        variant="subtle"
        icon="i-lucide-calendar-x"
        :title="t('rides.invalidRange')"
      />
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
        :empty="t('common.empty')"
        class="cursor-pointer"
        @select="(_e: Event, row: { original: Ride }) => navigateTo(`/rides/${row.original.id}`)"
      >
        <template #requested_at-cell="{ row }">
          <span class="whitespace-nowrap">{{ formatDate(row.original.requested_at, locale) }}</span>
        </template>
        <template #passenger-cell="{ row }">
          <span class="font-medium">{{ personName(row.original.passenger) }}</span>
        </template>
        <template #driver-cell="{ row }">
          <div v-if="row.original.driver">
            <p>{{ personName(row.original.driver) }}</p>
            <p
              v-if="row.original.driver.vehicle?.plate"
              class="font-mono text-xs text-(--ui-text-muted)"
            >
              {{ row.original.driver.vehicle.plate }}
            </p>
          </div>
          <span
            v-else
            class="text-(--ui-text-muted)"
          >—</span>
        </template>
        <template #route-cell="{ row }">
          <div class="max-w-xs space-y-0.5 text-xs">
            <p
              class="truncate"
              :title="shortAddress(row.original.pickup)"
            >
              <UIcon
                name="i-lucide-circle-dot"
                class="mr-1 align-middle text-primary"
              />{{ shortAddress(row.original.pickup) }}
            </p>
            <p
              class="truncate"
              :title="shortAddress(row.original.dropoff)"
            >
              <UIcon
                name="i-lucide-map-pin"
                class="mr-1 align-middle text-error"
              />{{ shortAddress(row.original.dropoff) }}
            </p>
          </div>
        </template>
        <template #fare-cell="{ row }">
          <span class="whitespace-nowrap font-medium">{{ formatMoney(row.original.fare, locale) }}</span>
          <UBadge
            v-if="Number(row.original.surge_multiplier) > 1"
            color="warning"
            variant="subtle"
            size="sm"
            class="ml-1"
          >
            {{ formatMultiplier(row.original.surge_multiplier) }}
          </UBadge>
        </template>
        <template #payment_method-cell="{ row }">
          {{ t(`paymentMethods.${row.original.payment_method}`, row.original.payment_method) }}
        </template>
        <template #status-cell="{ row }">
          <UBadge
            :color="rideStatusColor(row.original.status)"
            variant="subtle"
          >
            {{ t(`rides.statuses.${row.original.status}`, row.original.status) }}
          </UBadge>
        </template>
      </UTable>

      <div class="flex items-center justify-between border-t border-(--ui-border) pt-4">
        <span class="text-sm text-(--ui-text-muted)">
          {{ t('rides.total', { n: data?.total ?? 0 }) }}
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
