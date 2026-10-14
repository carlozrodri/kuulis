<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { Closing, ClosingTotals, InvariantsResult, LedgerIssue } from '~/types/api'

definePageMeta({ permission: 'finance.view' })

const { t, locale } = useI18n()
const { request } = useApi()
const auth = useAuth()
const toast = useToast()
const apiError = useApiError()

const canClose = computed(() => auth.can('finance.close'))
const usdt = (value: string | number | null | undefined) => formatUsdt(value, locale.value)

// ---- Ledger invariants ------------------------------------------------------------------------

const { data: invariants, status: invariantsStatus } = await useAsyncData(
  'finance-invariants',
  () => request<InvariantsResult | null>('/admin/finance/invariants'),
)
const ISSUES_SHOWN = 10
const shownIssues = computed(() => invariants.value?.issues.slice(0, ISSUES_SHOWN) ?? [])
const issueLabel = (issue: LedgerIssue) => t(`closings.invariants.kinds.${issue.kind}`, issue.kind)
/** The extra keys of an issue (balances, ids) as a compact line. */
const issueDetail = (issue: LedgerIssue) =>
  Object.entries(issue)
    .filter(([key, value]) => key !== 'kind' && key !== 'user_id' && value !== null && value !== undefined)
    .map(([key, value]) => `${key}: ${String(value)}`)
    .join(' · ')

const checking = ref(false)
async function runInvariants() {
  checking.value = true
  try {
    invariants.value = await request<InvariantsResult>('/admin/finance/invariants/run', { method: 'POST' })
    toast.add({ title: t('closings.invariants.ran'), color: invariants.value.ok ? 'success' : 'warning' })
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    checking.value = false
  }
}

// ---- Closings -----------------------------------------------------------------------------------

const { data: closings, status, error, refresh } = await useAsyncData(
  'finance-closings',
  () => request<Closing[]>('/admin/finance/closings'),
)
const tampered = computed(() => (closings.value ?? []).some(c => !c.hash_ok))

const columns = computed<TableColumn<Closing>[]>(() => [
  { accessorKey: 'month', header: t('closings.month') },
  { id: 'fees', header: t('closings.feesCollected') },
  { id: 'topUps', header: t('closings.topUpsCredited') },
  { id: 'balance', header: t('closings.closingBalance') },
  { id: 'status', header: t('closings.status') },
  { accessorKey: 'closed_at', header: t('closings.closedAt') },
  { id: 'actions', header: '' },
])

const selectedMonth = ref<string | null>(null)
const selected = computed(() => closings.value?.find(c => c.month === selectedMonth.value) ?? null)
const detailOpen = computed({
  get: () => selected.value !== null,
  set: (open: boolean) => {
    if (!open) selectedMonth.value = null
  },
})
function closingChanged(updated: Closing) {
  if (!closings.value) return
  closings.value = closings.value.map(c => (c.month === updated.month ? updated : c))
}

// ---- Close a month --------------------------------------------------------------------------------

const thisMonth = caracasMonth()
const closeOpen = ref(false)
const closeMonth = ref('')
const closable = computed(() => closableMonths((closings.value ?? []).map(c => c.month), thisMonth))
const closableItems = computed(() => closable.value.map(m => ({ label: formatMonth(m, locale.value), value: m })))
const preview = ref<ClosingTotals | null>(null)
const previewLoading = ref(false)
const previewError = ref('')
const closing = ref(false)

function askClose() {
  // After a closing, the next month in order; the very first time, last month.
  closeMonth.value = (closings.value?.length ? closable.value.at(-1) : closable.value[0]) ?? ''
  closeOpen.value = true
}

let previewSeq = 0
watch([closeMonth, closeOpen], async ([month, open]) => {
  preview.value = null
  previewError.value = ''
  if (!open || !month) return
  const seq = ++previewSeq
  previewLoading.value = true
  try {
    const totals = await request<ClosingTotals>('/admin/finance/closings/preview', { query: { month } })
    if (seq === previewSeq) preview.value = totals
  }
  catch (err) {
    if (seq === previewSeq) previewError.value = apiError(err)
  }
  finally {
    if (seq === previewSeq) previewLoading.value = false
  }
})

async function confirmClose() {
  if (!closeMonth.value || !preview.value) return
  closing.value = true
  try {
    const created = await request<Closing>('/admin/finance/closings', { method: 'POST', body: { month: closeMonth.value } })
    toast.add({ title: t('closings.close.done', { month: formatMonth(created.month, locale.value) }), color: 'success' })
    closeOpen.value = false
    await refresh()
    selectedMonth.value = created.month
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    closing.value = false
  }
}
</script>

<template>
  <UDashboardPanel id="closings">
    <template #header>
      <UDashboardNavbar :title="t('nav.closings')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton
            v-if="canClose"
            icon="i-lucide-book-lock"
            :label="t('closings.close.button')"
            :disabled="!closings"
            @click="askClose"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <p class="text-sm text-(--ui-text-muted)">
        {{ t('closings.help') }}
      </p>

      <!-- Ledger invariants -->
      <UCard>
        <template #header>
          <div class="flex flex-wrap items-center justify-between gap-2">
            <div>
              <div class="flex items-center gap-2">
                <h2 class="font-semibold">
                  {{ t('closings.invariants.title') }}
                </h2>
                <UBadge
                  v-if="invariants"
                  :color="invariants.ok ? 'success' : 'error'"
                  variant="subtle"
                  size="sm"
                >
                  {{ invariants.ok ? t('closings.invariants.ok') : t('closings.invariants.failed', { n: invariants.issues.length }) }}
                </UBadge>
              </div>
              <p class="text-sm text-(--ui-text-muted)">
                {{ invariants
                  ? t('closings.invariants.checkedAt', { time: formatDate(invariants.checked_at, locale), wallets: formatNumber(invariants.wallets, locale) })
                  : t('closings.invariants.help') }}
              </p>
            </div>
            <UButton
              v-if="canClose"
              icon="i-lucide-scan-search"
              color="neutral"
              variant="outline"
              size="sm"
              :label="t('closings.invariants.run')"
              :loading="checking"
              @click="runInvariants"
            />
          </div>
        </template>
        <USkeleton
          v-if="invariantsStatus === 'pending' && !invariants"
          class="h-6 w-64"
        />
        <p
          v-else-if="!invariants"
          class="text-sm text-(--ui-text-muted)"
        >
          {{ t('closings.invariants.never') }}
        </p>
        <p
          v-else-if="invariants.ok"
          class="text-sm text-(--ui-text-muted)"
        >
          {{ t('closings.invariants.help') }}
        </p>
        <ul
          v-else
          class="space-y-2 text-sm"
        >
          <li
            v-for="(issue, index) in shownIssues"
            :key="index"
            class="flex flex-wrap items-baseline gap-2"
          >
            <UIcon
              name="i-lucide-circle-alert"
              class="size-4 shrink-0 self-center text-(--ui-error)"
            />
            <span class="font-medium">{{ issueLabel(issue) }}</span>
            <NuxtLink
              v-if="issue.user_id"
              :to="walletLink(issue.user_id)"
              class="text-primary hover:underline"
            >
              {{ t('closings.invariants.user') }} {{ issue.user_id.slice(0, 8) }}
            </NuxtLink>
            <span class="font-mono text-xs text-(--ui-text-muted) break-all">{{ issueDetail(issue) }}</span>
          </li>
          <li
            v-if="invariants.issues.length > ISSUES_SHOWN"
            class="text-(--ui-text-muted)"
          >
            {{ t('closings.invariants.more', { n: invariants.issues.length - ISSUES_SHOWN }) }}
          </li>
        </ul>
      </UCard>

      <UAlert
        v-if="tampered"
        color="error"
        variant="solid"
        icon="i-lucide-shield-alert"
        :title="t('closings.tamperedList')"
      />
      <UAlert
        v-if="error"
        color="error"
        variant="subtle"
        icon="i-lucide-circle-alert"
        :title="apiError(error)"
      />

      <UTable
        :data="closings ?? []"
        :columns="columns"
        :loading="status === 'pending'"
        :empty="t('closings.empty')"
      >
        <template #month-cell="{ row }">
          <span class="whitespace-nowrap font-medium capitalize">{{ formatMonth(row.original.month, locale) }}</span>
        </template>
        <template #fees-cell="{ row }">
          <span class="tabular-nums">{{ usdt(row.original.totals.fees_collected) }}</span>
        </template>
        <template #topUps-cell="{ row }">
          <span class="tabular-nums">{{ usdt(row.original.totals.top_ups?.credited?.amount) }}</span>
          <p class="text-xs text-(--ui-text-muted)">
            {{ formatNumber(row.original.totals.top_ups?.credited?.count ?? 0, locale) }}
          </p>
        </template>
        <template #balance-cell="{ row }">
          <span class="tabular-nums">{{ usdt(row.original.totals.balances?.closing) }}</span>
        </template>
        <template #status-cell="{ row }">
          <UBadge
            :color="closingBadge(row.original).color"
            :variant="row.original.hash_ok ? 'subtle' : 'solid'"
            :icon="row.original.hash_ok ? undefined : 'i-lucide-shield-alert'"
          >
            {{ t(`closings.statuses.${closingBadge(row.original).key}`) }}
          </UBadge>
        </template>
        <template #closed_at-cell="{ row }">
          <span class="text-sm whitespace-nowrap">{{ formatDate(row.original.closed_at, locale) }}</span>
          <p class="text-xs text-(--ui-text-muted)">
            {{ row.original.closed_by?.name || row.original.closed_by?.email || '' }}
          </p>
        </template>
        <template #actions-cell="{ row }">
          <div class="flex justify-end">
            <UButton
              size="xs"
              color="neutral"
              variant="soft"
              icon="i-lucide-eye"
              :label="t('closings.view')"
              @click="selectedMonth = row.original.month"
            />
          </div>
        </template>
      </UTable>

      <USlideover
        v-model:open="detailOpen"
        :title="selected ? t('closings.detail.title', { month: formatMonth(selected.month, locale) }) : ''"
        :ui="{ content: 'sm:max-w-2xl' }"
      >
        <template #body>
          <ClosingDetail
            v-if="selected"
            :key="selected.month"
            :closing="selected"
            @changed="closingChanged"
          />
        </template>
      </USlideover>

      <UModal
        v-model:open="closeOpen"
        :title="t('closings.close.title')"
        :description="t('closings.close.help')"
        :ui="{ content: 'sm:max-w-2xl' }"
      >
        <template #body>
          <div class="space-y-4">
            <p
              v-if="!closable.length"
              class="text-sm text-(--ui-text-muted)"
            >
              {{ t('closings.close.none') }}
            </p>
            <template v-else>
              <UFormField
                :label="t('closings.close.month')"
                required
              >
                <USelect
                  v-model="closeMonth"
                  :items="closableItems"
                  class="w-60 capitalize"
                  :disabled="closing"
                />
              </UFormField>
              <USkeleton
                v-if="previewLoading"
                class="h-48"
              />
              <UAlert
                v-else-if="previewError"
                color="error"
                variant="subtle"
                icon="i-lucide-circle-alert"
                :title="previewError"
              />
              <template v-else-if="preview">
                <h3 class="text-sm font-semibold">
                  {{ t('closings.close.preview') }}
                </h3>
                <ClosingTotals :totals="preview" />
                <UAlert
                  color="warning"
                  variant="subtle"
                  icon="i-lucide-triangle-alert"
                  :title="t('closings.close.confirm')"
                />
              </template>
            </template>
          </div>
        </template>
        <template #footer>
          <div class="flex w-full justify-end gap-2">
            <UButton
              color="neutral"
              variant="ghost"
              :label="t('common.cancel')"
              @click="closeOpen = false"
            />
            <UButton
              v-if="closable.length"
              icon="i-lucide-book-lock"
              :label="t('closings.close.submit', { month: formatMonth(closeMonth, locale) })"
              :disabled="!preview"
              :loading="closing"
              @click="confirmClose"
            />
          </div>
        </template>
      </UModal>
    </template>
  </UDashboardPanel>
</template>
