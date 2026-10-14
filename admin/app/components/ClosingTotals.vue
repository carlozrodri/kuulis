<script setup lang="ts">
import type { ClosingTotals } from '~/types/api'
import { CHARGE_STATUSES, WALLET_ENTRY_KINDS } from '~/types/api'

/** What a monthly closing freezes (doc 17): ledger movements, top-ups, fees billed and wallet balances. */
const props = defineProps<{ totals: ClosingTotals }>()

const { t, locale } = useI18n()
const usdt = (value: string | number | null | undefined, signed = false) => formatUsdt(value, locale.value, signed)
const countAmount = (value: { count: number, amount: string } | undefined) =>
  t('closings.totals.countAmount', { n: formatNumber(value?.count ?? 0, locale.value), amount: usdt(value?.amount ?? 0) })

const entryRows = computed(() =>
  WALLET_ENTRY_KINDS.map(kind => ({ kind, ...(props.totals.entries?.[kind] ?? { count: 0, credits: '0.00', debits: '0.00' }) })),
)
const topUpRows = computed(() => [
  { label: t('closings.totals.credited'), value: countAmount(props.totals.top_ups?.credited), strong: true },
  { label: t('closings.totals.auto'), value: countAmount(props.totals.top_ups?.credited_auto) },
  { label: t('closings.totals.manual'), value: countAmount(props.totals.top_ups?.credited_manual) },
  { label: t('closings.totals.unmatched'), value: countAmount(props.totals.top_ups?.unmatched) },
])
</script>

<template>
  <div class="space-y-4">
    <dl class="grid gap-3 rounded-md bg-(--ui-bg-elevated) p-3 text-sm sm:grid-cols-4">
      <div>
        <dt class="text-(--ui-text-muted)">
          {{ t('closings.totals.feesCollected') }}
        </dt>
        <dd class="text-lg font-semibold tabular-nums">
          {{ usdt(totals.fees_collected) }}
        </dd>
      </div>
      <div>
        <dt class="text-(--ui-text-muted)">
          {{ t('closings.totals.opening') }}
        </dt>
        <dd class="tabular-nums">
          {{ usdt(totals.balances?.opening) }}
        </dd>
      </div>
      <div>
        <dt class="text-(--ui-text-muted)">
          {{ t('closings.totals.closing') }}
        </dt>
        <dd class="tabular-nums">
          {{ usdt(totals.balances?.closing) }}
        </dd>
      </div>
      <div>
        <dt class="text-(--ui-text-muted)">
          {{ t('closings.totals.net') }}
        </dt>
        <dd class="tabular-nums">
          {{ usdt(totals.balances?.net, true) }}
        </dd>
      </div>
    </dl>

    <div>
      <h4 class="mb-1 text-sm font-medium">
        {{ t('closings.totals.movements') }}
      </h4>
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-(--ui-border) text-left text-(--ui-text-muted)">
            <th class="py-1.5 font-medium">
              {{ t('closings.totals.kind') }}
            </th>
            <th class="py-1.5 text-right font-medium">
              {{ t('closings.totals.count') }}
            </th>
            <th class="py-1.5 text-right font-medium">
              {{ t('closings.totals.credits') }}
            </th>
            <th class="py-1.5 text-right font-medium">
              {{ t('closings.totals.debits') }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in entryRows"
            :key="row.kind"
            class="border-b border-(--ui-border) last:border-b-0"
          >
            <td class="py-1.5">
              {{ t(`wallet.kinds.${row.kind}`, row.kind) }}
            </td>
            <td class="py-1.5 text-right tabular-nums">
              {{ formatNumber(row.count, locale) }}
            </td>
            <td class="py-1.5 text-right tabular-nums">
              {{ usdt(row.credits) }}
            </td>
            <td class="py-1.5 text-right tabular-nums">
              {{ usdt(row.debits) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="grid gap-4 sm:grid-cols-2">
      <div>
        <h4 class="mb-1 text-sm font-medium">
          {{ t('closings.totals.topUps') }}
        </h4>
        <dl class="space-y-1 text-sm">
          <div
            v-for="row in topUpRows"
            :key="row.label"
            class="flex justify-between gap-2"
          >
            <dt class="text-(--ui-text-muted)">
              {{ row.label }}
            </dt>
            <dd
              class="tabular-nums"
              :class="row.strong ? 'font-medium' : ''"
            >
              {{ row.value }}
            </dd>
          </div>
        </dl>
      </div>
      <div>
        <h4 class="mb-1 text-sm font-medium">
          {{ t('closings.totals.charges') }}
        </h4>
        <dl class="space-y-1 text-sm">
          <div
            v-for="s in CHARGE_STATUSES"
            :key="s"
            class="flex justify-between gap-2"
          >
            <dt class="text-(--ui-text-muted)">
              {{ t(`subscriptions.statuses.${s}`) }}
            </dt>
            <dd class="tabular-nums">
              {{ t('closings.totals.countAmount', { n: formatNumber(totals.charges?.[s]?.count ?? 0, locale), amount: usdt(totals.charges?.[s]?.fees ?? 0) }) }}
            </dd>
          </div>
        </dl>
      </div>
    </div>
  </div>
</template>
