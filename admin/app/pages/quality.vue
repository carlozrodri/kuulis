<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { CancellationCount, Page, QualityLevel, QualityRole, QualityRow } from '~/types/api'
import { QUALITY_LEVELS } from '~/types/api'
import type { DayRange, RangePreset } from '~/utils/dates'

definePageMeta({ permission: 'quality.view' })

const { t, locale } = useI18n()
const { request } = useApi()
const route = useRoute()
const router = useRouter()
const apiError = useApiError()

// ---- People below the thresholds ------------------------------------------------------------

const role = ref<QualityRole>(route.query.role === 'passenger' ? 'passenger' : 'driver')
type LevelFilter = QualityLevel | 'all'
const level = ref<LevelFilter>('all')
const search = ref('')
const debouncedSearch = ref('')
let searchTimer: ReturnType<typeof setTimeout> | undefined
watch(search, (value) => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => (debouncedSearch.value = value.trim()), 300)
})
const page = ref(1)
const limit = 20

watch([debouncedSearch, role, level], () => {
  page.value = 1
})
// Keep the tab in the URL so "back" from a person returns to the same list.
watch(role, (value) => {
  router.replace({ query: { ...route.query, role: value } })
})

const query = computed(() => ({
  role: role.value,
  limit,
  offset: (page.value - 1) * limit,
  ...(debouncedSearch.value ? { q: debouncedSearch.value } : {}),
  ...(level.value !== 'all' ? { level: level.value } : {}),
}))

const { data, status, error } = await useAsyncData(
  'quality-users',
  () => request<Page<QualityRow>>('/admin/quality/users', { query: query.value }),
  { watch: [query] },
)

const tabs = computed(() => (['driver', 'passenger'] as const).map(value => ({ label: t(`quality.roles.${value}`), value })))
const levelItems = computed(() => [
  { label: t('quality.allLevels'), value: 'all' as LevelFilter },
  ...QUALITY_LEVELS.map(value => ({ label: t(`quality.levels.${value}`), value: value as LevelFilter })),
])

const columns = computed<TableColumn<QualityRow>[]>(() => [
  { id: 'person', header: t('quality.person') },
  { accessorKey: 'level', header: t('quality.level') },
  { accessorKey: 'cancel_rate', header: t('quality.cancelRate') },
  role.value === 'driver'
    ? { accessorKey: 'acceptance_rate', header: t('quality.acceptanceRate') }
    : { accessorKey: 'no_shows', header: t('quality.noShows') },
  { accessorKey: 'rating_avg', header: t('quality.rating') },
  { accessorKey: 'reasons', header: t('quality.reasonsLabel') },
  { accessorKey: 'paused_until', header: t('quality.pausedUntil') },
])

/** Drivers open their profile; passengers (or a driver without one) the user page. */
const personLink = (row: QualityRow) => (row.role === 'driver' ? driverLink(row.user_id, row.driver_profile_id) : `/users/${row.user_id}`)

// ---- Cancellations by reason ----------------------------------------------------------------

const presets: Exclude<RangePreset, 'custom'>[] = ['last30', 'last7', 'thisMonth', 'lastMonth']
const preset = ref<RangePreset>('last30')
const range = ref<DayRange>(presetRange('last30'))

const { data: cancellations, status: cancellationsStatus, error: cancellationsError } = await useAsyncData(
  'quality-cancellations',
  () => request<CancellationCount[]>('/admin/quality/cancellations', { query: { date_from: range.value.from, date_to: range.value.to } }),
  { watch: [range] },
)
const groups = computed(() => groupCancellations(cancellations.value ?? []))
const intFormat = (value: number) => formatNumber(value, locale.value)
</script>

<template>
  <UDashboardPanel id="quality">
    <template #header>
      <UDashboardNavbar :title="t('nav.quality')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
      </UDashboardNavbar>
      <UDashboardToolbar>
        <template #left>
          <UTabs
            v-model="role"
            :items="tabs"
            :content="false"
            size="sm"
            variant="link"
          />
        </template>
        <template #right>
          <USelect
            v-model="level"
            :items="levelItems"
            class="w-44"
            :aria-label="t('quality.level')"
          />
          <UInput
            v-model="search"
            icon="i-lucide-search"
            :placeholder="t('quality.search')"
            class="w-72 max-w-full"
          />
        </template>
      </UDashboardToolbar>
    </template>

    <template #body>
      <p class="text-sm text-(--ui-text-muted)">
        {{ t('quality.help') }}
      </p>
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
        :empty="t('quality.empty')"
        class="cursor-pointer"
        @select="(_e: Event, row: { original: QualityRow }) => navigateTo(personLink(row.original))"
      >
        <template #person-cell="{ row }">
          <NuxtLink
            :to="personLink(row.original)"
            class="font-medium text-primary hover:underline"
            @click.stop
          >
            {{ row.original.name || '—' }}
          </NuxtLink>
          <p class="text-xs text-(--ui-text-muted)">
            {{ row.original.email }}
          </p>
        </template>
        <template #level-cell="{ row }">
          <UBadge
            :color="qualityBadge(row.original.level).color"
            :variant="qualityBadge(row.original.level).variant"
          >
            {{ t(`quality.levels.${row.original.level}`) }}
          </UBadge>
        </template>
        <template #cancel_rate-cell="{ row }">
          <span class="tabular-nums">{{ formatPercent(row.original.cancel_rate, locale) }}</span>
          <p class="text-xs text-(--ui-text-muted)">
            {{ t('quality.cancelsOf', { n: row.original.cancels, total: row.original.role === 'driver' ? row.original.accepted : row.original.rides }) }}
          </p>
        </template>
        <template #acceptance_rate-cell="{ row }">
          <span class="tabular-nums">{{ formatPercent(row.original.acceptance_rate, locale) }}</span>
          <p class="text-xs text-(--ui-text-muted)">
            {{ t('quality.acceptedOf', { n: row.original.accepted, total: row.original.offers }) }}
          </p>
        </template>
        <template #no_shows-cell="{ row }">
          <span class="tabular-nums">{{ intFormat(row.original.no_shows) }}</span>
        </template>
        <template #rating_avg-cell="{ row }">
          <span v-if="row.original.rating_avg !== null">★ {{ formatRating(row.original.rating_avg) }}</span>
          <span v-else>—</span>
          <p class="text-xs text-(--ui-text-muted)">
            {{ t('quality.ratingCount', row.original.rating_count) }}
          </p>
        </template>
        <template #reasons-cell="{ row }">
          <div class="flex flex-wrap gap-1">
            <UBadge
              v-for="reason in row.original.reasons"
              :key="reason"
              color="neutral"
              variant="outline"
              size="sm"
            >
              {{ t(`quality.reasons.${reason}`) }}
            </UBadge>
          </div>
        </template>
        <template #paused_until-cell="{ row }">
          <UBadge
            v-if="row.original.paused_until"
            color="warning"
            variant="subtle"
            icon="i-lucide-pause"
          >
            {{ formatDate(row.original.paused_until, locale) }}
          </UBadge>
          <span
            v-else
            class="text-(--ui-text-muted)"
          >—</span>
        </template>
      </UTable>

      <div class="flex items-center justify-between border-t border-(--ui-border) pt-4">
        <span class="text-sm text-(--ui-text-muted)">
          {{ t('quality.total', data?.total ?? 0) }}
        </span>
        <UPagination
          v-model:page="page"
          :total="data?.total ?? 0"
          :items-per-page="limit"
        />
      </div>

      <UCard>
        <template #header>
          <div class="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 class="font-semibold">
                {{ t('quality.cancellations.title') }}
              </h2>
              <p class="text-sm text-(--ui-text-muted)">
                {{ t('quality.cancellations.help') }}
              </p>
            </div>
            <DateRangePicker
              v-model:preset="preset"
              v-model:range="range"
              :presets="presets"
            />
          </div>
        </template>
        <UAlert
          v-if="cancellationsError"
          color="error"
          variant="subtle"
          icon="i-lucide-circle-alert"
          :title="apiError(cancellationsError)"
        />
        <USkeleton
          v-else-if="cancellationsStatus === 'pending' && !cancellations"
          class="h-40"
        />
        <p
          v-else-if="!groups.length"
          class="text-sm text-(--ui-text-muted)"
        >
          {{ t('quality.cancellations.empty') }}
        </p>
        <div
          v-else
          class="grid gap-6 lg:grid-cols-2"
          :class="{ 'opacity-60': cancellationsStatus === 'pending' }"
        >
          <div
            v-for="group in groups"
            :key="group.side"
            class="overflow-x-auto"
          >
            <h3 class="mb-2 text-sm font-medium">
              {{ t(`quality.cancellations.bySide.${group.side}`) }}
            </h3>
            <table class="w-full text-left text-sm">
              <thead class="text-(--ui-text-muted)">
                <tr>
                  <th class="py-2 pr-4 font-medium">
                    {{ t('quality.cancellations.reason') }}
                  </th>
                  <th class="py-2 pr-4 text-right font-medium">
                    {{ t('quality.cancellations.total') }}
                  </th>
                  <th class="py-2 pr-4 text-right font-medium">
                    {{ t('quality.cancellations.counted') }}
                  </th>
                  <th class="py-2 text-right font-medium">
                    {{ t('quality.cancellations.reassigned') }}
                  </th>
                </tr>
              </thead>
              <tbody class="divide-y divide-(--ui-border)">
                <tr
                  v-for="row in group.rows"
                  :key="row.reason_code ?? 'none'"
                >
                  <td class="py-2 pr-4">
                    {{ t(cancelReasonKey(row.reason_code)) }}
                    <!-- Share of the side's cancellations. -->
                    <div class="mt-1 h-1 rounded bg-(--ui-bg-elevated)">
                      <div
                        class="h-1 rounded bg-primary"
                        :style="{ width: `${shareOf(row.total, group.total) * 100}%` }"
                      />
                    </div>
                  </td>
                  <td class="py-2 pr-4 text-right tabular-nums">
                    {{ intFormat(row.total) }}
                  </td>
                  <td class="py-2 pr-4 text-right tabular-nums">
                    {{ intFormat(row.counted) }}
                  </td>
                  <td class="py-2 text-right tabular-nums">
                    {{ intFormat(row.reassigned) }}
                  </td>
                </tr>
              </tbody>
              <tfoot class="border-t border-(--ui-border) font-medium">
                <tr>
                  <td class="py-2 pr-4">
                    {{ t('quality.cancellations.sum') }}
                  </td>
                  <td class="py-2 pr-4 text-right tabular-nums">
                    {{ intFormat(group.total) }}
                  </td>
                  <td class="py-2 pr-4 text-right tabular-nums">
                    {{ intFormat(group.counted) }}
                  </td>
                  <td class="py-2 text-right tabular-nums">
                    {{ intFormat(group.reassigned) }}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      </UCard>
    </template>
  </UDashboardPanel>
</template>
