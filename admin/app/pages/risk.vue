<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { BlockedRead, HoldRead, HoldStatus, Page, RiskKind, SignalRead, SignalStatus } from '~/types/api'
import { HOLD_STATUSES, RISK_KINDS, SIGNAL_STATUSES } from '~/types/api'

definePageMeta({ permission: 'risk.view' })

const { t, te, locale } = useI18n()
const { request } = useApi()
const route = useRoute()
const router = useRouter()
const auth = useAuth()
const toast = useToast()
const apiError = useApiError()
const risk = useRiskSummary()

const canManage = computed(() => auth.can('risk.manage'))
const label = (key: string, fallback: string) => (te(key) ? t(key) : fallback)
const queryString = (key: string) => (typeof route.query[key] === 'string' ? route.query[key] as string : '')

type Tab = 'alerts' | 'holds' | 'blocked'
const TABS: Tab[] = ['alerts', 'holds', 'blocked']
const tab = ref<Tab>(TABS.includes(queryString('tab') as Tab) ? queryString('tab') as Tab : 'alerts')
// Keep the tab and the open alert in the URL so a link (the user page) lands on them.
const selectedId = ref<string | null>(queryString('signal') || null)
watch([tab, selectedId], ([value, signal]) => {
  router.replace({ query: { ...(value !== 'alerts' ? { tab: value } : {}), ...(signal ? { signal } : {}) } })
})
const tabs = computed(() => TABS.map(value => ({ label: t(`risk.tabs.${value}`), value })))

onMounted(() => risk.refresh())
const limit = 25

// ---- Alerts ---------------------------------------------------------------------------------

type KindFilter = RiskKind | 'all'
type SignalFilter = SignalStatus | 'all'
const kind = ref<KindFilter>(RISK_KINDS.includes(queryString('kind') as RiskKind) ? queryString('kind') as RiskKind : 'all')
const signalStatus = ref<SignalFilter>('open')
const signalPage = ref(1)
watch([kind, signalStatus], () => {
  signalPage.value = 1
})

const signalsParams = computed(() => signalsQuery({ kind: kind.value, status: signalStatus.value, limit, offset: (signalPage.value - 1) * limit }))
const { data: signals, status: signalsStatus, error: signalsError, refresh: refreshSignals } = await useAsyncData(
  'risk-signals',
  () => request<Page<SignalRead>>('/admin/risk/signals', { query: signalsParams.value }),
  { watch: [signalsParams] },
)

const kindItems = computed(() => {
  const total = riskOpenCount(risk.summary.value)
  const count = (n: number) => (risk.summary.value ? ` (${n})` : '')
  return [
    { label: `${t('risk.allKinds')}${count(total)}`, value: 'all' as KindFilter },
    ...RISK_KINDS.map(value => ({ label: `${t(riskKindKey(value))}${count(riskOpenCount(risk.summary.value, value))}`, value: value as KindFilter })),
  ]
})
const signalStatusItems = computed(() => [
  ...SIGNAL_STATUSES.map(value => ({ label: t(`risk.statuses.${value}`), value: value as SignalFilter })),
  { label: t('risk.allStatuses'), value: 'all' as SignalFilter },
])

const signalColumns = computed<TableColumn<SignalRead>[]>(() => [
  { accessorKey: 'kind', header: t('risk.kind') },
  { accessorKey: 'reasons', header: t('risk.reasonsLabel') },
  { accessorKey: 'score', header: t('risk.scoreShort') },
  { id: 'user', header: t('risk.user') },
  { id: 'related', header: t('risk.related') },
  { accessorKey: 'created_at', header: t('risk.date') },
])

async function signalChanged() {
  await Promise.all([refreshSignals(), refreshHolds(), risk.refresh()])
}

const detailOpen = computed({
  get: () => !!selectedId.value,
  set: (value: boolean) => {
    if (!value) selectedId.value = null
  },
})

// ---- Held payments --------------------------------------------------------------------------

type HoldFilter = HoldStatus | 'all'
const holdStatus = ref<HoldFilter>('held')
const holdPage = ref(1)
watch(holdStatus, () => {
  holdPage.value = 1
})
const holdsParams = computed(() => ({
  status: holdStatus.value === 'all' ? '' : holdStatus.value,
  limit,
  offset: (holdPage.value - 1) * limit,
}))
const { data: holds, status: holdsStatus, error: holdsError, refresh: refreshHolds } = await useAsyncData(
  'risk-holds',
  () => request<Page<HoldRead>>('/admin/risk/holds', { query: holdsParams.value }),
  { watch: [holdsParams] },
)
const holdStatusItems = computed(() => [
  ...HOLD_STATUSES.map(value => ({ label: t(`risk.holdStatuses.${value}`), value: value as HoldFilter })),
  { label: t('risk.allStatuses'), value: 'all' as HoldFilter },
])
const holdColumns = computed<TableColumn<HoldRead>[]>(() => [
  { accessorKey: 'kind', header: t('risk.kind') },
  { accessorKey: 'amount', header: t('risk.holds.amount') },
  { id: 'recipient', header: t('risk.holds.recipient') },
  { id: 'sender', header: t('risk.holds.sender') },
  { accessorKey: 'reasons', header: t('risk.reasonsLabel') },
  { accessorKey: 'created_at', header: t('risk.date') },
  { id: 'actions', header: '' },
])

const holdModalOpen = ref(false)
const holdAction = ref<'release' | 'void'>('release')
const holdTarget = ref<HoldRead | null>(null)
function actOnHold(hold: HoldRead, action: 'release' | 'void') {
  holdTarget.value = hold
  holdAction.value = action
  holdModalOpen.value = true
}
async function holdDone() {
  await Promise.all([refreshHolds(), risk.refresh()])
}

// ---- Banned identifiers ---------------------------------------------------------------------

const search = ref('')
const debouncedSearch = ref('')
let searchTimer: ReturnType<typeof setTimeout> | undefined
watch(search, (value) => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => (debouncedSearch.value = value.trim()), 300)
})
const blockedPage = ref(1)
watch(debouncedSearch, () => {
  blockedPage.value = 1
})
const blockedParams = computed(() => ({
  limit,
  offset: (blockedPage.value - 1) * limit,
  ...(debouncedSearch.value ? { q: debouncedSearch.value } : {}),
}))
const { data: blocked, status: blockedStatus, error: blockedError, refresh: refreshBlocked } = await useAsyncData(
  'risk-blocked',
  () => request<Page<BlockedRead>>('/admin/risk/blocked', { query: blockedParams.value }),
  { watch: [blockedParams] },
)
const blockedColumns = computed<TableColumn<BlockedRead>[]>(() => [
  { accessorKey: 'kind', header: t('risk.blocked.kind') },
  { accessorKey: 'reason', header: t('risk.blocked.reason') },
  { id: 'account', header: t('risk.blocked.account') },
  { accessorKey: 'created_at', header: t('risk.blocked.by') },
  { id: 'actions', header: '' },
])

const removing = ref<string | null>(null)
async function unblock(row: BlockedRead) {
  if (!confirm(t('risk.blocked.removeConfirm', { kind: label(blockedKindKey(row.kind), row.kind) }))) return
  removing.value = row.id
  try {
    await request(`/admin/risk/blocked/${row.id}`, { method: 'DELETE' })
    toast.add({ title: t('risk.blocked.removed'), color: 'success' })
    await refreshBlocked()
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    removing.value = null
  }
}
</script>

<template>
  <UDashboardPanel id="risk">
    <template #header>
      <UDashboardNavbar :title="t('nav.risk')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <span
            v-if="risk.summary.value?.holds"
            class="text-sm text-(--ui-text-muted)"
          >
            {{ t('risk.heldTotal', { n: risk.summary.value.holds, amount: formatUsdt(risk.summary.value.held_amount, locale) }) }}
          </span>
        </template>
      </UDashboardNavbar>
      <UDashboardToolbar>
        <template #left>
          <UTabs
            v-model="tab"
            :items="tabs"
            :content="false"
            size="sm"
            variant="link"
          />
        </template>
        <template #right>
          <template v-if="tab === 'alerts'">
            <USelect
              v-model="kind"
              :items="kindItems"
              class="w-56"
              :aria-label="t('risk.kind')"
            />
            <USelect
              v-model="signalStatus"
              :items="signalStatusItems"
              class="w-40"
              :aria-label="t('risk.status')"
            />
          </template>
          <USelect
            v-else-if="tab === 'holds'"
            v-model="holdStatus"
            :items="holdStatusItems"
            class="w-40"
            :aria-label="t('risk.status')"
          />
          <UInput
            v-else
            v-model="search"
            icon="i-lucide-search"
            :placeholder="t('risk.blocked.search')"
            class="w-72 max-w-full"
          />
        </template>
      </UDashboardToolbar>
    </template>

    <template #body>
      <p class="text-sm text-(--ui-text-muted)">
        {{ t(`risk.help.${tab}`) }}
      </p>

      <!-- Alerts -->
      <template v-if="tab === 'alerts'">
        <UAlert
          v-if="signalsError"
          color="error"
          variant="subtle"
          icon="i-lucide-circle-alert"
          :title="apiError(signalsError)"
        />
        <UTable
          :data="signals?.items ?? []"
          :columns="signalColumns"
          :loading="signalsStatus === 'pending'"
          :empty="t('risk.empty.alerts')"
          class="cursor-pointer"
          @select="(_e: Event, row: { original: SignalRead }) => (selectedId = row.original.id)"
        >
          <template #kind-cell="{ row }">
            <span class="flex items-center gap-2 font-medium">
              <UIcon
                :name="riskKindIcon(row.original.kind)"
                class="size-4 shrink-0"
              />
              {{ label(riskKindKey(row.original.kind), row.original.kind) }}
            </span>
            <UBadge
              v-if="signalStatus === 'all'"
              :color="signalStatusColor(row.original.status)"
              variant="subtle"
              size="sm"
              class="mt-1"
            >
              {{ label(`risk.statuses.${row.original.status}`, row.original.status) }}
            </UBadge>
          </template>
          <template #reasons-cell="{ row }">
            <div class="flex max-w-xs flex-wrap gap-1">
              <UBadge
                v-for="reason in row.original.reasons"
                :key="reason"
                color="neutral"
                variant="outline"
                size="sm"
              >
                {{ label(riskReasonKey(reason), reason) }}
              </UBadge>
            </div>
          </template>
          <template #score-cell="{ row }">
            <UBadge
              :color="riskScoreColor(row.original.score)"
              variant="subtle"
              class="tabular-nums"
            >
              {{ row.original.score }}
            </UBadge>
          </template>
          <template #user-cell="{ row }">
            <RiskUserCell
              :user="row.original.user"
              score
            />
          </template>
          <template #related-cell="{ row }">
            <RiskUserCell :user="row.original.related_user" />
          </template>
          <template #created_at-cell="{ row }">
            <span class="whitespace-nowrap">{{ formatDate(row.original.created_at, locale) }}</span>
          </template>
        </UTable>
        <div class="flex items-center justify-between border-t border-(--ui-border) pt-4">
          <span class="text-sm text-(--ui-text-muted)">
            {{ t('risk.totalAlerts', signals?.total ?? 0) }}
          </span>
          <UPagination
            v-model:page="signalPage"
            :total="signals?.total ?? 0"
            :items-per-page="limit"
          />
        </div>
      </template>

      <!-- Held payments -->
      <template v-else-if="tab === 'holds'">
        <UAlert
          v-if="holdsError"
          color="error"
          variant="subtle"
          icon="i-lucide-circle-alert"
          :title="apiError(holdsError)"
        />
        <UTable
          :data="holds?.items ?? []"
          :columns="holdColumns"
          :loading="holdsStatus === 'pending'"
          :empty="t('risk.empty.holds')"
        >
          <template #kind-cell="{ row }">
            <span class="font-medium">{{ label(holdKindKey(row.original.kind), row.original.kind) }}</span>
            <div>
              <UBadge
                v-if="holdStatus === 'all' || !isHoldOpen(row.original)"
                :color="holdStatusColor(row.original.status)"
                variant="subtle"
                size="sm"
              >
                {{ label(`risk.holdStatuses.${row.original.status}`, row.original.status) }}
              </UBadge>
            </div>
            <NuxtLink
              v-if="row.original.ride_id"
              :to="`/rides/${row.original.ride_id}`"
              class="text-xs text-primary hover:underline"
            >
              {{ t('live.openRide') }}
            </NuxtLink>
          </template>
          <template #amount-cell="{ row }">
            <span class="whitespace-nowrap font-medium tabular-nums">{{ formatUsdt(row.original.amount, locale) }}</span>
          </template>
          <template #recipient-cell="{ row }">
            <RiskUserCell
              :user="row.original.user"
              score
            />
          </template>
          <template #sender-cell="{ row }">
            <RiskUserCell :user="row.original.sender" />
          </template>
          <template #reasons-cell="{ row }">
            <div class="flex max-w-xs flex-wrap gap-1">
              <UBadge
                v-for="reason in row.original.reasons"
                :key="reason"
                color="neutral"
                variant="outline"
                size="sm"
              >
                {{ label(riskReasonKey(reason), reason) }}
              </UBadge>
            </div>
          </template>
          <template #created_at-cell="{ row }">
            <span class="whitespace-nowrap">{{ formatDate(row.original.created_at, locale) }}</span>
            <p
              v-if="isHoldOpen(row.original) && row.original.release_at"
              class="text-xs text-(--ui-text-muted)"
            >
              {{ t('risk.holds.releasesAt', { date: formatDate(row.original.release_at, locale) }) }}
            </p>
            <p
              v-if="row.original.resolved_at"
              class="text-xs text-(--ui-text-muted)"
            >
              {{ t('risk.reviewedBy', { name: row.original.resolved_by_name || '—', date: formatDate(row.original.resolved_at, locale) }) }}
            </p>
            <p
              v-if="row.original.note"
              class="max-w-xs truncate text-xs text-(--ui-text-muted)"
              :title="row.original.note"
            >
              {{ row.original.note }}
            </p>
          </template>
          <template #actions-cell="{ row }">
            <div
              v-if="canManage && isHoldOpen(row.original)"
              class="flex justify-end gap-2"
            >
              <UButton
                size="xs"
                color="success"
                variant="soft"
                icon="i-lucide-check"
                :label="t('risk.holds.release')"
                @click="actOnHold(row.original, 'release')"
              />
              <UButton
                size="xs"
                color="error"
                variant="soft"
                icon="i-lucide-undo-2"
                :label="t('risk.holds.void')"
                @click="actOnHold(row.original, 'void')"
              />
            </div>
          </template>
        </UTable>
        <div class="flex items-center justify-between border-t border-(--ui-border) pt-4">
          <span class="text-sm text-(--ui-text-muted)">
            {{ t('risk.totalHolds', holds?.total ?? 0) }}
          </span>
          <UPagination
            v-model:page="holdPage"
            :total="holds?.total ?? 0"
            :items-per-page="limit"
          />
        </div>
      </template>

      <!-- Banned identifiers -->
      <template v-else>
        <UAlert
          v-if="blockedError"
          color="error"
          variant="subtle"
          icon="i-lucide-circle-alert"
          :title="apiError(blockedError)"
        />
        <UTable
          :data="blocked?.items ?? []"
          :columns="blockedColumns"
          :loading="blockedStatus === 'pending'"
          :empty="t('risk.empty.blocked')"
        >
          <template #kind-cell="{ row }">
            <UBadge
              color="error"
              variant="outline"
            >
              {{ label(blockedKindKey(row.original.kind), row.original.kind) }}
            </UBadge>
          </template>
          <template #reason-cell="{ row }">
            <span
              class="block max-w-sm whitespace-normal"
            >{{ row.original.reason || '—' }}</span>
          </template>
          <template #account-cell="{ row }">
            <RiskUserCell :user="row.original.source_user" />
          </template>
          <template #created_at-cell="{ row }">
            <span class="whitespace-nowrap">{{ formatDate(row.original.created_at, locale) }}</span>
            <p class="text-xs text-(--ui-text-muted)">
              {{ row.original.created_by_name || '—' }}
            </p>
          </template>
          <template #actions-cell="{ row }">
            <div class="flex justify-end">
              <UButton
                v-if="canManage"
                size="xs"
                color="neutral"
                variant="outline"
                icon="i-lucide-trash-2"
                :loading="removing === row.original.id"
                :label="t('risk.blocked.remove')"
                @click="unblock(row.original)"
              />
            </div>
          </template>
        </UTable>
        <div class="flex items-center justify-between border-t border-(--ui-border) pt-4">
          <span class="text-sm text-(--ui-text-muted)">
            {{ t('risk.totalBlocked', blocked?.total ?? 0) }}
          </span>
          <UPagination
            v-model:page="blockedPage"
            :total="blocked?.total ?? 0"
            :items-per-page="limit"
          />
        </div>
      </template>

      <USlideover
        v-model:open="detailOpen"
        :title="t('risk.detailTitle')"
        :ui="{ content: 'sm:max-w-2xl' }"
      >
        <template #body>
          <RiskSignalDetail
            v-if="selectedId"
            :key="selectedId"
            :signal-id="selectedId"
            @changed="signalChanged"
          />
        </template>
      </USlideover>

      <RiskHoldModal
        v-model:open="holdModalOpen"
        :hold="holdTarget"
        :action="holdAction"
        @done="holdDone"
      />
    </template>
  </UDashboardPanel>
</template>
