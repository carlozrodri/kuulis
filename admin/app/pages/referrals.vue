<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { Page, ReferralAdmin, ReferralProgram, ReferralRanking, ReferralsOverview, ReferralStatus } from '~/types/api'
import { REFERRAL_STATUSES } from '~/types/api'
import type { ReferralAction, ReferralProgramForm } from '~/utils/referrals'

definePageMeta({ permission: 'referrals.view' })

const { t, te, locale } = useI18n()
const { request } = useApi()
const route = useRoute()
const router = useRouter()
const auth = useAuth()
const toast = useToast()
const apiError = useApiError()

const canManage = computed(() => auth.can('referrals.manage'))
const label = (key: string, fallback: string) => (te(key) ? t(key) : fallback)
const usdt = (value: string | number | null | undefined) => formatUsdt(value, locale.value)

type Tab = 'list' | 'ranking' | 'program'
const TABS: Tab[] = ['list', 'ranking', 'program']
const tab = ref<Tab>(TABS.includes(route.query.tab as Tab) ? route.query.tab as Tab : 'list')
watch(tab, value => router.replace({ query: value === 'list' ? {} : { tab: value } }))
const tabs = computed(() => TABS.map(value => ({ label: t(`referrals.tabs.${value}`), value })))

const { data: overview, refresh: refreshOverview } = await useAsyncData(
  'referrals-overview',
  () => request<ReferralsOverview>('/admin/referrals/overview'),
)
const count = (status: ReferralStatus) => overview.value?.counts.find(c => c.status === status)?.count ?? 0

// ---- Referrals ------------------------------------------------------------------------------

type StatusFilter = ReferralStatus | 'all' | 'alerts'
const status = ref<StatusFilter>('all')
const search = ref('')
const debouncedSearch = ref('')
let searchTimer: ReturnType<typeof setTimeout> | undefined
watch(search, (value) => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => (debouncedSearch.value = value.trim()), 300)
})
const page = ref(1)
const limit = 25
watch([status, debouncedSearch], () => {
  page.value = 1
})
const listQuery = computed(() => referralsQuery({ status: status.value, q: debouncedSearch.value, limit, offset: (page.value - 1) * limit }))
const { data: referrals, status: listStatus, error: listError, refresh: refreshList } = await useAsyncData(
  'referrals-list',
  () => request<Page<ReferralAdmin>>('/admin/referrals', { query: listQuery.value }),
  { watch: [listQuery] },
)

const statusItems = computed(() => [
  { label: t('referrals.allStatuses'), value: 'all' as StatusFilter },
  { label: `${t('referrals.alertsFilter')} (${overview.value?.alerts ?? 0})`, value: 'alerts' as StatusFilter },
  ...REFERRAL_STATUSES.map(value => ({ label: `${t(`referrals.statuses.${value}`)} (${count(value)})`, value: value as StatusFilter })),
])

const columns = computed<TableColumn<ReferralAdmin>[]>(() => [
  { id: 'referrer', header: t('referrals.referrer') },
  { id: 'referred', header: t('referrals.referred') },
  { accessorKey: 'status', header: t('referrals.status') },
  { id: 'progress', header: t('referrals.progress') },
  { accessorKey: 'reward_amount', header: t('referrals.reward') },
  { accessorKey: 'created_at', header: t('referrals.joined') },
  { id: 'actions', header: '' },
])

const reasonLabel = (row: ReferralAdmin) => {
  if (!row.reason) return null
  const text = label(`referrals.reasons.${row.reason}`, row.reason)
  if (row.reason === 'shared_identity' && row.details.shared?.length) {
    return `${text}: ${row.details.shared.map(kind => label(`risk.blockedKinds.${kind}`, kind)).join(', ')}`
  }
  return text
}

// ---- Actions --------------------------------------------------------------------------------

const modalOpen = ref(false)
const action = ref<ReferralAction>('release')
const target = ref<ReferralAdmin | null>(null)
const note = ref('')
const busy = ref(false)

function act(row: ReferralAdmin, value: ReferralAction) {
  target.value = row
  action.value = value
  note.value = ''
  modalOpen.value = true
}

const actionDescription = computed(() => {
  const row = target.value
  if (!row) return ''
  return t(`referrals.actions.${action.value}.description`, {
    referrer: row.referrer?.name || row.referrer?.email || '—',
    referred: row.referred?.name || row.referred?.email || '—',
    amount: usdt(row.reward_amount ?? overview.value?.program.reward_usd ?? 0),
  })
})
const rejectLabel = computed(() => (target.value?.status === 'rejected' ? t('referrals.actions.reject.reviewed') : t('referrals.actions.reject.button')))

async function submitAction() {
  const row = target.value
  if (!row) return
  busy.value = true
  try {
    const body = note.value.trim() ? { note: note.value.trim() } : {}
    await request<ReferralAdmin>(`/admin/referrals/${row.id}/${action.value}`, { method: 'POST', body })
    toast.add({ title: t(`referrals.actions.${action.value}.done`), color: 'success' })
    modalOpen.value = false
    await Promise.all([refreshList(), refreshOverview(), refreshRanking()])
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    busy.value = false
  }
}

// ---- Ranking --------------------------------------------------------------------------------

const { data: ranking, status: rankingStatus, refresh: refreshRanking } = await useAsyncData(
  'referrals-ranking',
  () => request<ReferralRanking[]>('/admin/referrals/ranking', { query: { limit: 20 } }),
)
const rankingColumns = computed<TableColumn<ReferralRanking>[]>(() => [
  { id: 'position', header: '#' },
  { id: 'user', header: t('referrals.referrer') },
  { accessorKey: 'invited', header: t('referrals.ranking.invited') },
  { accessorKey: 'rewarded', header: t('referrals.ranking.rewarded') },
  { accessorKey: 'earned_usd', header: t('referrals.ranking.earned') },
])

// ---- Program --------------------------------------------------------------------------------

const form = ref<ReferralProgramForm | null>(null)
watch(() => overview.value?.program, (program) => {
  if (program) form.value = toProgramForm(program)
}, { immediate: true })
const formError = computed(() => (form.value ? programFormError(form.value) : null))
const dirty = computed(() => !!form.value && !!overview.value && JSON.stringify(fromProgramForm(form.value)) !== JSON.stringify(fromProgramForm(toProgramForm(overview.value.program))))
const saving = ref(false)
const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone

async function saveProgram() {
  if (!form.value || formError.value) return
  saving.value = true
  try {
    await request<ReferralProgram>('/admin/referrals/program', { method: 'PUT', body: fromProgramForm(form.value) })
    toast.add({ title: t('referrals.program.saved'), color: 'success' })
    await refreshOverview()
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    saving.value = false
  }
}
</script>

<template>
  <UDashboardPanel id="referrals">
    <template #header>
      <UDashboardNavbar :title="t('nav.referrals')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UBadge
            v-if="overview && !overview.program.enabled"
            color="neutral"
            variant="subtle"
          >
            {{ t('referrals.programOff') }}
          </UBadge>
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
        <template
          v-if="tab === 'list'"
          #right
        >
          <USelect
            v-model="status"
            :items="statusItems"
            class="w-52"
            :aria-label="t('referrals.status')"
          />
          <UInput
            v-model="search"
            icon="i-lucide-search"
            :placeholder="t('referrals.search')"
            class="w-72 max-w-full"
          />
        </template>
      </UDashboardToolbar>
    </template>

    <template #body>
      <p class="text-sm text-(--ui-text-muted)">
        {{ overview ? t('referrals.help', { reward: usdt(overview.program.reward_usd), trips: overview.program.required_trips, days: overview.program.window_days }) : '' }}
      </p>

      <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <UCard>
          <p class="text-sm text-(--ui-text-muted)">
            {{ t('referrals.totals.paid') }}
          </p>
          <p class="text-2xl font-semibold tabular-nums">
            {{ usdt(overview?.paid_usd ?? 0) }}
          </p>
          <p class="text-xs text-(--ui-text-muted)">
            {{ t('referrals.totals.month', { amount: usdt(overview?.month_paid_usd ?? 0) }) }}
          </p>
        </UCard>
        <UCard>
          <p class="text-sm text-(--ui-text-muted)">
            {{ t('referrals.totals.held') }}
          </p>
          <p class="text-2xl font-semibold tabular-nums">
            {{ usdt(overview?.held_usd ?? 0) }}
          </p>
          <p class="text-xs text-(--ui-text-muted)">
            {{ t('referrals.totals.alerts', overview?.alerts ?? 0) }}
          </p>
        </UCard>
        <UCard>
          <p class="text-sm text-(--ui-text-muted)">
            {{ t('referrals.totals.budgetLeft') }}
          </p>
          <p class="text-2xl font-semibold tabular-nums">
            {{ usdt(overview?.budget_left_usd ?? 0) }}
          </p>
          <p class="text-xs text-(--ui-text-muted)">
            {{ t('referrals.totals.budget', { amount: usdt(overview?.program.budget_usd ?? 0) }) }}
          </p>
        </UCard>
        <UCard>
          <p class="text-sm text-(--ui-text-muted)">
            {{ t('referrals.totals.invites') }}
          </p>
          <p class="text-2xl font-semibold tabular-nums">
            {{ formatNumber(overview?.counts.reduce((n, c) => n + c.count, 0) ?? 0, locale) }}
          </p>
          <p class="text-xs text-(--ui-text-muted)">
            {{ t('referrals.totals.breakdown', { pending: count('pending'), rewarded: count('rewarded'), months: overview?.free_months ?? 0 }) }}
          </p>
        </UCard>
      </div>
      <UAlert
        v-for="(n, reason) in overview?.waiting ?? {}"
        :key="reason"
        color="warning"
        variant="subtle"
        icon="i-lucide-hourglass"
        :title="t('referrals.waiting', { n, reason: label(`referrals.reasons.${reason}`, String(reason)) })"
      />

      <!-- Referrals -->
      <template v-if="tab === 'list'">
        <UAlert
          v-if="listError"
          color="error"
          variant="subtle"
          icon="i-lucide-circle-alert"
          :title="apiError(listError)"
        />
        <UTable
          :data="referrals?.items ?? []"
          :columns="columns"
          :loading="listStatus === 'pending'"
          :empty="t('referrals.empty')"
        >
          <template #referrer-cell="{ row }">
            <PartyCell :party="row.original.referrer" />
            <p class="font-mono text-xs text-(--ui-text-muted)">
              {{ row.original.code }}
            </p>
          </template>
          <template #referred-cell="{ row }">
            <PartyCell :party="row.original.referred" />
          </template>
          <template #status-cell="{ row }">
            <UBadge
              :color="referralStatusColor(row.original.status)"
              variant="subtle"
              size="sm"
            >
              {{ label(`referrals.statuses.${row.original.status}`, row.original.status) }}
            </UBadge>
            <p
              v-if="reasonLabel(row.original)"
              class="mt-1 max-w-56 text-xs"
              :class="isReferralAlert(row.original) ? 'text-warning' : 'text-(--ui-text-muted)'"
            >
              {{ reasonLabel(row.original) }}
            </p>
            <p
              v-if="row.original.note"
              class="mt-1 max-w-56 text-xs text-(--ui-text-muted)"
            >
              {{ t('referrals.noteShort', { note: row.original.note }) }}
            </p>
          </template>
          <template #progress-cell="{ row }">
            <template v-if="row.original.reward_kind === 'free_month'">
              <span class="text-xs text-(--ui-text-muted)">{{ t('referrals.legacy') }}</span>
            </template>
            <div
              v-else
              class="w-36"
            >
              <UProgress
                :model-value="referralProgress(row.original)"
                size="sm"
                :color="row.original.status === 'rejected' ? 'neutral' : 'primary'"
              />
              <p class="mt-1 text-xs tabular-nums text-(--ui-text-muted)">
                {{ t('referrals.trips', { n: row.original.trips, required: row.original.required_trips }) }}
              </p>
              <p
                v-if="row.original.deadline_at && row.original.status === 'pending'"
                class="text-xs text-(--ui-text-muted)"
              >
                {{ t('referrals.deadline', { date: formatDate(row.original.deadline_at, locale) }) }}
              </p>
              <p
                v-else-if="!row.original.deadline_at && row.original.status === 'pending'"
                class="text-xs text-(--ui-text-muted)"
              >
                {{ t('referrals.notApproved') }}
              </p>
            </div>
          </template>
          <template #reward_amount-cell="{ row }">
            <span
              v-if="row.original.reward_kind === 'free_month'"
              class="whitespace-nowrap"
            >{{ t('referrals.freeMonth') }}</span>
            <span
              v-else-if="row.original.reward_amount"
              class="whitespace-nowrap tabular-nums"
            >{{ usdt(row.original.reward_amount) }}</span>
            <span
              v-else
              class="text-(--ui-text-muted)"
            >—</span>
          </template>
          <template #created_at-cell="{ row }">
            <span class="whitespace-nowrap">{{ formatDate(row.original.created_at, locale) }}</span>
          </template>
          <template #actions-cell="{ row }">
            <div
              v-if="canManage"
              class="flex justify-end gap-1"
            >
              <UButton
                v-for="value in referralActions(row.original)"
                :key="value"
                size="xs"
                :color="value === 'release' ? 'success' : value === 'reject' ? 'error' : 'neutral'"
                variant="soft"
                :label="value === 'reject' && row.original.status === 'rejected' ? t('referrals.actions.reject.reviewed') : t(`referrals.actions.${value}.button`)"
                @click="act(row.original, value)"
              />
            </div>
          </template>
        </UTable>
        <div class="flex items-center justify-between border-t border-(--ui-border) pt-4">
          <span class="text-sm text-(--ui-text-muted)">
            {{ t('referrals.total', referrals?.total ?? 0) }}
          </span>
          <UPagination
            v-model:page="page"
            :total="referrals?.total ?? 0"
            :items-per-page="limit"
          />
        </div>
      </template>

      <!-- Ranking -->
      <template v-else-if="tab === 'ranking'">
        <UTable
          :data="ranking ?? []"
          :columns="rankingColumns"
          :loading="rankingStatus === 'pending'"
          :empty="t('referrals.empty')"
        >
          <template #position-cell="{ row }">
            <span class="tabular-nums text-(--ui-text-muted)">{{ row.index + 1 }}</span>
          </template>
          <template #user-cell="{ row }">
            <PartyCell :party="row.original.user" />
          </template>
          <template #earned_usd-cell="{ row }">
            <span class="tabular-nums">{{ usdt(row.original.earned_usd) }}</span>
          </template>
        </UTable>
      </template>

      <!-- Program -->
      <template v-else-if="form">
        <UCard class="max-w-3xl">
          <template #header>
            <div class="flex items-center justify-between gap-4">
              <div>
                <h2 class="font-semibold">
                  {{ t('referrals.program.title') }}
                </h2>
                <p class="text-sm text-(--ui-text-muted)">
                  {{ t('referrals.program.help') }}
                </p>
              </div>
              <USwitch
                v-model="form.enabled"
                :label="t('referrals.program.enabled')"
                :disabled="!canManage"
              />
            </div>
          </template>
          <div class="grid gap-4 sm:grid-cols-2">
            <UFormField
              :label="t('referrals.program.reward')"
              :help="t('referrals.program.rewardHelp')"
            >
              <UInputNumber
                v-model="form.reward_usd"
                :min="REFERRAL_LIMITS.reward_usd[0]"
                :max="REFERRAL_LIMITS.reward_usd[1]"
                :step="0.5"
                :format-options="{ minimumFractionDigits: 2, maximumFractionDigits: 2 }"
                :disabled="!canManage"
                class="w-full"
              />
            </UFormField>
            <UFormField
              :label="t('referrals.program.requiredTrips')"
              :help="t('referrals.program.requiredTripsHelp')"
            >
              <UInputNumber
                v-model="form.required_trips"
                :min="REFERRAL_LIMITS.required_trips[0]"
                :max="REFERRAL_LIMITS.required_trips[1]"
                :disabled="!canManage"
                class="w-full"
              />
            </UFormField>
            <UFormField
              :label="t('referrals.program.windowDays')"
              :help="t('referrals.program.windowDaysHelp')"
            >
              <UInputNumber
                v-model="form.window_days"
                :min="REFERRAL_LIMITS.window_days[0]"
                :max="REFERRAL_LIMITS.window_days[1]"
                :disabled="!canManage"
                class="w-full"
              />
            </UFormField>
            <UFormField
              :label="t('referrals.program.monthlyCap')"
              :help="t('referrals.program.monthlyCapHelp')"
            >
              <UInputNumber
                v-model="form.monthly_cap"
                :min="REFERRAL_LIMITS.monthly_cap[0]"
                :max="REFERRAL_LIMITS.monthly_cap[1]"
                :disabled="!canManage"
                class="w-full"
              />
            </UFormField>
            <UFormField
              :label="t('referrals.program.budget')"
              :help="t('referrals.program.budgetHelp', { left: usdt(overview?.budget_left_usd ?? 0) })"
            >
              <UInputNumber
                v-model="form.budget_usd"
                :min="REFERRAL_LIMITS.budget_usd[0]"
                :max="REFERRAL_LIMITS.budget_usd[1]"
                :step="10"
                :format-options="{ minimumFractionDigits: 2, maximumFractionDigits: 2 }"
                :disabled="!canManage"
                class="w-full"
              />
            </UFormField>
            <UFormField
              :label="t('referrals.program.freeMonth')"
              :help="t('referrals.program.freeMonthHelp')"
            >
              <USwitch
                v-model="form.referred_free_month"
                :disabled="!canManage"
              />
            </UFormField>
            <UFormField
              :label="t('referrals.program.startsAt')"
              :help="t('referrals.program.datesHelp', { zone: timeZone })"
            >
              <UInput
                v-model="form.starts_at"
                type="datetime-local"
                :disabled="!canManage"
                class="w-full"
              />
            </UFormField>
            <UFormField :label="t('referrals.program.endsAt')">
              <UInput
                v-model="form.ends_at"
                type="datetime-local"
                :min="form.starts_at || undefined"
                :disabled="!canManage"
                class="w-full"
              />
            </UFormField>
          </div>
          <p class="mt-4 text-sm text-(--ui-text-muted)">
            {{ t('referrals.program.passengers') }}
          </p>
          <template
            v-if="canManage"
            #footer
          >
            <div class="flex items-center justify-end gap-3">
              <span
                v-if="formError"
                class="text-sm text-error"
              >{{ t(formError) }}</span>
              <UButton
                :label="t('referrals.program.save')"
                icon="i-lucide-save"
                :loading="saving"
                :disabled="!dirty || !!formError"
                @click="saveProgram"
              />
            </div>
          </template>
        </UCard>
      </template>

      <UModal
        v-model:open="modalOpen"
        :title="t(`referrals.actions.${action}.title`)"
        :description="actionDescription"
      >
        <template #body>
          <UFormField
            :label="t('referrals.note')"
            :help="t('referrals.noteHelp')"
          >
            <UTextarea
              v-model="note"
              class="w-full"
              :rows="3"
              :maxlength="REFERRAL_NOTE_MAX"
            />
          </UFormField>
        </template>
        <template #footer>
          <div class="flex w-full justify-end gap-2">
            <UButton
              color="neutral"
              variant="ghost"
              :label="t('common.cancel')"
              @click="modalOpen = false"
            />
            <UButton
              :color="action === 'release' ? 'success' : action === 'reject' ? 'error' : 'primary'"
              :label="action === 'reject' ? rejectLabel : t(`referrals.actions.${action}.button`)"
              :loading="busy"
              @click="submitAction"
            />
          </div>
        </template>
      </UModal>
    </template>
  </UDashboardPanel>
</template>
