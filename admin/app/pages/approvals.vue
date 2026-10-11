<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { ApprovalRead } from '~/types/api'

// Open to the whole team: each person sees the requests they made and those their role can decide.
const { t, te, locale } = useI18n()
const { request } = useApi()
const apiError = useApiError()
const toast = useToast()
const approvalCount = useApprovalCount()

const statusFilter = ref<string>('pending')
const statusItems = computed(() => [
  ...APPROVAL_STATUSES.map(s => ({ label: t(`approvals.status.${s}`), value: s })),
  { label: t('approvals.all'), value: 'all' },
])
const query = computed(() => (statusFilter.value === 'all' ? {} : { status: statusFilter.value }))

const { data: approvals, status, error, refresh } = await useAsyncData(
  'approvals',
  () => request<ApprovalRead[]>('/admin/approvals', { query: query.value }),
  { watch: [query] },
)

const actionLabel = (action: string) => (te(`approvals.actions.${action}`) ? t(`approvals.actions.${action}`) : action)

const columns = computed<TableColumn<ApprovalRead>[]>(() => [
  { accessorKey: 'created_at', header: t('approvals.date') },
  { id: 'request', header: t('approvals.request') },
  { id: 'requester', header: t('approvals.requester') },
  { id: 'status', header: t('approvals.state') },
  { id: 'actions', header: '' },
])

// ---- Decide -----------------------------------------------------------------------------------
const deciding = ref<{ approval: ApprovalRead, mode: 'approve' | 'reject' } | null>(null)
const decisionOpen = computed({
  get: () => deciding.value !== null,
  set: (value) => {
    if (!value) deciding.value = null
  },
})
const note = ref('')
const saving = ref(false)
function decide(approval: ApprovalRead, mode: 'approve' | 'reject') {
  note.value = ''
  deciding.value = { approval, mode }
}
const canSubmit = computed(() => deciding.value?.mode === 'approve' || note.value.trim().length > 0)

async function submit() {
  if (!deciding.value || !canSubmit.value) return
  const { approval, mode } = deciding.value
  saving.value = true
  try {
    await request(`/admin/approvals/${approval.id}/${mode}`, { method: 'POST', body: { note: note.value.trim() } })
    toast.add({ title: t(mode === 'approve' ? 'approvals.approved' : 'approvals.rejected'), color: 'success' })
    deciding.value = null
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    saving.value = false
    await Promise.all([refresh(), approvalCount.refresh()])
  }
}

const payloadRows = (approval: ApprovalRead) =>
  Object.entries(approval.payload).map(([key, value]) => ({ key, value: auditValue(value) }))
</script>

<template>
  <UDashboardPanel id="approvals">
    <template #header>
      <UDashboardNavbar :title="t('nav.approvals')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <USelect
            v-model="statusFilter"
            :items="statusItems"
            class="w-40"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <p class="text-sm text-(--ui-text-muted)">
        {{ t('approvals.help') }}
      </p>
      <UAlert
        v-if="error"
        color="error"
        variant="subtle"
        icon="i-lucide-circle-alert"
        :title="apiError(error)"
      />
      <UTable
        :data="approvals ?? []"
        :columns="columns"
        :loading="status === 'pending'"
        :empty="t('approvals.empty')"
      >
        <template #created_at-cell="{ row }">
          <span class="whitespace-nowrap">{{ formatDate(row.original.created_at, locale) }}</span>
        </template>
        <template #request-cell="{ row }">
          <div class="max-w-md space-y-1">
            <p class="font-medium">
              {{ actionLabel(row.original.action) }}
            </p>
            <p class="text-sm">
              {{ row.original.summary }}
            </p>
            <p
              v-if="row.original.reason"
              class="text-xs text-(--ui-text-muted)"
            >
              {{ t('approvals.reason') }}: {{ row.original.reason }}
            </p>
            <details class="text-xs">
              <summary class="cursor-pointer text-(--ui-text-muted)">
                {{ t('approvals.detail') }}
              </summary>
              <dl class="mt-1 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
                <template
                  v-for="item in payloadRows(row.original)"
                  :key="item.key"
                >
                  <dt class="font-mono text-(--ui-text-muted)">
                    {{ item.key }}
                  </dt>
                  <dd class="font-mono break-all">
                    {{ item.value }}
                  </dd>
                </template>
              </dl>
            </details>
          </div>
        </template>
        <template #requester-cell="{ row }">
          <span class="text-sm">{{ row.original.requested_by_email }}</span>
        </template>
        <template #status-cell="{ row }">
          <div class="space-y-1">
            <UBadge
              :color="approvalColor(row.original.status)"
              variant="subtle"
            >
              {{ t(`approvals.status.${row.original.status}`) }}
            </UBadge>
            <p
              v-if="row.original.decided_by_email"
              class="text-xs text-(--ui-text-muted)"
            >
              {{ row.original.decided_by_email }} · {{ formatDate(row.original.decided_at, locale) }}
            </p>
            <p
              v-else-if="row.original.status === 'pending'"
              class="text-xs text-(--ui-text-muted)"
            >
              {{ t('approvals.expires', { date: formatDate(row.original.expires_at, locale) }) }}
            </p>
            <p
              v-if="row.original.decision_note"
              class="text-xs"
            >
              “{{ row.original.decision_note }}”
            </p>
          </div>
        </template>
        <template #actions-cell="{ row }">
          <div class="flex justify-end gap-2">
            <template v-if="row.original.can_decide">
              <UButton
                size="sm"
                icon="i-lucide-check"
                :label="t('approvals.approve')"
                @click="decide(row.original, 'approve')"
              />
              <UButton
                size="sm"
                color="error"
                variant="soft"
                icon="i-lucide-x"
                :label="t('approvals.reject')"
                @click="decide(row.original, 'reject')"
              />
            </template>
            <span
              v-else-if="row.original.status === 'pending'"
              class="text-xs text-(--ui-text-muted)"
            >
              {{ t('approvals.waitingOther') }}
            </span>
            <UButton
              v-if="approvalLink(row.original)"
              size="sm"
              color="neutral"
              variant="ghost"
              icon="i-lucide-external-link"
              :to="approvalLink(row.original)!"
              :aria-label="t('approvals.open')"
            />
          </div>
        </template>
      </UTable>

      <UModal
        v-model:open="decisionOpen"
        :title="deciding?.mode === 'reject' ? t('approvals.rejectTitle') : t('approvals.approveTitle')"
        :description="deciding ? `${actionLabel(deciding.approval.action)} · ${deciding.approval.summary}` : ''"
      >
        <template #body>
          <form
            id="decision-form"
            class="space-y-3"
            @submit.prevent="submit"
          >
            <p
              v-if="deciding?.mode === 'approve'"
              class="text-sm"
            >
              {{ t('approvals.approveHint', { email: deciding.approval.requested_by_email }) }}
            </p>
            <UFormField
              :label="deciding?.mode === 'reject' ? t('approvals.rejectNote') : t('approvals.note')"
              :required="deciding?.mode === 'reject'"
            >
              <UTextarea
                v-model="note"
                :maxlength="500"
                :rows="3"
                class="w-full"
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
              @click="deciding = null"
            />
            <UButton
              type="submit"
              form="decision-form"
              :color="deciding?.mode === 'reject' ? 'error' : 'primary'"
              :label="deciding?.mode === 'reject' ? t('approvals.reject') : t('approvals.approve')"
              :loading="saving"
              :disabled="!canSubmit"
            />
          </div>
        </template>
      </UModal>
    </template>
  </UDashboardPanel>
</template>
