<script setup lang="ts">
import type { PersonSummary, ReportAdminDetail, ReportNote, ReportPriority, ReportUpdate } from '~/types/api'
import { REPORT_PRIORITIES } from '~/types/api'

const { t, locale } = useI18n()
const route = useRoute()
const { request } = useApi()
const auth = useAuth()
const toast = useToast()
const apiError = useApiError()
const reportCounts = useReportCounts()

const id = computed(() => route.params.id as string)
const { data: report, refresh, status, error } = await useAsyncData(
  `report-${id.value}`,
  () => request<ReportAdminDetail>(`/admin/reports/${id.value}`),
)

const closed = computed(() => !!report.value && isClosedReport(report.value.status))
const urgent = computed(() => report.value?.priority === 'urgent' && !closed.value)
const me = computed(() => auth.user.value?.id ?? null)
const assignedToMe = computed(() => !!me.value && report.value?.assigned_to?.id === me.value)

// Oldest first, like a conversation.
const notes = computed(() => [...(report.value?.notes ?? [])].sort((a, b) => a.created_at.localeCompare(b.created_at)))

async function reload() {
  await refresh()
  reportCounts.refresh()
}

// ---- PATCH: status / priority / assignee ------------------------------------------------------

const busy = ref<string | null>(null)

async function update(key: string, body: ReportUpdate, success: string) {
  busy.value = key
  try {
    await request(`/admin/reports/${id.value}`, { method: 'PATCH', body })
    toast.add({ title: success, color: 'success' })
    await reload()
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    busy.value = null
  }
}

const priorityItems = computed(() => REPORT_PRIORITIES.map(value => ({ label: t(`reports.priorities.${value}`), value })))
function setPriority(value: ReportPriority) {
  if (value !== report.value?.priority) update('priority', { priority: value }, t('reports.toast.priority'))
}
const startReview = () => update('status', { status: 'in_review' }, t('reports.toast.inReview'))
const backToOpen = () => update('status', { status: 'open' }, t('reports.toast.open'))
// Taking a report moves it to "in review" as well, which is what assigning it means in practice.
const assignToMe = () => update('assign', {
  assigned_to_id: me.value,
  ...(report.value?.status === 'open' ? { status: 'in_review' as const } : {}),
}, t('reports.toast.assigned'))
const unassign = () => update('assign', { assigned_to_id: null }, t('reports.toast.unassigned'))

async function reopen() {
  busy.value = 'reopen'
  try {
    await request(`/admin/reports/${id.value}/reopen`, { method: 'POST' })
    toast.add({ title: t('reports.toast.reopened'), color: 'success' })
    await reload()
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    busy.value = null
  }
}

// ---- Notes ----------------------------------------------------------------------------------

const noteBody = ref('')
async function addNote() {
  const body = noteBody.value.trim()
  if (!body) return
  busy.value = 'note'
  try {
    await request<ReportNote>(`/admin/reports/${id.value}/notes`, { method: 'POST', body: { body } })
    noteBody.value = ''
    await refresh()
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    busy.value = null
  }
}

const noteIcon = (note: ReportNote) =>
  ({ note: 'i-lucide-message-square', status: 'i-lucide-git-commit-horizontal', suspension: 'i-lucide-user-x' } as Record<string, string>)[note.kind]
  ?? 'i-lucide-info'

// ---- Resolve / dismiss ----------------------------------------------------------------------

const resolveKind = ref<'resolved' | 'dismissed' | null>(null)
const resolution = ref('')
const resolveOpen = computed({
  get: () => resolveKind.value !== null,
  set: (open: boolean) => {
    if (!open) resolveKind.value = null
  },
})
const resolutionLength = computed(() => resolution.value.trim().length)
const canResolve = computed(() => resolutionLength.value >= RESOLUTION_MIN && resolutionLength.value <= RESOLUTION_MAX)

function askResolve(kind: 'resolved' | 'dismissed') {
  resolution.value = ''
  resolveKind.value = kind
}

async function confirmResolve() {
  const kind = resolveKind.value
  if (!kind || !canResolve.value) return
  busy.value = 'resolve'
  try {
    await request(`/admin/reports/${id.value}/resolve`, { method: 'POST', body: { status: kind, resolution: resolution.value.trim() } })
    toast.add({ title: t(kind === 'resolved' ? 'reports.toast.resolved' : 'reports.toast.dismissed'), color: 'success' })
    resolveKind.value = null
    await reload()
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    busy.value = null
  }
}

// ---- Suspension from the report ---------------------------------------------------------------

const suspendTarget = ref<PersonSummary | null>(null)
const suspendOpen = computed({
  get: () => suspendTarget.value !== null,
  set: (open: boolean) => {
    if (!open) suspendTarget.value = null
  },
})

// ---- Ride ---------------------------------------------------------------------------------------

const ride = computed(() => report.value?.ride ?? null)
const ridePassenger = computed(() => ride.value?.passenger_name || personName(ride.value?.passenger))
const rideDriver = computed(() => ride.value?.driver_name || personName(ride.value?.driver))
</script>

<template>
  <UDashboardPanel id="report-detail">
    <template #header>
      <UDashboardNavbar :title="report ? t('reports.detailTitle', { category: t(`reports.categories.${report.category}`, report.category) }) : t('nav.reports')">
        <template #leading>
          <UButton
            icon="i-lucide-arrow-left"
            color="neutral"
            variant="ghost"
            :aria-label="t('common.back')"
            to="/reports"
          />
        </template>
        <template #trailing>
          <template v-if="report">
            <UBadge
              :color="reportStatusColor[report.status] ?? 'neutral'"
              variant="subtle"
            >
              {{ t(`reports.statuses.${report.status}`, report.status) }}
            </UBadge>
            <UBadge
              v-if="report.priority === 'urgent'"
              color="error"
              :variant="urgent ? 'solid' : 'subtle'"
              icon="i-lucide-siren"
            >
              {{ t('reports.priorities.urgent') }}
            </UBadge>
          </template>
        </template>
        <template #right>
          <template v-if="report">
            <template v-if="!closed">
              <UButton
                icon="i-lucide-check"
                :label="t('reports.actions.resolve')"
                @click="askResolve('resolved')"
              />
              <UButton
                icon="i-lucide-x"
                color="neutral"
                variant="outline"
                :label="t('reports.actions.dismiss')"
                @click="askResolve('dismissed')"
              />
            </template>
            <UButton
              v-else
              icon="i-lucide-rotate-ccw"
              color="neutral"
              variant="outline"
              :label="t('reports.actions.reopen')"
              :loading="busy === 'reopen'"
              @click="reopen"
            />
          </template>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <UAlert
        v-if="error && !report"
        color="error"
        variant="subtle"
        icon="i-lucide-circle-alert"
        :title="apiError(error)"
      />
      <div
        v-else-if="status === 'pending' && !report"
        class="grid gap-4 lg:grid-cols-3"
      >
        <USkeleton class="h-64 lg:col-span-2" />
        <USkeleton class="h-64" />
      </div>

      <div
        v-if="report"
        class="grid gap-6 lg:grid-cols-3"
      >
        <!-- Main column -->
        <div class="grid content-start gap-6 lg:col-span-2">
          <UCard :class="urgent ? 'ring-2 ring-error/60' : ''">
            <div class="space-y-4">
              <div class="flex flex-wrap items-center gap-2 text-sm">
                <UIcon
                  :name="reportCategoryIcon[report.category] ?? 'i-lucide-flag'"
                  class="size-5"
                  :class="urgent ? 'text-error' : 'text-(--ui-text-muted)'"
                />
                <span class="font-semibold">{{ t(`reports.categories.${report.category}`, report.category) }}</span>
                <span class="text-(--ui-text-muted)">· {{ t(`reports.categoryHelp.${report.category}`, '') }}</span>
              </div>
              <blockquote class="border-l-4 border-(--ui-border-accented) pl-4 text-base whitespace-pre-wrap break-words">
                {{ report.description }}
              </blockquote>
              <dl class="grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
                <div>
                  <dt class="text-(--ui-text-muted)">
                    {{ t('reports.createdAt') }}
                  </dt>
                  <dd>{{ formatDate(report.created_at, locale) }}</dd>
                </div>
                <div>
                  <dt class="text-(--ui-text-muted)">
                    {{ t('reports.reportedFrom') }}
                  </dt>
                  <dd>{{ t(`reports.reporterRole.${report.reporter_role ?? 'general'}`) }}</dd>
                </div>
                <div>
                  <dt class="text-(--ui-text-muted)">
                    {{ t('reports.updatedAt') }}
                  </dt>
                  <dd>{{ formatDate(report.updated_at, locale) }}</dd>
                </div>
                <div v-if="report.resolved_at">
                  <dt class="text-(--ui-text-muted)">
                    {{ t('reports.resolvedAt') }}
                  </dt>
                  <dd>{{ formatDate(report.resolved_at, locale) }}</dd>
                </div>
              </dl>
              <UAlert
                v-if="report.resolution"
                :color="report.status === 'resolved' ? 'success' : 'neutral'"
                variant="subtle"
                icon="i-lucide-message-square-reply"
                :title="t('reports.resolutionSent')"
                :description="report.resolution"
              />
            </div>
          </UCard>

          <!-- People -->
          <div
            class="grid gap-6"
            :class="report.reported_summary ? 'md:grid-cols-2' : ''"
          >
            <PersonSummaryCard
              :summary="report.reporter_summary"
              :title="t('reports.reporter')"
              @suspend="suspendTarget = report.reporter_summary"
            />
            <PersonSummaryCard
              v-if="report.reported_summary"
              :summary="report.reported_summary"
              :title="t('reports.reported')"
              highlight
              @suspend="suspendTarget = report.reported_summary"
            />
          </div>

          <!-- Notes -->
          <UCard>
            <template #header>
              <div class="flex items-center justify-between gap-2">
                <h2 class="font-semibold">
                  {{ t('reports.notes.title') }}
                </h2>
                <span class="text-xs text-(--ui-text-muted)">{{ t('reports.notes.internal') }}</span>
              </div>
            </template>
            <p
              v-if="!notes.length"
              class="text-sm text-(--ui-text-muted)"
            >
              {{ t('reports.notes.empty') }}
            </p>
            <ol
              v-else
              class="space-y-3"
            >
              <li
                v-for="note in notes"
                :key="note.id"
                class="flex gap-3"
              >
                <span
                  class="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full"
                  :class="note.kind === 'note'
                    ? 'bg-primary/10 text-primary'
                    : note.kind === 'suspension' ? 'bg-error/10 text-error' : 'bg-(--ui-bg-elevated) text-(--ui-text-muted)'"
                >
                  <UIcon
                    :name="noteIcon(note)"
                    class="size-4"
                  />
                </span>
                <div
                  v-if="note.kind === 'note'"
                  class="min-w-0 flex-1 rounded-lg bg-(--ui-bg-elevated) px-3 py-2 text-sm"
                >
                  <p class="mb-0.5 text-xs font-medium text-(--ui-text-muted)">
                    {{ note.author?.name || note.author?.email || t('reports.notes.staff') }} · {{ formatDate(note.created_at, locale) }}
                  </p>
                  <p class="whitespace-pre-wrap break-words">
                    {{ note.body }}
                  </p>
                </div>
                <div
                  v-else
                  class="min-w-0 flex-1 py-1 text-sm text-(--ui-text-muted) italic"
                >
                  <span class="whitespace-pre-wrap break-words">{{ note.body }}</span>
                  <span class="text-xs not-italic">
                    · {{ note.author?.name || note.author?.email || t('reports.notes.system') }} · {{ formatDate(note.created_at, locale) }}
                  </span>
                </div>
              </li>
            </ol>
            <template #footer>
              <form
                class="space-y-2"
                @submit.prevent="addNote"
              >
                <UTextarea
                  v-model="noteBody"
                  class="w-full"
                  :rows="2"
                  autoresize
                  :maxlength="REPORT_NOTE_MAX"
                  :placeholder="t('reports.notes.placeholder')"
                  :aria-label="t('reports.notes.add')"
                />
                <div class="flex items-center justify-between gap-2">
                  <span class="text-xs text-(--ui-text-muted)">{{ t('reports.notes.help') }}</span>
                  <UButton
                    type="submit"
                    size="sm"
                    icon="i-lucide-send"
                    :label="t('reports.notes.add')"
                    :disabled="!noteBody.trim()"
                    :loading="busy === 'note'"
                  />
                </div>
              </form>
            </template>
          </UCard>
        </div>

        <!-- Side column -->
        <div class="grid content-start gap-6">
          <UCard>
            <template #header>
              <h2 class="font-semibold">
                {{ t('reports.manage') }}
              </h2>
            </template>
            <div class="space-y-4 text-sm">
              <div class="space-y-1">
                <p class="text-(--ui-text-muted)">
                  {{ t('reports.status') }}
                </p>
                <div class="flex flex-wrap items-center gap-2">
                  <UBadge
                    :color="reportStatusColor[report.status] ?? 'neutral'"
                    variant="subtle"
                  >
                    {{ t(`reports.statuses.${report.status}`, report.status) }}
                  </UBadge>
                  <UButton
                    v-if="report.status === 'open'"
                    size="xs"
                    variant="soft"
                    icon="i-lucide-eye"
                    :label="t('reports.actions.startReview')"
                    :loading="busy === 'status'"
                    @click="startReview"
                  />
                  <UButton
                    v-if="report.status === 'in_review'"
                    size="xs"
                    color="neutral"
                    variant="ghost"
                    icon="i-lucide-undo-2"
                    :label="t('reports.actions.backToOpen')"
                    :loading="busy === 'status'"
                    @click="backToOpen"
                  />
                </div>
              </div>

              <UFormField :label="t('reports.priority')">
                <USelect
                  :model-value="report.priority"
                  :items="priorityItems"
                  class="w-40"
                  :loading="busy === 'priority'"
                  :disabled="closed"
                  @update:model-value="(v) => setPriority(v as ReportPriority)"
                />
              </UFormField>

              <div class="space-y-1">
                <p class="text-(--ui-text-muted)">
                  {{ t('reports.assignedTo') }}
                </p>
                <p>
                  {{ report.assigned_to ? (report.assigned_to.name || report.assigned_to.email) : t('reports.unassigned') }}
                </p>
                <div
                  v-if="!closed"
                  class="flex flex-wrap gap-2"
                >
                  <UButton
                    v-if="!assignedToMe && me"
                    size="xs"
                    variant="soft"
                    icon="i-lucide-user-round-check"
                    :label="t('reports.actions.assignToMe')"
                    :loading="busy === 'assign'"
                    @click="assignToMe"
                  />
                  <UButton
                    v-if="report.assigned_to"
                    size="xs"
                    color="neutral"
                    variant="ghost"
                    icon="i-lucide-user-round-x"
                    :label="t('reports.actions.unassign')"
                    :loading="busy === 'assign'"
                    @click="unassign"
                  />
                </div>
              </div>

              <div
                v-if="!closed"
                class="space-y-2 border-t border-(--ui-border) pt-4"
              >
                <div class="flex flex-wrap gap-2">
                  <UButton
                    icon="i-lucide-check"
                    :label="t('reports.actions.resolve')"
                    @click="askResolve('resolved')"
                  />
                  <UButton
                    icon="i-lucide-x"
                    color="neutral"
                    variant="outline"
                    :label="t('reports.actions.dismiss')"
                    @click="askResolve('dismissed')"
                  />
                </div>
                <p class="text-xs text-(--ui-text-muted)">
                  {{ t('reports.resolveHint') }}
                </p>
              </div>
            </div>
          </UCard>

          <UCard>
            <template #header>
              <div class="flex items-center justify-between gap-2">
                <h2 class="font-semibold">
                  {{ t('reports.rideTitle') }}
                </h2>
                <UButton
                  v-if="ride"
                  size="xs"
                  color="neutral"
                  variant="ghost"
                  trailing-icon="i-lucide-arrow-right"
                  :label="t('reports.openRide')"
                  :to="`/rides/${ride.id}`"
                />
              </div>
            </template>
            <div
              v-if="ride"
              class="space-y-3 text-sm"
            >
              <div class="flex flex-wrap items-center justify-between gap-2">
                <UBadge
                  :color="rideStatusColor(ride.status)"
                  variant="subtle"
                >
                  {{ t(`rides.statuses.${ride.status}`, ride.status) }}
                </UBadge>
                <span class="font-medium">{{ formatMoney(ride.fare, locale) }}</span>
              </div>
              <p class="text-(--ui-text-muted)">
                {{ formatDate(ride.requested_at, locale) }}
              </p>
              <div class="space-y-1 text-xs">
                <p class="truncate">
                  <UIcon
                    name="i-lucide-circle-dot"
                    class="mr-1 align-middle text-primary"
                  />{{ shortAddress(ride.pickup) }}
                </p>
                <p class="truncate">
                  <UIcon
                    name="i-lucide-map-pin"
                    class="mr-1 align-middle text-error"
                  />{{ shortAddress(ride.dropoff) }}
                </p>
              </div>
              <dl class="grid grid-cols-2 gap-2">
                <div>
                  <dt class="text-(--ui-text-muted)">
                    {{ t('rides.passenger') }}
                  </dt>
                  <dd>{{ ridePassenger }}</dd>
                </div>
                <div>
                  <dt class="text-(--ui-text-muted)">
                    {{ t('rides.driver') }}
                  </dt>
                  <dd>{{ rideDriver }}</dd>
                </div>
                <div v-if="ride.driver?.vehicle">
                  <dt class="text-(--ui-text-muted)">
                    {{ t('drivers.plate') }}
                  </dt>
                  <dd class="font-mono">
                    {{ ride.driver.vehicle.plate }}
                  </dd>
                </div>
                <div>
                  <dt class="text-(--ui-text-muted)">
                    {{ t('rides.paymentMethod') }}
                  </dt>
                  <dd>{{ t(`paymentMethods.${ride.payment_method}`, ride.payment_method) }}</dd>
                </div>
              </dl>
            </div>
            <p
              v-else
              class="text-sm text-(--ui-text-muted)"
            >
              {{ t('reports.noRide') }}
            </p>
          </UCard>
        </div>
      </div>

      <SuspendUserModal
        v-if="suspendTarget && report"
        v-model:open="suspendOpen"
        :user-id="suspendTarget.user_id"
        :name="suspendTarget.name || suspendTarget.email"
        :report-id="report.id"
        :current="isSuspensionInForce(suspendTarget.suspension) ? suspendTarget.suspension : null"
        @suspended="refresh"
      />

      <UModal
        v-model:open="resolveOpen"
        :title="resolveKind ? t(`reports.resolve.${resolveKind}Title`) : ''"
        :description="resolveKind ? t(`reports.resolve.${resolveKind}Help`) : ''"
      >
        <template #body>
          <form
            id="resolve-report-form"
            class="space-y-3"
            @submit.prevent="confirmResolve"
          >
            <UAlert
              color="info"
              variant="subtle"
              icon="i-lucide-eye"
              :title="t('reports.resolve.visible', { name: report?.reporter?.name || report?.reporter?.email || '' })"
              :description="t('reports.resolve.visibleHelp')"
            />
            <UFormField
              :label="t('reports.resolve.resolution')"
              :help="t('reports.resolve.resolutionHelp', { min: RESOLUTION_MIN, max: RESOLUTION_MAX })"
              required
            >
              <UTextarea
                v-model="resolution"
                class="w-full"
                :rows="4"
                :maxlength="RESOLUTION_MAX"
                autofocus
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
              @click="resolveOpen = false"
            />
            <UButton
              type="submit"
              form="resolve-report-form"
              :color="resolveKind === 'dismissed' ? 'neutral' : 'primary'"
              :label="resolveKind ? t(`reports.resolve.${resolveKind}Confirm`) : ''"
              :disabled="!canResolve"
              :loading="busy === 'resolve'"
            />
          </div>
        </template>
      </UModal>
    </template>
  </UDashboardPanel>
</template>
