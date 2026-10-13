<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { CampaignRead, CampaignStatus, Page } from '~/types/api'
import { CAMPAIGN_STATUSES } from '~/types/api'

definePageMeta({ permission: 'notifications.send' })

const { t, locale } = useI18n()
const { request } = useApi()
const route = useRoute()
const router = useRouter()
const apiError = useApiError()

const initialStatus = route.query.status as CampaignStatus
const statusFilter = ref<CampaignStatus | 'all'>(CAMPAIGN_STATUSES.includes(initialStatus) ? initialStatus : 'all')
const page = ref(1)
const limit = 20
watch(statusFilter, (value) => {
  page.value = 1
  router.replace({ query: value !== 'all' ? { status: value } : {} })
})

const query = computed(() => ({
  limit,
  offset: (page.value - 1) * limit,
  ...(statusFilter.value !== 'all' ? { status: statusFilter.value } : {}),
}))
const { data, status, error, refresh } = await useAsyncData(
  'campaigns',
  () => request<Page<CampaignRead>>('/admin/campaigns', { query: query.value }),
  { watch: [query] },
)

// Results move while a campaign goes out: refresh the list every few seconds then (visible tab only).
const anySending = computed(() => (data.value?.items ?? []).some(c => c.status === 'sending'))
let timer: ReturnType<typeof setInterval> | undefined
const stopTimer = () => {
  clearInterval(timer)
  timer = undefined
}
watch(anySending, (sending) => {
  stopTimer()
  if (sending) {
    timer = setInterval(() => {
      if (document.visibilityState === 'visible') refresh()
    }, CAMPAIGN_POLL_MS)
  }
}, { immediate: true })
onBeforeUnmount(stopTimer)

const statusItems = computed(() => [
  { label: t('campaigns.allStatuses'), value: 'all' },
  ...CAMPAIGN_STATUSES.map(value => ({ label: t(`campaigns.statuses.${value}`), value })),
])

const columns = computed<TableColumn<CampaignRead>[]>(() => [
  { id: 'name', header: t('campaigns.name') },
  { id: 'status', header: t('campaigns.status') },
  { id: 'audience', header: t('campaigns.audience') },
  { id: 'when', header: t('campaigns.whenCol') },
  { id: 'results', header: t('campaigns.results') },
])

const CHANNEL_ICONS = { push: 'i-lucide-smartphone', inbox: 'i-lucide-inbox', email: 'i-lucide-mail' } as const
</script>

<template>
  <UDashboardPanel id="campaigns">
    <template #header>
      <UDashboardNavbar :title="t('nav.campaigns')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton
            icon="i-lucide-plus"
            :label="t('campaigns.new')"
            to="/campaigns/new"
          />
        </template>
      </UDashboardNavbar>
      <UDashboardToolbar>
        <template #left>
          <USelect
            v-model="statusFilter"
            :items="statusItems"
            class="w-52"
            :aria-label="t('campaigns.status')"
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
        :empty="t('campaigns.empty')"
        :ui="{ tr: 'cursor-pointer' }"
        @select="(_e: Event, row: { original: CampaignRead }) => navigateTo(`/campaigns/${row.original.id}`)"
      >
        <template #name-cell="{ row }">
          <p class="font-medium">
            {{ row.original.name }}
          </p>
          <p class="max-w-xs truncate text-xs text-(--ui-text-muted)">
            {{ row.original.title_es }}
          </p>
        </template>
        <template #status-cell="{ row }">
          <UBadge
            :color="CAMPAIGN_STATUS_COLORS[row.original.status]"
            variant="subtle"
          >
            {{ t(`campaigns.statuses.${row.original.status}`) }}
          </UBadge>
        </template>
        <template #audience-cell="{ row }">
          <p class="max-w-xs text-sm whitespace-normal">
            {{ segmentSummary(row.original.segment, t, locale) }}
          </p>
          <p class="mt-0.5 flex gap-1 text-(--ui-text-muted)">
            <UIcon
              v-for="channel in row.original.channels"
              :key="channel"
              :name="CHANNEL_ICONS[channel]"
              class="size-3.5"
              :aria-label="t(`campaigns.channels.${channel}`)"
            />
          </p>
        </template>
        <template #when-cell="{ row }">
          <p class="text-xs text-(--ui-text-muted)">
            {{ t(`campaigns.when.${campaignMoment(row.original).key}`) }}
          </p>
          <p class="text-sm whitespace-nowrap">
            {{ formatDate(campaignMoment(row.original).at, locale) }}
          </p>
        </template>
        <template #results-cell="{ row }">
          <template v-if="['sending', 'sent', 'cancelled'].includes(row.original.status)">
            <p class="text-sm whitespace-nowrap tabular-nums">
              {{ t('campaigns.sentCount', { n: formatNumber(row.original.stats.sent, locale) }) }}
            </p>
            <p class="text-xs whitespace-nowrap text-(--ui-text-muted) tabular-nums">
              {{ t('campaigns.openedShort', { rate: formatPercent(campaignRates(row.original.stats).openRate, locale) }) }}
            </p>
          </template>
          <span
            v-else
            class="text-(--ui-text-muted)"
          >—</span>
        </template>
      </UTable>

      <div class="flex justify-end border-t border-(--ui-border) pt-4">
        <UPagination
          v-model:page="page"
          :total="data?.total ?? 0"
          :items-per-page="limit"
        />
      </div>
    </template>
  </UDashboardPanel>
</template>
