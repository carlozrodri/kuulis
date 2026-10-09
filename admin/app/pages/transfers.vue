<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { AdminTransfer, AppConfig, Page } from '~/types/api'

const { t, locale } = useI18n()
const { request } = useApi()
const route = useRoute()
const router = useRouter()
const apiError = useApiError()

const queryString = (key: string) => (typeof route.query[key] === 'string' ? route.query[key] as string : '')
const search = ref(queryString('q'))
const debouncedSearch = ref(search.value.trim())
const page = ref(Math.max(1, Number(queryString('page')) || 1))
const limit = 25

let searchTimer: ReturnType<typeof setTimeout> | undefined
watch(search, (value) => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => (debouncedSearch.value = value.trim()), 300)
})
watch(debouncedSearch, () => {
  page.value = 1
})
watch([debouncedSearch, page], () => {
  router.replace({
    query: {
      ...(debouncedSearch.value ? { q: debouncedSearch.value } : {}),
      ...(page.value > 1 ? { page: String(page.value) } : {}),
    },
  })
})

const query = computed(() => ({
  limit,
  offset: (page.value - 1) * limit,
  ...(debouncedSearch.value ? { q: debouncedSearch.value } : {}),
}))

const { data, status, error } = await useAsyncData(
  'transfers',
  () => request<Page<AdminTransfer>>('/admin/transfers', { query: query.value }),
  { watch: [query] },
)
const { data: config } = await useAsyncData('transfers-config', () => request<AppConfig>('/admin/config').catch(() => null))
const monthlyLimit = computed(() => config.value?.transfer_monthly_limit ?? '50.00')

const columns = computed<TableColumn<AdminTransfer>[]>(() => [
  { accessorKey: 'created_at', header: t('transfers.date') },
  { id: 'sender', header: t('transfers.sender') },
  { id: 'recipient', header: t('transfers.recipient') },
  { accessorKey: 'amount', header: t('transfers.amount') },
  { accessorKey: 'note', header: t('transfers.note') },
])
</script>

<template>
  <UDashboardPanel id="transfers">
    <template #header>
      <UDashboardNavbar :title="t('nav.transfers')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
      </UDashboardNavbar>
      <UDashboardToolbar>
        <template #left>
          <p class="text-sm text-(--ui-text-muted)">
            {{ t('transfers.help', { limit: formatUsdt(monthlyLimit, locale) }) }}
          </p>
        </template>
        <template #right>
          <UInput
            v-model="search"
            icon="i-lucide-search"
            :placeholder="t('transfers.search')"
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
        :loading="status === 'pending'"
        :empty="t('common.empty')"
      >
        <template #created_at-cell="{ row }">
          <span class="whitespace-nowrap">{{ formatDate(row.original.created_at, locale) }}</span>
        </template>
        <template #sender-cell="{ row }">
          <PartyCell :party="transferParties(row.original).sender" />
        </template>
        <template #recipient-cell="{ row }">
          <PartyCell :party="transferParties(row.original).recipient" />
        </template>
        <template #amount-cell="{ row }">
          <span class="whitespace-nowrap font-medium tabular-nums">{{ formatUsdt(row.original.amount, locale) }}</span>
        </template>
        <template #note-cell="{ row }">
          <span
            class="block max-w-xs truncate"
            :title="row.original.note ?? undefined"
          >{{ row.original.note || '—' }}</span>
        </template>
      </UTable>

      <div class="flex items-center justify-between border-t border-(--ui-border) pt-4">
        <span class="text-sm text-(--ui-text-muted)">
          {{ t('transfers.total', { n: data?.total ?? 0 }) }}
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
