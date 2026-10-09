<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { Page, Promotion, PromotionStatus } from '~/types/api'
import { PROMOTION_STATUSES } from '~/types/api'

const { t, locale } = useI18n()
const { request } = useApi()
const auth = useAuth()
const route = useRoute()
const router = useRouter()
const apiError = useApiError()

type StatusFilter = PromotionStatus | 'all'
const statusFilters: StatusFilter[] = ['all', ...PROMOTION_STATUSES]
const queryString = (key: string) => (typeof route.query[key] === 'string' ? route.query[key] as string : '')

// Filters live in the URL so "back" from a promotion returns to the same list.
const initialStatus = queryString('status') as StatusFilter
const status = ref<StatusFilter>(statusFilters.includes(initialStatus) ? initialStatus : 'all')
const search = ref(queryString('q'))
const debouncedSearch = ref(search.value.trim())
const page = ref(Math.max(1, Number(queryString('page')) || 1))
const limit = 20

let searchTimer: ReturnType<typeof setTimeout> | undefined
watch(search, (value) => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => (debouncedSearch.value = value.trim()), 300)
})
watch([debouncedSearch, status], () => {
  page.value = 1
})
watch([debouncedSearch, status, page], () => {
  router.replace({
    query: {
      ...(status.value !== 'all' ? { status: status.value } : {}),
      ...(debouncedSearch.value ? { q: debouncedSearch.value } : {}),
      ...(page.value > 1 ? { page: String(page.value) } : {}),
    },
  })
})

const query = computed(() => ({
  limit,
  offset: (page.value - 1) * limit,
  ...(debouncedSearch.value ? { q: debouncedSearch.value } : {}),
  ...(status.value !== 'all' ? { status: status.value } : {}),
}))

const { data, status: fetchStatus, error } = await useAsyncData(
  'promotions',
  () => request<Page<Promotion>>('/admin/promotions', { query: query.value }),
  { watch: [query] },
)

const tabs = computed(() =>
  statusFilters.map(value => ({
    label: value === 'all' ? t('promotions.allStatuses') : t(`promotions.statuses.${value}`),
    value,
  })),
)

const columns = computed<TableColumn<Promotion>[]>(() => [
  { accessorKey: 'name', header: t('promotions.name') },
  { id: 'discount', header: t('promotions.discount') },
  { id: 'validity', header: t('promotions.validity') },
  { id: 'budget', header: t('promotions.budgetUsage') },
  { id: 'uses', header: t('promotions.uses') },
  { accessorKey: 'status', header: t('promotions.status') },
])
</script>

<template>
  <UDashboardPanel id="promotions">
    <template #header>
      <UDashboardNavbar :title="t('nav.promotions')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton
            icon="i-lucide-shield-alert"
            color="neutral"
            variant="outline"
            :label="t('promotions.alerts.title')"
            to="/promotions/alerts"
          />
          <UButton
            v-if="auth.isAdmin.value"
            icon="i-lucide-plus"
            :label="t('promotions.new')"
            to="/promotions/new"
          />
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
            :placeholder="t('promotions.search')"
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
        :empty="t('common.empty')"
        class="cursor-pointer"
        @select="(_e: Event, row: { original: Promotion }) => navigateTo(`/promotions/${row.original.id}`)"
      >
        <template #name-cell="{ row }">
          <p class="font-medium">
            {{ row.original.name }}
          </p>
          <UBadge
            v-if="row.original.code"
            color="neutral"
            variant="outline"
            size="sm"
            class="font-mono"
          >
            {{ row.original.code }}
          </UBadge>
          <span
            v-else
            class="text-xs text-(--ui-text-muted)"
          >{{ t('promotions.automatic') }}</span>
        </template>
        <template #discount-cell="{ row }">
          <p class="whitespace-nowrap font-medium">
            {{ formatDiscount(row.original, locale) }}
          </p>
          <p
            v-if="row.original.discount_type === 'percent' && row.original.max_discount"
            class="text-xs whitespace-nowrap text-(--ui-text-muted)"
          >
            {{ t('promotions.upTo', { amount: formatMoney(row.original.max_discount, locale) }) }}
          </p>
        </template>
        <template #validity-cell="{ row }">
          <div class="text-xs whitespace-nowrap">
            <p>{{ formatDate(row.original.starts_at, locale) }}</p>
            <p class="text-(--ui-text-muted)">
              → {{ formatDate(row.original.ends_at, locale) }}
            </p>
          </div>
        </template>
        <template #budget-cell="{ row }">
          <div class="w-44 space-y-1">
            <UProgress
              :model-value="budgetUsage(row.original)"
              :color="budgetUsage(row.original) >= 90 ? 'warning' : 'primary'"
              size="sm"
            />
            <p class="text-xs text-(--ui-text-muted) tabular-nums">
              {{ formatMoney(committedBudget(row.original.stats), locale) }} / {{ formatMoney(row.original.budget, locale) }}
            </p>
          </div>
        </template>
        <template #uses-cell="{ row }">
          <span class="tabular-nums">{{ row.original.stats?.uses ?? 0 }}</span>
          <span
            v-if="row.original.max_total_uses"
            class="text-(--ui-text-muted)"
          > / {{ row.original.max_total_uses }}</span>
        </template>
        <template #status-cell="{ row }">
          <UBadge
            :color="promotionStatusColor[row.original.status] ?? 'neutral'"
            variant="subtle"
          >
            {{ t(`promotions.statuses.${row.original.status}`, row.original.status) }}
          </UBadge>
        </template>
      </UTable>

      <div class="flex items-center justify-between border-t border-(--ui-border) pt-4">
        <span class="text-sm text-(--ui-text-muted)">
          {{ t('promotions.total', { n: data?.total ?? 0 }) }}
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
