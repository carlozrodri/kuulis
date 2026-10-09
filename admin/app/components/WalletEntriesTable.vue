<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { WalletEntry } from '~/types/api'

defineProps<{ entries: WalletEntry[], loading?: boolean }>()

const { t, locale } = useI18n()

const columns = computed<TableColumn<WalletEntry>[]>(() => [
  { accessorKey: 'created_at', header: t('wallet.date') },
  { accessorKey: 'kind', header: t('wallet.kind') },
  { id: 'detail', header: t('wallet.detail.title') },
  { accessorKey: 'amount', header: t('wallet.amount') },
  { accessorKey: 'balance_after', header: t('wallet.balanceAfter') },
])

/** Main line of the "detail" column, built from `details` so it follows the panel language. */
function describe(entry: WalletEntry): string {
  const d = entry.details ?? {}
  switch (entry.kind) {
    case 'promo_credit':
      return t('wallet.detail.promo', { name: entry.description || '—', passenger: d.passenger_name || '—' })
    case 'top_up':
      return d.reference ? t('wallet.detail.topUpRef', { reference: d.reference }) : t('wallet.detail.topUp')
    case 'transfer_in':
      return t('wallet.detail.transferIn', { name: d.counterpart_name || '—' })
    case 'transfer_out':
      return t('wallet.detail.transferOut', { name: d.counterpart_name || '—' })
    case 'subscription_fee':
      return t('wallet.detail.fee', { month: formatMonth(d.month, locale.value) })
    case 'adjustment':
      return d.reason || entry.description || '—'
    default:
      return entry.description || '—'
  }
}

/** Secondary line: the transfer note. */
const secondary = (entry: WalletEntry) => ((entry.kind === 'transfer_in' || entry.kind === 'transfer_out') && entry.details?.note) || null
</script>

<template>
  <UTable
    :data="entries"
    :columns="columns"
    :loading="loading"
    :empty="t('wallet.noEntries')"
  >
    <template #created_at-cell="{ row }">
      <span class="whitespace-nowrap">{{ formatDate(row.original.created_at, locale) }}</span>
    </template>
    <template #kind-cell="{ row }">
      <UBadge
        :color="walletEntryColor[row.original.kind] ?? 'neutral'"
        variant="subtle"
        size="sm"
      >
        {{ t(`wallet.kinds.${row.original.kind}`, row.original.kind) }}
      </UBadge>
    </template>
    <template #detail-cell="{ row }">
      <p class="max-w-sm truncate">
        <NuxtLink
          v-if="row.original.ride_id"
          :to="`/rides/${row.original.ride_id}`"
          class="text-primary hover:underline"
        >
          {{ describe(row.original) }}
        </NuxtLink>
        <span
          v-else
          :title="describe(row.original)"
        >{{ describe(row.original) }}</span>
      </p>
      <p
        v-if="secondary(row.original)"
        class="max-w-sm truncate text-xs text-(--ui-text-muted)"
      >
        «{{ secondary(row.original) }}»
      </p>
    </template>
    <template #amount-cell="{ row }">
      <span
        class="whitespace-nowrap font-medium tabular-nums"
        :class="entryAmountClass(row.original)"
      >{{ formatUsdt(row.original.amount, locale, true) }}</span>
    </template>
    <template #balance_after-cell="{ row }">
      <span class="whitespace-nowrap tabular-nums text-(--ui-text-muted)">{{ formatUsdt(row.original.balance_after, locale) }}</span>
    </template>
  </UTable>
</template>
