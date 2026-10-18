<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { MarketingPerformanceRow, MarketingPlatform } from '~/types/api'
import { MARKETING_PLATFORMS } from '~/types/api'

definePageMeta({ permission: 'marketing.view' })

const { t, locale } = useI18n()
const { request } = useApi()
const apiError = useApiError()

const platform = ref<MarketingPlatform | 'all'>('all')
const pillar = ref('')
const format = ref('')
const from = ref('')
const to = ref('')
const platformItems = computed(() => [
  { label: t('marketing.allPlatforms'), value: 'all' },
  ...MARKETING_PLATFORMS.map(p => ({ label: platformLabel[p], value: p })),
])

const query = computed(() => ({
  ...(platform.value !== 'all' ? { platform: platform.value } : {}),
  ...(pillar.value.trim() ? { pillar: pillar.value.trim() } : {}),
  ...(format.value.trim() ? { format: format.value.trim() } : {}),
  ...(isDay(from.value) ? { from: from.value } : {}),
  ...(isDay(to.value) ? { to: to.value } : {}),
}))
const { data, status, error } = await useAsyncData(
  'marketing-performance',
  () => request<MarketingPerformanceRow[]>('/admin/marketing/performance', { query: query.value }),
  { watch: [query] },
)
const totals = computed(() => performanceTotals(data.value ?? []))

const num = (v: number | null | undefined) => formatNumber(v, locale.value)
const columns = computed<TableColumn<MarketingPerformanceRow>[]>(() => [
  { id: 'piece', header: t('marketing.performance.piece') },
  { accessorKey: 'platform', header: t('marketing.performance.platform') },
  { accessorKey: 'published_at', header: t('marketing.performance.publishedAt') },
  { id: 'views', header: t('marketing.metrics.fields.views') },
  { id: 'likes', header: t('marketing.metrics.fields.likes') },
  { id: 'comments', header: t('marketing.metrics.fields.comments') },
  { id: 'shares', header: t('marketing.metrics.fields.shares') },
  { id: 'saves', header: t('marketing.metrics.fields.saves') },
  { id: 'completion', header: t('marketing.metrics.fields.completion_rate') },
  { id: 'age', header: t('marketing.metrics.age') },
  { id: 'link', header: '' },
])
</script>

<template>
  <UDashboardPanel id="marketing-performance">
    <template #header>
      <UDashboardNavbar :title="t('nav.marketingPerformance')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
      </UDashboardNavbar>
      <UDashboardToolbar>
        <div class="flex flex-wrap items-center gap-2 py-1">
          <USelect
            v-model="platform"
            :items="platformItems"
            class="w-40"
          />
          <UInput
            v-model="pillar"
            :placeholder="t('marketing.fields.pillar')"
            class="w-32"
          />
          <UInput
            v-model="format"
            :placeholder="t('marketing.fields.format')"
            class="w-32"
          />
          <UInput
            v-model="from"
            type="date"
            :aria-label="t('marketing.performance.from')"
            class="w-40"
          />
          <UInput
            v-model="to"
            type="date"
            :aria-label="t('marketing.performance.to')"
            class="w-40"
          />
        </div>
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

      <div class="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
        <UCard
          v-for="tile in [
            { key: 'publications', value: num(totals.publications) },
            { key: 'views', value: num(totals.views) },
            { key: 'likes', value: num(totals.likes) },
            { key: 'comments', value: num(totals.comments) },
            { key: 'shares', value: num(totals.shares) },
            { key: 'saves', value: num(totals.saves) },
            { key: 'completion', value: formatPercent(totals.completion, locale) },
          ]"
          :key="tile.key"
          :ui="{ body: 'p-3 sm:p-4' }"
        >
          <p class="text-xs text-(--ui-text-muted)">
            {{ t(`marketing.performance.totals.${tile.key}`) }}
          </p>
          <p class="text-xl font-semibold tabular-nums">
            {{ tile.value }}
          </p>
        </UCard>
      </div>

      <UTable
        :data="data ?? []"
        :columns="columns"
        :loading="status === 'pending'"
        :empty="t('marketing.performance.empty')"
        class="cursor-pointer"
        @select="(_e: Event, row: { original: MarketingPerformanceRow }) => navigateTo(`/marketing/piezas/${row.original.content_id}`)"
      >
        <template #piece-cell="{ row }">
          <p class="max-w-64 truncate font-medium">
            {{ row.original.title }}
          </p>
          <p class="font-mono text-xs text-(--ui-text-muted)">
            {{ row.original.code }}<template v-if="row.original.pillar">
              · {{ row.original.pillar }}
            </template>
          </p>
        </template>
        <template #platform-cell="{ row }">
          <span class="flex items-center gap-1 whitespace-nowrap">
            <UIcon :name="platformIcon[row.original.platform]" />
            {{ platformLabel[row.original.platform] }}
          </span>
        </template>
        <template #published_at-cell="{ row }">
          <span class="whitespace-nowrap">{{ formatCaracasDateTime(row.original.published_at, locale) }}</span>
        </template>
        <template #views-cell="{ row }">
          <span class="tabular-nums">{{ num(row.original.latest?.views) }}</span>
        </template>
        <template #likes-cell="{ row }">
          <span class="tabular-nums">{{ num(row.original.latest?.likes) }}</span>
        </template>
        <template #comments-cell="{ row }">
          <span class="tabular-nums">{{ num(row.original.latest?.comments) }}</span>
        </template>
        <template #shares-cell="{ row }">
          <span class="tabular-nums">{{ num(row.original.latest?.shares) }}</span>
        </template>
        <template #saves-cell="{ row }">
          <span class="tabular-nums">{{ num(row.original.latest?.saves) }}</span>
        </template>
        <template #completion-cell="{ row }">
          <span class="tabular-nums">{{ formatPercent(row.original.latest?.completion_rate, locale) }}</span>
        </template>
        <template #age-cell="{ row }">
          <span
            v-if="row.original.latest"
            class="whitespace-nowrap text-(--ui-text-muted)"
          >{{ t('marketing.metrics.hours', { n: row.original.latest.age_h }) }}</span>
          <UBadge
            v-else
            color="warning"
            variant="subtle"
          >
            {{ t('marketing.metrics.none') }}
          </UBadge>
        </template>
        <template #link-cell="{ row }">
          <UButton
            v-if="row.original.url"
            :to="row.original.url"
            target="_blank"
            rel="noopener"
            size="xs"
            color="neutral"
            variant="ghost"
            icon="i-lucide-external-link"
            :aria-label="t('marketing.metrics.openPost')"
            @click.stop
          />
        </template>
      </UTable>
    </template>
  </UDashboardPanel>
</template>
