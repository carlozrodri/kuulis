<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { AdminDriver, AdminTopUp, AppConfig, Page, TopUpInfo, TopUpStatus } from '~/types/api'
import { TOP_UP_STATUSES } from '~/types/api'

const { t, locale } = useI18n()
const { request } = useApi()
const auth = useAuth()
const route = useRoute()
const router = useRouter()
const toast = useToast()
const apiError = useApiError()

type StatusFilter = TopUpStatus | 'all'
const statusFilters: StatusFilter[] = [...TOP_UP_STATUSES, 'all']
const queryString = (key: string) => (typeof route.query[key] === 'string' ? route.query[key] as string : '')

// Filters live in the URL so "back" returns to the same list. Pending first: that is the work queue.
const initialStatus = queryString('status') as StatusFilter
const status = ref<StatusFilter>(statusFilters.includes(initialStatus) ? initialStatus : 'pending')
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
      ...(status.value !== 'pending' ? { status: status.value } : {}),
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

const { data, status: fetchStatus, error, refresh } = await useAsyncData(
  'top-ups',
  () => request<Page<AdminTopUp>>('/admin/top-ups', { query: query.value }),
  { watch: [query] },
)

// Explanation banner: Kuulis' Pay ID comes from settings; `automatic` only from /wallet/top-up-info, which may
// be restricted to drivers, so the banner also works without it.
const { data: config } = await useAsyncData('top-ups-config', () => request<AppConfig>('/admin/config').catch(() => null))
const { data: info } = await useAsyncData('top-ups-info', () => request<TopUpInfo>('/wallet/top-up-info').catch(() => null))
const payId = computed(() => config.value?.topup_binance_pay_id ?? info.value?.pay_id ?? '')
const accountName = computed(() => config.value?.topup_account_name || info.value?.account_name || 'Kuulis')
const minAmount = computed(() => config.value?.topup_min_amount ?? info.value?.min_amount ?? '5.00')
const automatic = computed<boolean | null>(() => info.value?.automatic ?? null)
const showHelp = ref(true)

const tabs = computed(() =>
  statusFilters.map(value => ({
    label: value === 'all' ? t('topUps.allStatuses') : t(`topUps.statuses.${value}`),
    value,
  })),
)

const columns = computed<TableColumn<AdminTopUp>[]>(() => [
  { accessorKey: 'created_at', header: t('topUps.createdAt') },
  { id: 'driver', header: t('topUps.driver') },
  { accessorKey: 'amount', header: t('topUps.amount') },
  { id: 'payer', header: t('topUps.payer') },
  { accessorKey: 'reference', header: t('topUps.reference') },
  { accessorKey: 'status', header: t('topUps.status') },
  ...(auth.isAdmin.value ? [{ id: 'actions', header: '' }] : []),
])

// ---- Admin actions (one modal: confirm / reject / assign) ------------------------------------

type ActionKind = 'confirm' | 'reject' | 'assign'
const action = ref<{ kind: ActionKind, topUp: AdminTopUp } | null>(null)
const actionOpen = computed({
  get: () => action.value !== null,
  set: (open: boolean) => {
    if (!open) action.value = null
  },
})
const busy = ref(false)

const confirmAmount = ref<number | null>(null)
const confirmReference = ref('')
const rejectReason = ref('')

function openAction(kind: ActionKind, topUp: AdminTopUp) {
  const amount = Number(topUp.amount)
  confirmAmount.value = Number.isFinite(amount) && amount > 0 ? amount : null
  confirmReference.value = topUp.reference ?? ''
  rejectReason.value = ''
  driverSearch.value = ''
  driverResults.value = []
  selectedDriver.value = null
  action.value = { kind, topUp }
}

// Assign: search drivers with the existing list endpoint, then POST the driver's user_id.
const driverSearch = ref('')
const driverResults = ref<AdminDriver[]>([])
const driverSearching = ref(false)
const selectedDriver = ref<AdminDriver | null>(null)
let driverTimer: ReturnType<typeof setTimeout> | undefined
let driverSeq = 0
watch(driverSearch, (value) => {
  clearTimeout(driverTimer)
  const q = value.trim()
  if (q.length < 2) {
    driverResults.value = []
    return
  }
  driverTimer = setTimeout(async () => {
    const seq = ++driverSeq
    driverSearching.value = true
    try {
      const result = await request<Page<AdminDriver>>('/admin/drivers', { query: { q, limit: 8, offset: 0 } })
      if (seq === driverSeq) driverResults.value = result.items
    }
    catch (err) {
      if (seq === driverSeq) toast.add({ title: apiError(err), color: 'error' })
    }
    finally {
      if (seq === driverSeq) driverSearching.value = false
    }
  }, 300)
})

const canSubmit = computed(() => {
  const kind = action.value?.kind
  if (kind === 'confirm') return confirmAmount.value !== null && Number.isFinite(confirmAmount.value) && confirmAmount.value > 0
  if (kind === 'reject') return !!rejectReason.value.trim()
  if (kind === 'assign') return !!selectedDriver.value
  return false
})

async function submitAction() {
  const current = action.value
  if (!current || !canSubmit.value) return
  const { kind, topUp } = current
  let body: Record<string, unknown>
  if (kind === 'confirm') {
    const reference = confirmReference.value.trim()
    body = { amount: confirmAmount.value!.toFixed(2), ...(reference ? { reference } : {}) }
  }
  else if (kind === 'reject') {
    body = { reason: rejectReason.value.trim() }
  }
  else {
    body = { user_id: selectedDriver.value!.user_id }
  }
  busy.value = true
  try {
    await request(`/admin/top-ups/${topUp.id}/${kind}`, { method: 'POST', body })
    toast.add({ title: t(`topUps.toast.${kind}`), color: 'success' })
    action.value = null
    await refresh()
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    busy.value = false
  }
}

const moneyFormat = { minimumFractionDigits: 2, maximumFractionDigits: 2 }
</script>

<template>
  <UDashboardPanel id="top-ups">
    <template #header>
      <UDashboardNavbar :title="t('nav.topUps')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton
            icon="i-lucide-circle-help"
            color="neutral"
            variant="ghost"
            :aria-label="t('topUps.help.toggle')"
            :aria-pressed="showHelp"
            @click="showHelp = !showHelp"
          />
          <UButton
            icon="i-lucide-arrow-left-right"
            color="neutral"
            variant="outline"
            :label="t('nav.transfers')"
            to="/transfers"
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
            :placeholder="t('topUps.search')"
            class="w-72 max-w-full"
          />
        </template>
      </UDashboardToolbar>
    </template>

    <template #body>
      <UAlert
        v-if="showHelp"
        color="info"
        variant="subtle"
        icon="i-lucide-info"
        :title="t('topUps.help.title')"
      >
        <template #description>
          <ol class="list-decimal space-y-1 pl-4">
            <li>
              {{ t('topUps.help.step1') }}
            </li>
            <li>
              <template v-if="payId">
                {{ t('topUps.help.step2', { payId, name: accountName, min: formatUsdt(minAmount, locale) }) }}
              </template>
              <template v-else>
                {{ t('topUps.help.step2Missing') }}
                <NuxtLink
                  to="/settings"
                  class="font-medium underline"
                >{{ t('nav.settings') }}</NuxtLink>
              </template>
            </li>
            <li>{{ t('topUps.help.step3') }}</li>
          </ol>
          <p class="mt-2">
            <template v-if="automatic === true">
              {{ t('topUps.help.automatic') }}
            </template>
            <template v-else-if="automatic === false">
              {{ t('topUps.help.manual') }}
            </template>
            <template v-else>
              {{ t('topUps.help.unknownMode') }}
            </template>
          </p>
          <p class="mt-2">
            {{ t('topUps.help.statuses') }}
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

      <UTable
        :data="data?.items ?? []"
        :columns="columns"
        :loading="fetchStatus === 'pending'"
        :empty="t('common.empty')"
      >
        <template #created_at-cell="{ row }">
          <span class="whitespace-nowrap">{{ formatDate(row.original.created_at, locale) }}</span>
        </template>
        <template #driver-cell="{ row }">
          <PartyCell
            :party="ownerOf(row.original)"
            :empty="t('topUps.noOwner')"
          />
        </template>
        <template #amount-cell="{ row }">
          <span class="whitespace-nowrap font-medium tabular-nums">{{ formatUsdt(row.original.amount, locale) }}</span>
        </template>
        <template #payer-cell="{ row }">
          <p
            v-if="row.original.payer_binance_id"
            class="font-mono text-xs"
          >
            {{ row.original.payer_binance_id }}
          </p>
          <p
            v-if="row.original.payer_name"
            class="text-xs text-(--ui-text-muted)"
          >
            {{ row.original.payer_name }}
          </p>
          <span v-if="!row.original.payer_binance_id && !row.original.payer_name">—</span>
        </template>
        <template #reference-cell="{ row }">
          <span class="font-mono text-xs break-all">{{ row.original.reference || '—' }}</span>
          <p
            v-if="row.original.note"
            class="max-w-xs truncate text-xs text-(--ui-text-muted)"
            :title="row.original.note"
          >
            {{ row.original.note }}
          </p>
        </template>
        <template #status-cell="{ row }">
          <UBadge
            :color="topUpStatusColor[row.original.status] ?? 'neutral'"
            variant="subtle"
          >
            {{ t(`topUps.statuses.${row.original.status}`, row.original.status) }}
          </UBadge>
          <p
            v-if="row.original.status === 'completed' && row.original.completed_at"
            class="text-xs whitespace-nowrap text-(--ui-text-muted)"
          >
            {{ formatDate(row.original.completed_at, locale) }}
          </p>
          <p
            v-if="row.original.status === 'rejected' && row.original.rejection_reason"
            class="max-w-xs truncate text-xs text-error"
            :title="row.original.rejection_reason"
          >
            {{ row.original.rejection_reason }}
          </p>
        </template>
        <template #actions-cell="{ row }">
          <div class="flex justify-end gap-2">
            <UButton
              v-if="row.original.status === 'pending'"
              size="xs"
              icon="i-lucide-check"
              variant="soft"
              :label="t('topUps.actions.confirm')"
              @click="openAction('confirm', row.original)"
            />
            <UButton
              v-if="row.original.status === 'unmatched'"
              size="xs"
              icon="i-lucide-user-plus"
              variant="soft"
              :label="t('topUps.actions.assign')"
              @click="openAction('assign', row.original)"
            />
            <UButton
              v-if="row.original.status === 'pending' || row.original.status === 'unmatched'"
              size="xs"
              icon="i-lucide-x"
              color="error"
              variant="soft"
              :label="t('topUps.actions.reject')"
              @click="openAction('reject', row.original)"
            />
          </div>
        </template>
      </UTable>

      <div class="flex items-center justify-between border-t border-(--ui-border) pt-4">
        <span class="text-sm text-(--ui-text-muted)">
          {{ t('topUps.total', { n: data?.total ?? 0 }) }}
        </span>
        <UPagination
          v-model:page="page"
          :total="data?.total ?? 0"
          :items-per-page="limit"
        />
      </div>

      <UModal
        v-model:open="actionOpen"
        :title="action ? t(`topUps.actions.${action.kind}Title`) : ''"
        :description="action ? t(`topUps.actions.${action.kind}Help`) : ''"
      >
        <template #body>
          <form
            v-if="action"
            id="top-up-action-form"
            class="space-y-4"
            @submit.prevent="submitAction"
          >
            <dl class="grid grid-cols-2 gap-3 rounded-md bg-(--ui-bg-elevated) p-3 text-sm">
              <div>
                <dt class="text-(--ui-text-muted)">
                  {{ t('topUps.requested') }}
                </dt>
                <dd class="font-medium tabular-nums">
                  {{ formatUsdt(action.topUp.amount, locale) }}
                </dd>
              </div>
              <div>
                <dt class="text-(--ui-text-muted)">
                  {{ t('topUps.driver') }}
                </dt>
                <dd>{{ ownerOf(action.topUp)?.name || ownerOf(action.topUp)?.email || t('topUps.noOwner') }}</dd>
              </div>
              <div v-if="action.topUp.payer_binance_id || action.topUp.payer_name">
                <dt class="text-(--ui-text-muted)">
                  {{ t('topUps.payer') }}
                </dt>
                <dd>
                  <span class="font-mono">{{ action.topUp.payer_binance_id }}</span>
                  {{ action.topUp.payer_name }}
                </dd>
              </div>
              <div v-if="action.topUp.reference">
                <dt class="text-(--ui-text-muted)">
                  {{ t('topUps.reference') }}
                </dt>
                <dd class="font-mono break-all">
                  {{ action.topUp.reference }}
                </dd>
              </div>
            </dl>

            <template v-if="action.kind === 'confirm'">
              <UFormField
                :label="t('topUps.receivedAmount')"
                :help="t('topUps.receivedAmountHelp')"
                required
              >
                <UInputNumber
                  v-model="confirmAmount"
                  :min="0.01"
                  :max="100000"
                  :step="1"
                  :format-options="moneyFormat"
                  class="w-full"
                />
              </UFormField>
              <UFormField
                :label="t('topUps.reference')"
                :help="t('topUps.referenceHelp')"
              >
                <UInput
                  v-model="confirmReference"
                  maxlength="64"
                  class="w-full font-mono"
                />
              </UFormField>
            </template>

            <UFormField
              v-else-if="action.kind === 'reject'"
              :label="t('topUps.rejectReason')"
              required
            >
              <UTextarea
                v-model="rejectReason"
                class="w-full"
                :rows="3"
                maxlength="500"
                required
              />
            </UFormField>

            <div
              v-else
              class="space-y-3"
            >
              <UFormField
                :label="t('topUps.findDriver')"
                :help="t('topUps.findDriverHelp')"
              >
                <UInput
                  v-model="driverSearch"
                  icon="i-lucide-search"
                  :loading="driverSearching"
                  :placeholder="t('drivers.search')"
                  class="w-full"
                />
              </UFormField>
              <p
                v-if="driverSearch.trim().length >= 2 && !driverSearching && !driverResults.length"
                class="text-sm text-(--ui-text-muted)"
              >
                {{ t('common.empty') }}
              </p>
              <ul
                v-if="driverResults.length"
                class="max-h-64 divide-y divide-(--ui-border) overflow-y-auto rounded-md border border-(--ui-border)"
                role="listbox"
                :aria-label="t('topUps.findDriver')"
              >
                <li
                  v-for="driver in driverResults"
                  :key="driver.id"
                  role="option"
                  :aria-selected="selectedDriver?.id === driver.id"
                >
                  <button
                    type="button"
                    class="flex w-full items-center justify-between gap-2 p-3 text-left text-sm hover:bg-(--ui-bg-elevated)"
                    :class="{ 'bg-(--ui-bg-elevated)': selectedDriver?.id === driver.id }"
                    @click="selectedDriver = driver"
                  >
                    <span>
                      <span class="block font-medium">{{ driver.user?.full_name || '—' }}</span>
                      <span class="block text-xs text-(--ui-text-muted)">{{ driver.user?.email }} · {{ driver.national_id || '—' }}</span>
                    </span>
                    <span class="flex items-center gap-2">
                      <UBadge
                        :color="driverStatusColor[driver.status]"
                        variant="subtle"
                        size="sm"
                      >
                        {{ t(`drivers.statuses.${driver.status}`) }}
                      </UBadge>
                      <UIcon
                        v-if="selectedDriver?.id === driver.id"
                        name="i-lucide-check"
                        class="size-4 text-primary"
                      />
                    </span>
                  </button>
                </li>
              </ul>
              <p
                v-if="selectedDriver"
                class="text-sm"
              >
                {{ t('topUps.assignTo', { name: selectedDriver.user?.full_name || selectedDriver.user?.email, amount: formatUsdt(action.topUp.amount, locale) }) }}
              </p>
            </div>
          </form>
        </template>
        <template #footer>
          <div class="flex w-full justify-end gap-2">
            <UButton
              color="neutral"
              variant="ghost"
              :label="t('common.cancel')"
              @click="actionOpen = false"
            />
            <UButton
              type="submit"
              form="top-up-action-form"
              :color="action?.kind === 'reject' ? 'error' : 'primary'"
              :label="action ? t(`topUps.actions.${action.kind}`) : ''"
              :disabled="!canSubmit"
              :loading="busy"
            />
          </div>
        </template>
      </UModal>
    </template>
  </UDashboardPanel>
</template>
