<script setup lang="ts">
import type { TableColumn, TableRow } from '@nuxt/ui'
import type { AdminCharge, ChargePage, ChargeStatus, SubscriptionRunResult } from '~/types/api'
import { CHARGE_STATUSES } from '~/types/api'

const { t, locale } = useI18n()
const { request } = useApi()
const auth = useAuth()
const route = useRoute()
const router = useRouter()
const toast = useToast()
const apiError = useApiError()

const queryString = (key: string) => (typeof route.query[key] === 'string' ? route.query[key] as string : '')

type Section = 'charges' | 'schedules'
const section = ref<Section>(queryString('tab') === 'schedules' ? 'schedules' : 'charges')
const sectionTabs = computed(() => [
  { label: t('subscriptions.charges'), value: 'charges', icon: 'i-lucide-receipt' },
  { label: t('subscriptions.schedules.title'), value: 'schedules', icon: 'i-lucide-layers' },
])

// ---- Charges filters (in the URL) -----------------------------------------------------------

const thisMonth = caracasMonth()
/** Charges are created on day 1 for the month before, so that is the useful default. */
const lastClosed = addMonths(thisMonth, -1)

type StatusFilter = ChargeStatus | 'all'
const statusFilters: StatusFilter[] = ['all', ...CHARGE_STATUSES]
const initialStatus = queryString('status') as StatusFilter
const status = ref<StatusFilter>(statusFilters.includes(initialStatus) ? initialStatus : 'all')
const initialMonth = queryString('month')
const month = ref<string>(initialMonth === 'all' || isMonth(initialMonth) ? initialMonth : lastClosed)
const search = ref(queryString('q'))
const debouncedSearch = ref(search.value.trim())
const page = ref(Math.max(1, Number(queryString('page')) || 1))
const limit = 25

let searchTimer: ReturnType<typeof setTimeout> | undefined
watch(search, (value) => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => (debouncedSearch.value = value.trim()), 300)
})
watch([debouncedSearch, status, month], () => {
  page.value = 1
})
watch([section, debouncedSearch, status, month, page], () => {
  router.replace({
    query: {
      ...(section.value !== 'charges' ? { tab: section.value } : {}),
      ...(status.value !== 'all' ? { status: status.value } : {}),
      ...(month.value !== lastClosed ? { month: month.value } : {}),
      ...(debouncedSearch.value ? { q: debouncedSearch.value } : {}),
      ...(page.value > 1 ? { page: String(page.value) } : {}),
    },
  })
})

const baseFilters = computed(() => ({
  ...(month.value !== 'all' ? { month: month.value } : {}),
  ...(debouncedSearch.value ? { q: debouncedSearch.value } : {}),
}))
const query = computed(() => ({
  limit,
  offset: (page.value - 1) * limit,
  ...baseFilters.value,
  ...(status.value !== 'all' ? { status: status.value } : {}),
}))

const { data, status: fetchStatus, error, refresh } = await useAsyncData(
  'subscription-charges',
  () => request<ChargePage>('/admin/subscriptions/charges', { query: query.value }),
  { watch: [query] },
)

// ---- Totals ---------------------------------------------------------------------------------

/**
 * Totals per status for the month and search, independent of the status tab. One request per status: `total`
 * gives the count and the API's `totals` the fee sum. The pending one loads up to a page of rows to count the
 * blocked drivers. Against an API without `totals`, the panel adds up every row instead (small at launch).
 */
const SUMMARY_PAGE = 100
const SUMMARY_MAX_PAGES = 20
interface Summary {
  paid: { count: number, fee: number }
  pending: { count: number, fee: number, overdue: number }
  waived: { count: number }
  partial: boolean
}

async function summaryFromRows(): Promise<Summary> {
  const items: AdminCharge[] = []
  let total = Infinity
  for (let i = 0; i < SUMMARY_MAX_PAGES && items.length < total; i++) {
    const chunk = await request<ChargePage>('/admin/subscriptions/charges', {
      query: { ...baseFilters.value, limit: SUMMARY_PAGE, offset: i * SUMMARY_PAGE },
    })
    items.push(...chunk.items)
    total = chunk.total
    if (!chunk.items.length) break
  }
  const of = (s: ChargeStatus) => items.filter(c => c.status === s)
  return {
    paid: { count: of('paid').length, fee: sumAmounts(of('paid').map(c => c.fee)) },
    pending: { count: of('pending').length, fee: sumAmounts(of('pending').map(c => c.fee)), overdue: of('pending').filter(c => isOverdue(c)).length },
    waived: { count: of('waived').length },
    partial: items.length < total,
  }
}

const { data: summary, status: summaryStatus, refresh: refreshSummary } = await useAsyncData(
  'subscription-charges-summary',
  async (): Promise<Summary | null> => {
    const byStatus = (s: ChargeStatus, size: number) =>
      request<ChargePage>('/admin/subscriptions/charges', { query: { ...baseFilters.value, status: s, limit: size, offset: 0 } })
    const [pending, paid, waived] = await Promise.all([byStatus('pending', SUMMARY_PAGE), byStatus('paid', 1), byStatus('waived', 1)])
    if (!pending.totals || !paid.totals) return summaryFromRows()
    return {
      paid: { count: paid.total, fee: sumAmounts([paid.totals.paid]) },
      pending: { count: pending.total, fee: sumAmounts([pending.totals.pending]), overdue: pending.items.filter(c => isOverdue(c)).length },
      waived: { count: waived.total },
      partial: pending.items.length < pending.total,
    }
  },
  { watch: [baseFilters] },
)

// ---- Table ----------------------------------------------------------------------------------

const statusTabs = computed(() =>
  statusFilters.map(value => ({
    label: value === 'all' ? t('subscriptions.allStatuses') : t(`subscriptions.statuses.${value}`),
    value,
  })),
)
const monthItems = computed(() => [
  { label: t('subscriptions.allMonths'), value: 'all' },
  ...monthsBack(thisMonth, 24).map(m => ({ label: formatMonth(m, locale.value), value: m })),
])

const columns = computed<TableColumn<AdminCharge>[]>(() => [
  { id: 'driver', header: t('subscriptions.driver') },
  { accessorKey: 'month', header: t('subscriptions.month') },
  { accessorKey: 'earnings', header: t('subscriptions.earnings') },
  { accessorKey: 'fee', header: t('subscriptions.fee') },
  { accessorKey: 'status', header: t('subscriptions.status') },
  { id: 'dates', header: t('subscriptions.dates') },
  ...(auth.isAdmin.value ? [{ id: 'actions', header: '' }] : []),
])
const tableMeta = {
  class: { tr: (row: TableRow<AdminCharge>) => (isOverdue(row.original) ? 'bg-error/5' : '') },
}

// ---- Waive (admin) --------------------------------------------------------------------------

const waiving = ref<AdminCharge | null>(null)
const waiveReason = ref('')
const waiveBusy = ref(false)
const waiveOpen = computed({
  get: () => waiving.value !== null,
  set: (open: boolean) => {
    if (!open) waiving.value = null
  },
})
function askWaive(charge: AdminCharge) {
  waiveReason.value = ''
  waiving.value = charge
}
async function waive() {
  const charge = waiving.value
  const reason = waiveReason.value.trim()
  if (!charge || !reason) return
  waiveBusy.value = true
  try {
    await request(`/admin/subscriptions/charges/${charge.id}/waive`, { method: 'POST', body: { reason } })
    toast.add({ title: t('subscriptions.waive.done'), color: 'success' })
    waiving.value = null
    await Promise.all([refresh(), refreshSummary()])
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    waiveBusy.value = false
  }
}

// ---- Run a closed month (admin) ---------------------------------------------------------------

const runOpen = ref(false)
const runMonth = ref(lastClosed)
const runBusy = ref(false)
const runResult = ref<SubscriptionRunResult | null>(null)
const closedMonthItems = computed(() => monthsBack(lastClosed, 12).map(m => ({ label: formatMonth(m, locale.value), value: m })))

function askRun() {
  runMonth.value = month.value !== 'all' && month.value < thisMonth ? month.value : lastClosed
  runResult.value = null
  runOpen.value = true
}
async function run() {
  if (!isMonth(runMonth.value) || runMonth.value >= thisMonth) return
  runBusy.value = true
  try {
    runResult.value = await request<SubscriptionRunResult>('/admin/subscriptions/run', { method: 'POST', body: { month: runMonth.value } })
    toast.add({ title: t('subscriptions.run.done', { month: formatMonth(runMonth.value, locale.value) }), color: 'success' })
    if (month.value !== runMonth.value) month.value = runMonth.value
    else await Promise.all([refresh(), refreshSummary()])
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    runBusy.value = false
  }
}
</script>

<template>
  <UDashboardPanel id="subscriptions">
    <template #header>
      <UDashboardNavbar :title="t('nav.subscriptions')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton
            v-if="auth.isAdmin.value && section === 'charges'"
            icon="i-lucide-play"
            :label="t('subscriptions.run.button')"
            @click="askRun"
          />
        </template>
      </UDashboardNavbar>
      <UDashboardToolbar>
        <template #left>
          <UTabs
            v-model="section"
            :items="sectionTabs"
            :content="false"
            size="sm"
            variant="link"
          />
        </template>
      </UDashboardToolbar>
    </template>

    <template #body>
      <FeeSchedules v-if="section === 'schedules'" />

      <template v-else>
        <div class="flex flex-wrap items-center justify-between gap-3">
          <UTabs
            v-model="status"
            :items="statusTabs"
            :content="false"
            size="sm"
            variant="pill"
          />
          <div class="flex flex-wrap gap-2">
            <USelect
              v-model="month"
              :items="monthItems"
              class="w-52 capitalize"
              :aria-label="t('subscriptions.month')"
            />
            <UInput
              v-model="search"
              icon="i-lucide-search"
              :placeholder="t('subscriptions.search')"
              class="w-64 max-w-full"
            />
          </div>
        </div>

        <div class="grid gap-4 sm:grid-cols-3">
          <UCard>
            <p class="text-sm text-(--ui-text-muted)">
              {{ t('subscriptions.totals.paid') }}
            </p>
            <USkeleton
              v-if="!summary && summaryStatus === 'pending'"
              class="mt-1 h-8 w-32"
            />
            <template v-else>
              <p class="text-2xl font-semibold tabular-nums">
                {{ formatUsdt(summary?.paid.fee ?? 0, locale) }}
              </p>
              <p class="text-xs text-(--ui-text-muted)">
                {{ t('subscriptions.totals.charges', { n: summary?.paid.count ?? 0 }) }}
              </p>
            </template>
          </UCard>
          <UCard>
            <p class="text-sm text-(--ui-text-muted)">
              {{ t('subscriptions.totals.pending') }}
            </p>
            <USkeleton
              v-if="!summary && summaryStatus === 'pending'"
              class="mt-1 h-8 w-32"
            />
            <template v-else>
              <p class="text-2xl font-semibold tabular-nums">
                {{ formatUsdt(summary?.pending.fee ?? 0, locale) }}
              </p>
              <p class="text-xs text-(--ui-text-muted)">
                {{ t('subscriptions.totals.charges', { n: summary?.pending.count ?? 0 }) }}
                <span
                  v-if="summary?.pending.overdue"
                  class="font-medium text-error"
                >· {{ t('subscriptions.totals.blocked', { n: summary.pending.overdue }) }}</span>
              </p>
            </template>
          </UCard>
          <UCard>
            <p class="text-sm text-(--ui-text-muted)">
              {{ t('subscriptions.totals.waived') }}
            </p>
            <USkeleton
              v-if="!summary && summaryStatus === 'pending'"
              class="mt-1 h-8 w-32"
            />
            <template v-else>
              <p class="text-2xl font-semibold tabular-nums">
                {{ summary?.waived.count ?? 0 }}
              </p>
              <p class="text-xs text-(--ui-text-muted)">
                {{ t('subscriptions.totals.waivedHelp') }}
              </p>
            </template>
          </UCard>
        </div>
        <p
          v-if="summary?.partial"
          class="text-xs text-warning"
        >
          {{ t('subscriptions.totals.partial') }}
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
          :meta="tableMeta"
          :loading="fetchStatus === 'pending'"
          :empty="t('common.empty')"
        >
          <template #driver-cell="{ row }">
            <PartyCell :party="ownerOf(row.original)" />
          </template>
          <template #month-cell="{ row }">
            <span class="whitespace-nowrap capitalize">{{ formatMonth(row.original.month, locale) }}</span>
          </template>
          <template #earnings-cell="{ row }">
            <span class="tabular-nums">{{ formatMoney(row.original.earnings, locale) }}</span>
          </template>
          <template #fee-cell="{ row }">
            <span class="whitespace-nowrap font-medium tabular-nums">{{ formatUsdt(row.original.fee, locale) }}</span>
            <p
              v-if="row.original.free_period"
              class="text-xs text-(--ui-text-muted)"
            >
              {{ t('subscriptions.freePeriod') }}
            </p>
          </template>
          <template #status-cell="{ row }">
            <UBadge
              v-if="isOverdue(row.original)"
              color="error"
              variant="subtle"
              icon="i-lucide-lock"
            >
              {{ t('subscriptions.blocked') }}
            </UBadge>
            <UBadge
              v-else
              :color="chargeStatusColor[row.original.status] ?? 'neutral'"
              variant="subtle"
            >
              {{ t(`subscriptions.statuses.${row.original.status}`, row.original.status) }}
            </UBadge>
            <p
              v-if="row.original.status === 'waived' && row.original.waived_reason"
              class="max-w-xs truncate text-xs text-(--ui-text-muted)"
              :title="row.original.waived_reason"
            >
              {{ row.original.waived_reason }}
            </p>
          </template>
          <template #dates-cell="{ row }">
            <p
              v-if="row.original.status === 'pending'"
              class="text-xs whitespace-nowrap"
              :class="isOverdue(row.original) ? 'font-medium text-error' : ''"
            >
              {{ t('subscriptions.dueAt') }}: {{ formatDate(row.original.due_at, locale) }}
            </p>
            <p
              v-else-if="row.original.status === 'paid'"
              class="text-xs whitespace-nowrap text-(--ui-text-muted)"
            >
              {{ t('subscriptions.paidAt') }}: {{ formatDate(row.original.paid_at, locale) }}
            </p>
            <span v-else>—</span>
          </template>
          <template #actions-cell="{ row }">
            <div class="flex justify-end">
              <UButton
                v-if="row.original.status === 'pending'"
                size="xs"
                icon="i-lucide-hand-heart"
                color="neutral"
                variant="soft"
                :label="t('subscriptions.waive.button')"
                @click="askWaive(row.original)"
              />
            </div>
          </template>
        </UTable>

        <div class="flex items-center justify-between border-t border-(--ui-border) pt-4">
          <span class="text-sm text-(--ui-text-muted)">
            {{ t('subscriptions.total', { n: data?.total ?? 0 }) }}
          </span>
          <UPagination
            v-model:page="page"
            :total="data?.total ?? 0"
            :items-per-page="limit"
          />
        </div>
      </template>

      <UModal
        v-model:open="waiveOpen"
        :title="t('subscriptions.waive.title')"
        :description="t('subscriptions.waive.help')"
      >
        <template #body>
          <form
            v-if="waiving"
            id="waive-form"
            class="space-y-4"
            @submit.prevent="waive"
          >
            <p class="text-sm">
              {{ t('subscriptions.waive.summary', {
                name: ownerOf(waiving)?.name || ownerOf(waiving)?.email || '—',
                month: formatMonth(waiving.month, locale),
                fee: formatUsdt(waiving.fee, locale),
              }) }}
            </p>
            <UFormField
              :label="t('subscriptions.waive.reason')"
              required
            >
              <UTextarea
                v-model="waiveReason"
                class="w-full"
                :rows="3"
                maxlength="500"
                required
              />
            </UFormField>
          </form>
        </template>
        <template #footer>
          <div class="flex w-full justify-end gap-2">
            <UButton
              color="neutral"
              variant="ghost"
              :label="t('common.cancel')"
              @click="waiveOpen = false"
            />
            <UButton
              type="submit"
              form="waive-form"
              :label="t('subscriptions.waive.button')"
              :disabled="!waiveReason.trim()"
              :loading="waiveBusy"
            />
          </div>
        </template>
      </UModal>

      <UModal
        v-model:open="runOpen"
        :title="t('subscriptions.run.title')"
        :description="t('subscriptions.run.help')"
      >
        <template #body>
          <div class="space-y-4">
            <UFormField
              :label="t('subscriptions.month')"
              required
            >
              <USelect
                v-model="runMonth"
                :items="closedMonthItems"
                class="w-60 capitalize"
                :disabled="runBusy"
              />
            </UFormField>
            <UAlert
              v-if="!runResult"
              color="warning"
              variant="subtle"
              icon="i-lucide-triangle-alert"
              :title="t('subscriptions.run.confirm', { month: formatMonth(runMonth, locale) })"
            />
            <dl
              v-else
              class="grid grid-cols-4 gap-3 rounded-md bg-(--ui-bg-elevated) p-3 text-sm"
            >
              <div
                v-for="key in (['created', 'paid', 'pending', 'waived'] as const)"
                :key="key"
              >
                <dt class="text-(--ui-text-muted)">
                  {{ t(`subscriptions.run.result.${key}`) }}
                </dt>
                <dd class="text-lg font-semibold tabular-nums">
                  {{ runResult[key] }}
                </dd>
              </div>
            </dl>
          </div>
        </template>
        <template #footer>
          <div class="flex w-full justify-end gap-2">
            <UButton
              color="neutral"
              variant="ghost"
              :label="runResult ? t('subscriptions.run.close') : t('common.cancel')"
              @click="runOpen = false"
            />
            <UButton
              v-if="!runResult"
              icon="i-lucide-play"
              :label="t('subscriptions.run.submit')"
              :loading="runBusy"
              @click="run"
            />
          </div>
        </template>
      </UModal>
    </template>
  </UDashboardPanel>
</template>
