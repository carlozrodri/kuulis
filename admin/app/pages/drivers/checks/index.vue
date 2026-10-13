<script setup lang="ts">
import type { TableColumn, TableRow } from '@nuxt/ui'
import type { CheckKind, CheckStatus, DriverCheckAdmin, Page } from '~/types/api'
import { CHECK_KINDS, CHECK_STATUSES } from '~/types/api'

definePageMeta({ permission: 'drivers.view' })

const { t, te, locale } = useI18n()
const { request } = useApi()
const route = useRoute()
const router = useRouter()
const auth = useAuth()
const toast = useToast()
const apiError = useApiError()

type Assignee = 'all' | 'mine' | 'unassigned'
const queryString = (key: string) => (typeof route.query[key] === 'string' ? route.query[key] as string : '')

// Filters live in the URL so "back" from a review returns to the same list. Pending first: the work queue.
const initialStatus = queryString('status') as CheckStatus
const status = ref<CheckStatus>(CHECK_STATUSES.includes(initialStatus) ? initialStatus : 'pending')
const initialKind = queryString('kind') as CheckKind
const kind = ref<CheckKind | 'all'>(CHECK_KINDS.includes(initialKind) ? initialKind : 'all')
const initialAssignee = queryString('assignee') as Assignee
const assignee = ref<Assignee>(['mine', 'unassigned'].includes(initialAssignee) ? initialAssignee : 'all')
const page = ref(Math.max(1, Number(queryString('page')) || 1))
const limit = 25

watch([status, kind, assignee], () => {
  page.value = 1
})
watch([status, kind, assignee, page], () => {
  router.replace({
    query: {
      ...(status.value !== 'pending' ? { status: status.value } : {}),
      ...(kind.value !== 'all' ? { kind: kind.value } : {}),
      ...(assignee.value !== 'all' ? { assignee: assignee.value } : {}),
      ...(page.value > 1 ? { page: String(page.value) } : {}),
    },
  })
})

const query = computed(() => ({
  limit,
  offset: (page.value - 1) * limit,
  status: status.value,
  ...(kind.value !== 'all' ? { kind: kind.value } : {}),
  ...(assignee.value === 'mine' ? { mine: true } : {}),
  ...(assignee.value === 'unassigned' ? { unassigned: true } : {}),
}))

const { data, status: fetchStatus, error, refresh } = await useAsyncData(
  'driver-checks',
  () => request<Page<DriverCheckAdmin>>('/admin/drivers/checks', { query: query.value }),
  { watch: [query] },
)

let timer: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  timer = setInterval(() => {
    if (document.visibilityState === 'visible') refresh()
  }, 60_000)
})
onBeforeUnmount(() => clearInterval(timer))

const tabs = computed(() => CHECK_STATUSES.map(value => ({ label: t(`verification.statuses.${value}`), value })))
const kindItems = computed(() => [
  { label: t('verification.allKinds'), value: 'all' },
  ...CHECK_KINDS.map(value => ({ label: t(`verification.kinds.${value}`), value })),
])
const assigneeItems = computed(() => (['all', 'mine', 'unassigned'] as const).map(value => ({ label: t(`verification.assignee.${value}`), value })))

const me = computed(() => auth.user.value?.id ?? null)
const canReview = computed(() => auth.can('drivers.review'))
const isOpen = (check: DriverCheckAdmin) => check.status === 'pending' || check.status === 'requested'
const reasonLabel = (reason: string) => (te(`verification.why.${reason}`) ? t(`verification.why.${reason}`) : reason)

const taking = ref<string | null>(null)
async function take(check: DriverCheckAdmin) {
  if (!me.value) return
  taking.value = check.id
  try {
    await request(`/admin/drivers/checks/${check.id}/assign`, { method: 'POST', body: { user_id: me.value } })
    toast.add({ title: t('verification.toast.assigned'), color: 'success' })
    await refresh()
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    taking.value = null
  }
}

const columns = computed<TableColumn<DriverCheckAdmin>[]>(() => [
  { id: 'waiting', header: t('verification.sentAt') },
  { accessorKey: 'kind', header: t('verification.kind') },
  { id: 'driver', header: t('verification.driver') },
  { accessorKey: 'reason', header: t('verification.why.title') },
  { id: 'assigned', header: t('verification.assignedTo') },
  { accessorKey: 'status', header: t('verification.status') },
  { id: 'actions', header: '' },
])
</script>

<template>
  <UDashboardPanel id="driver-checks">
    <template #header>
      <UDashboardNavbar :title="t('nav.driverChecks')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton
            to="/drivers"
            icon="i-lucide-bike"
            color="neutral"
            variant="ghost"
            :label="t('verification.newApplications')"
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
      </UDashboardToolbar>
      <UDashboardToolbar>
        <template #left>
          <div class="flex flex-wrap items-center gap-2">
            <USelect
              v-model="kind"
              :items="kindItems"
              class="w-56"
              :aria-label="t('verification.kind')"
            />
            <USelect
              v-model="assignee"
              :items="assigneeItems"
              class="w-44"
              :aria-label="t('verification.assignedTo')"
            />
          </div>
        </template>
      </UDashboardToolbar>
    </template>

    <template #body>
      <p class="text-sm text-(--ui-text-muted)">
        {{ t('verification.queueHelp') }}
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
        :loading="fetchStatus === 'pending'"
        :empty="t('verification.empty')"
        :ui="{ tr: 'cursor-pointer' }"
        @select="(_e: Event, row: TableRow<DriverCheckAdmin>) => navigateTo(`/drivers/checks/${row.original.id}`)"
      >
        <template #waiting-cell="{ row }">
          <span class="whitespace-nowrap">{{ formatDate(row.original.submitted_at ?? row.original.requested_at, locale) }}</span>
          <p
            v-if="!row.original.submitted_at"
            class="text-xs text-(--ui-text-muted)"
          >
            {{ t('verification.notSentYet') }}
          </p>
        </template>
        <template #kind-cell="{ row }">
          <span class="flex items-center gap-2 whitespace-nowrap">
            <UIcon
              v-if="row.original.kind === 'selfie'"
              name="i-lucide-scan-face"
              class="size-4"
            />
            <UIcon
              v-else-if="row.original.kind === 'reverification'"
              name="i-lucide-shield-alert"
              class="size-4 text-warning"
            />
            <UIcon
              v-else-if="row.original.kind === 'document_renewal'"
              name="i-lucide-file-clock"
              class="size-4"
            />
            <UIcon
              v-else
              name="i-lucide-bike"
              class="size-4"
            />
            {{ t(`verification.kinds.${row.original.kind}`) }}
          </span>
        </template>
        <template #driver-cell="{ row }">
          <p class="font-medium">
            {{ row.original.driver.full_name || '—' }}
          </p>
          <p class="text-xs text-(--ui-text-muted)">
            {{ row.original.driver.email }}
            <span
              v-if="row.original.driver.plate"
              class="font-mono"
            >· {{ row.original.driver.plate }}</span>
          </p>
        </template>
        <template #reason-cell="{ row }">
          {{ reasonLabel(row.original.reason) }}
        </template>
        <template #assigned-cell="{ row }">
          <span v-if="row.original.assigned_to">
            {{ row.original.assigned_to.id === me ? t('verification.me') : (row.original.assigned_to.full_name || row.original.assigned_to.email) }}
          </span>
          <span
            v-else
            class="text-(--ui-text-muted)"
          >{{ t('verification.unassigned') }}</span>
        </template>
        <template #status-cell="{ row }">
          <UBadge
            :color="checkStatusColor[row.original.status]"
            variant="subtle"
          >
            {{ t(`verification.statuses.${row.original.status}`) }}
          </UBadge>
        </template>
        <template #actions-cell="{ row }">
          <UButton
            v-if="canReview && isOpen(row.original) && row.original.assigned_to?.id !== me"
            size="xs"
            icon="i-lucide-hand"
            color="neutral"
            variant="outline"
            :label="t('verification.take')"
            :loading="taking === row.original.id"
            @click.stop="take(row.original)"
          />
        </template>
      </UTable>

      <div class="flex items-center justify-between border-t border-(--ui-border) pt-4">
        <span class="text-sm text-(--ui-text-muted)">
          {{ t('verification.total', { n: data?.total ?? 0 }) }}
        </span>
        <UPagination
          v-model:page="page"
          :total="data?.total ?? 0"
          :items-per-page="limit"
        />
      </div>
    </template>
  </UDashboardPanel>
</template>
