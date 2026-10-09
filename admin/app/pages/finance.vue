<script setup lang="ts">
import type { FinanceSummary, TopUpStatus, WalletEntryKind } from '~/types/api'
import { TOP_UP_STATUSES, WALLET_ENTRY_KINDS } from '~/types/api'
import type { DayRange, RangePreset } from '~/utils/dates'

const { t, locale } = useI18n()
const { request, download } = useApi()
const route = useRoute()
const router = useRouter()
const toast = useToast()
const apiError = useApiError()

const presets: Exclude<RangePreset, 'custom'>[] = ['thisMonth', 'lastMonth', 'last7']
const queryString = (key: string) => (typeof route.query[key] === 'string' ? route.query[key] as string : '')

// Range in the URL (custom ranges survive a reload); this month by default.
const initialFrom = queryString('from')
const initialTo = queryString('to')
const initialCustom = isDay(initialFrom) && isDay(initialTo) && !rangeIssue({ from: initialFrom, to: initialTo })
const preset = ref<RangePreset>(initialCustom ? 'custom' : 'thisMonth')
const range = ref<DayRange>(initialCustom ? { from: initialFrom, to: initialTo } : presetRange('thisMonth'))
watch(range, (value) => {
  router.replace({ query: preset.value === 'custom' ? { from: value.from, to: value.to } : {} })
})
watch(preset, (value) => {
  if (value !== 'custom') router.replace({ query: {} })
})

const { data: summary, status, error } = await useAsyncData(
  'finance-summary',
  () => request<FinanceSummary>('/admin/finance/summary', { query: { from: range.value.from, to: range.value.to } }),
  { watch: [range] },
)

const showHelp = ref(true)

// ---- Cards --------------------------------------------------------------------------------------

const usdt = (value: string | number | null | undefined) => formatUsdt(value, locale.value)
const adjustmentsNet = computed(() => {
  const a = summary.value?.adjustments
  return a ? sumAmounts([a.credit, `-${a.debit}`]) : null
})

// ---- Chart --------------------------------------------------------------------------------------

const days = computed(() => (summary.value ? listDays(summary.value.from, summary.value.to) : []))
const chartSeries = computed(() => {
  const byDate = new Map((summary.value?.by_day ?? []).map(d => [d.date, d]))
  const values = (key: 'top_ups' | 'fees' | 'promo_credits') => days.value.map(day => Number(byDate.get(day)?.[key] ?? 0) || 0)
  return [
    { key: 'top_ups', label: t('finance.chart.topUps'), values: values('top_ups'), color: 'var(--chart-1)' },
    { key: 'fees', label: t('finance.chart.fees'), values: values('fees'), color: 'var(--chart-2)' },
    { key: 'promo_credits', label: t('finance.chart.promoCredits'), values: values('promo_credits'), color: 'var(--chart-3)' },
  ]
})
const dayLabels = computed(() => days.value.map(day => formatDay(day, locale.value)))
const dayTicks = computed(() => days.value.map(day => formatShortDay(day, locale.value)))
const compactUsd = (value: number) => new Intl.NumberFormat(locale.value, { notation: 'compact', maximumFractionDigits: 1 }).format(value)

// ---- CSV exports --------------------------------------------------------------------------------

const entryKind = ref<WalletEntryKind | 'all'>('all')
const topUpStatus = ref<TopUpStatus | 'all'>('all')
const entryKindItems = computed(() => [
  { label: t('finance.export.allKinds'), value: 'all' },
  ...WALLET_ENTRY_KINDS.map(value => ({ label: t(`wallet.kinds.${value}`), value })),
])
const topUpStatusItems = computed(() => [
  { label: t('topUps.allStatuses'), value: 'all' },
  ...TOP_UP_STATUSES.map(value => ({ label: t(`topUps.statuses.${value}`), value })),
])

const downloading = ref<'entries' | 'top-ups' | null>(null)

async function exportCsv(which: 'entries' | 'top-ups') {
  const { from, to } = range.value
  const filter = which === 'entries' ? entryKind.value : topUpStatus.value
  const name = which === 'entries' ? 'movimientos' : 'recargas'
  const filename = `kuulis-${name}${filter !== 'all' ? `-${filter}` : ''}-${from}_${to}.csv`
  const query = {
    from,
    to,
    ...(filter !== 'all' ? { [which === 'entries' ? 'kind' : 'status']: filter } : {}),
  }
  downloading.value = which
  try {
    await download(`/admin/finance/${which}.csv`, filename, query)
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    downloading.value = null
  }
}
</script>

<template>
  <UDashboardPanel id="finance">
    <template #header>
      <UDashboardNavbar :title="t('nav.finance')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton
            icon="i-lucide-circle-help"
            color="neutral"
            variant="ghost"
            :aria-label="t('finance.help.toggle')"
            :aria-pressed="showHelp"
            @click="showHelp = !showHelp"
          />
        </template>
      </UDashboardNavbar>
      <UDashboardToolbar>
        <template #left>
          <DateRangePicker
            v-model:preset="preset"
            v-model:range="range"
            :presets="presets"
          />
        </template>
        <template #right>
          <span class="text-xs text-(--ui-text-muted)">{{ t('range.caracas') }}</span>
        </template>
      </UDashboardToolbar>
    </template>

    <template #body>
      <UAlert
        v-if="showHelp"
        color="info"
        variant="subtle"
        icon="i-lucide-info"
        :title="t('finance.help.title')"
      >
        <template #description>
          <ol class="list-decimal space-y-1 pl-4">
            <li>{{ t('finance.help.step1') }}</li>
            <li>{{ t('finance.help.step2') }}</li>
            <li>{{ t('finance.help.step3') }}</li>
            <li>{{ t('finance.help.step4') }}</li>
          </ol>
          <p class="mt-2">
            {{ t('finance.help.balances') }}
          </p>
        </template>
      </UAlert>

      <UAlert
        v-if="error"
        color="error"
        variant="subtle"
        icon="i-lucide-circle-alert"
        :title="apiError(error)"
      />

      <div
        v-if="status === 'pending' && !summary"
        class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"
      >
        <USkeleton
          v-for="n in 8"
          :key="n"
          class="h-28"
        />
      </div>

      <template v-if="summary">
        <div
          class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"
          :class="{ 'opacity-60': status === 'pending' }"
        >
          <!-- Top-ups credited -->
          <UCard class="sm:col-span-2">
            <p class="text-sm text-(--ui-text-muted)">
              {{ t('finance.cards.topUpsCompleted') }}
            </p>
            <p class="text-2xl font-semibold tabular-nums">
              {{ usdt(summary.top_ups.completed.amount) }}
            </p>
            <p class="text-xs text-(--ui-text-muted)">
              {{ t('finance.count', { n: summary.top_ups.completed.count }) }} · {{ t('finance.cards.byCompletedAt') }}
            </p>
            <div class="mt-3 grid grid-cols-2 gap-3 border-t border-(--ui-border) pt-3 text-sm">
              <div>
                <p class="text-(--ui-text-muted)">
                  {{ t('finance.cards.auto') }}
                </p>
                <p class="font-medium tabular-nums">
                  {{ usdt(summary.top_ups.completed_auto.amount) }}
                </p>
                <p class="text-xs text-(--ui-text-muted)">
                  {{ t('finance.count', { n: summary.top_ups.completed_auto.count }) }}
                </p>
              </div>
              <div>
                <p class="text-(--ui-text-muted)">
                  {{ t('finance.cards.manual') }}
                </p>
                <p class="font-medium tabular-nums">
                  {{ usdt(summary.top_ups.completed_manual.amount) }}
                </p>
                <p class="text-xs text-(--ui-text-muted)">
                  {{ t('finance.count', { n: summary.top_ups.completed_manual.count }) }}
                </p>
              </div>
            </div>
          </UCard>

          <!-- Top-ups not credited -->
          <UCard class="sm:col-span-2">
            <p class="text-sm text-(--ui-text-muted)">
              {{ t('finance.cards.topUpsOther') }}
            </p>
            <ul class="mt-2 divide-y divide-(--ui-border) text-sm">
              <li
                v-for="key in (['pending', 'unmatched', 'rejected'] as const)"
                :key="key"
                class="flex items-center justify-between gap-2 py-1.5"
              >
                <NuxtLink
                  :to="{ path: '/top-ups', query: { status: key } }"
                  class="flex items-center gap-2 hover:underline"
                >
                  <UBadge
                    :color="topUpStatusColor[key]"
                    variant="subtle"
                    size="sm"
                  >
                    {{ t(`topUps.statuses.${key}`) }}
                  </UBadge>
                  <span class="text-xs text-(--ui-text-muted)">{{ t('finance.count', { n: summary.top_ups[key].count }) }}</span>
                </NuxtLink>
                <span class="font-medium tabular-nums">{{ usdt(summary.top_ups[key].amount) }}</span>
              </li>
            </ul>
            <p class="mt-1 text-xs text-(--ui-text-muted)">
              {{ t('finance.cards.byCreatedAt') }}
            </p>
          </UCard>

          <!-- Fees -->
          <UCard>
            <p class="text-sm text-(--ui-text-muted)">
              {{ t('finance.cards.feesCollected') }}
            </p>
            <p class="text-2xl font-semibold tabular-nums">
              {{ usdt(summary.fees.collected) }}
            </p>
            <p class="mt-2 text-sm">
              <NuxtLink
                :to="{ path: '/subscriptions', query: { status: 'pending', month: 'all' } }"
                class="hover:underline"
              >
                {{ t('finance.cards.feesPending', { amount: usdt(summary.fees.pending) }) }}
              </NuxtLink>
            </p>
            <p class="text-xs text-(--ui-text-muted)">
              {{ t('finance.cards.feesPendingHelp') }} · {{ t('finance.cards.waived', { n: summary.fees.waived_count }) }}
            </p>
          </UCard>

          <!-- Promo credits -->
          <UCard>
            <p class="text-sm text-(--ui-text-muted)">
              {{ t('finance.cards.promoCredits') }}
            </p>
            <p class="text-2xl font-semibold tabular-nums">
              {{ usdt(summary.promo_credits) }}
            </p>
            <p class="mt-2 text-xs text-(--ui-text-muted)">
              {{ t('finance.cards.promoCreditsHelp') }}
            </p>
          </UCard>

          <!-- Adjustments -->
          <UCard>
            <p class="text-sm text-(--ui-text-muted)">
              {{ t('finance.cards.adjustments') }}
            </p>
            <p class="text-2xl font-semibold tabular-nums">
              {{ formatUsdt(adjustmentsNet, locale, true) }}
            </p>
            <p class="mt-2 text-sm tabular-nums">
              <span class="text-success">+{{ usdt(summary.adjustments.credit) }}</span>
              ·
              <span class="text-error">−{{ usdt(summary.adjustments.debit) }}</span>
            </p>
          </UCard>

          <!-- Transfers -->
          <UCard>
            <p class="text-sm text-(--ui-text-muted)">
              {{ t('finance.cards.transfers') }}
            </p>
            <p class="text-2xl font-semibold tabular-nums">
              {{ usdt(summary.transfers.amount) }}
            </p>
            <p class="mt-2 text-xs text-(--ui-text-muted)">
              {{ t('finance.count', { n: summary.transfers.count }) }} · {{ t('finance.cards.transfersHelp') }}
            </p>
          </UCard>

          <!-- Wallet balances -->
          <UCard class="sm:col-span-2 xl:col-span-4">
            <div class="flex flex-wrap items-center justify-between gap-4">
              <div class="flex items-center gap-3">
                <UIcon
                  name="i-lucide-piggy-bank"
                  class="size-8 text-primary"
                />
                <div>
                  <p class="text-sm text-(--ui-text-muted)">
                    {{ t('finance.cards.walletBalances') }}
                  </p>
                  <p class="text-2xl font-semibold tabular-nums">
                    {{ usdt(summary.wallet_balances) }}
                  </p>
                </div>
              </div>
              <p class="max-w-xl text-xs text-(--ui-text-muted)">
                {{ t('finance.cards.walletBalancesHelp') }}
              </p>
            </div>
          </UCard>
        </div>

        <UCard>
          <template #header>
            <h2 class="font-semibold">
              {{ t('finance.chart.title') }}
            </h2>
          </template>
          <SimpleChart
            :title="t('finance.chart.title')"
            :labels="dayLabels"
            :ticks="dayTicks"
            :series="chartSeries"
            :format="usdt"
            :axis-format="compactUsd"
          />
        </UCard>
      </template>

      <UCard>
        <template #header>
          <div>
            <h2 class="font-semibold">
              {{ t('finance.export.title') }}
            </h2>
            <p class="text-xs text-(--ui-text-muted)">
              {{ t('finance.export.help', { from: range.from, to: range.to }) }}
            </p>
          </div>
        </template>
        <div class="grid gap-6 md:grid-cols-2">
          <div class="space-y-2">
            <p class="font-medium">
              {{ t('finance.export.entries') }}
            </p>
            <p class="text-xs text-(--ui-text-muted)">
              {{ t('finance.export.entriesHelp') }}
            </p>
            <div class="flex flex-wrap gap-2">
              <USelect
                v-model="entryKind"
                :items="entryKindItems"
                class="w-56"
                :aria-label="t('wallet.kind')"
              />
              <UButton
                icon="i-lucide-download"
                :label="t('finance.export.download')"
                :loading="downloading === 'entries'"
                @click="exportCsv('entries')"
              />
            </div>
          </div>
          <div class="space-y-2">
            <p class="font-medium">
              {{ t('finance.export.topUps') }}
            </p>
            <p class="text-xs text-(--ui-text-muted)">
              {{ t('finance.export.topUpsHelp') }}
            </p>
            <div class="flex flex-wrap gap-2">
              <USelect
                v-model="topUpStatus"
                :items="topUpStatusItems"
                class="w-56"
                :aria-label="t('topUps.status')"
              />
              <UButton
                icon="i-lucide-download"
                :label="t('finance.export.download')"
                :loading="downloading === 'top-ups'"
                @click="exportCsv('top-ups')"
              />
            </div>
          </div>
        </div>
      </UCard>
    </template>
  </UDashboardPanel>
</template>
