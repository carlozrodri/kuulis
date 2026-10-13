<script setup lang="ts">
import type { AdminDriver, DocumentKind, DriverCheck, DriverDocument } from '~/types/api'
import { DOCUMENT_KINDS } from '~/types/api'
import type { DriverAction } from '~/utils/drivers'

definePageMeta({ permission: 'drivers.view' })

const { t, te, locale } = useI18n()
const route = useRoute()
const { request } = useApi()
const auth = useAuth()
const toast = useToast()
const apiError = useApiError()
const settings = useVerificationSettings()

const id = computed(() => route.params.id as string)
const { data: driver, refresh, status, error } = await useAsyncData(
  `driver-${id.value}`,
  () => request<AdminDriver>(`/admin/drivers/${id.value}`),
)

const age = computed(() => ageFrom(driver.value?.birth_date))
// Phase 1B: only shown once the API returns a rating (drivers without trips have none).
const rating = computed(() => (driver.value?.rating_count === 0 ? null : formatRating(driver.value?.rating_avg)))
const actions = computed<DriverAction[]>(() => (driver.value ? driverActions[driver.value.status] : []))
// Documents can be reviewed once the driver has submitted (not while still a draft).
const canReviewDocuments = computed(() => !!driver.value && driver.value.status !== 'draft')
const canReview = computed(() => auth.can('drivers.review'))
const me = computed(() => auth.user.value?.id ?? null)
const today = caracasToday()
const expiring = computed(() => settings.value.expiring_documents)

const sortedDocuments = computed(() => {
  const order = (kind: DocumentKind) => DOCUMENT_KINDS.indexOf(kind)
  return [...(driver.value?.documents ?? [])].sort(
    (a, b) => order(a.kind) - order(b.kind) || a.created_at.localeCompare(b.created_at),
  )
})
// Doc 12: replaced files stay for the record, folded under "Historial".
const documents = computed(() => sortedDocuments.value.filter(doc => !doc.superseded_by_id))
const replacedDocuments = computed(() => sortedDocuments.value.filter(doc => doc.superseded_by_id))
const showHistory = ref(false)
const expiryBadges = computed(() => Object.fromEntries(documents.value.map(doc => [doc.id, expiryBadge(doc, today, expiring.value)])))

const checks = computed(() => [...(driver.value?.checks ?? [])].sort((a, b) => b.requested_at.localeCompare(a.requested_at)))
const checkReason = (reason: string) => (te(`verification.why.${reason}`) ? t(`verification.why.${reason}`) : reason)
const pendingVehicleCheck = computed(() => {
  const vehicle = driver.value?.pending_vehicle
  if (!vehicle) return null
  return checks.value.find(c => c.kind === 'vehicle_change' && c.vehicle_id === vehicle.id && (c.status === 'pending' || c.status === 'requested')) ?? null
})
const openChecks = computed(() => checks.value.filter(c => c.status === 'pending' || c.status === 'requested'))
const inductionVisible = computed(() => !!driver.value && (settings.value.induction_required || !!driver.value.induction_completed_at))
const inductionMissing = computed(() => settings.value.induction_required && !driver.value?.induction_completed_at && driver.value?.status === 'pending_review')

// ---- Profile actions ----------------------------------------------------------------------

const busy = ref<string | null>(null)

async function run(key: string, path: string, body: Record<string, unknown> | undefined, success: string) {
  busy.value = key
  try {
    await request(path, { method: 'POST', ...(body ? { body } : {}) })
    toast.add({ title: success, color: 'success' })
    await refresh()
    return true
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
    return false
  }
  finally {
    busy.value = null
  }
}

const approve = () => run('approve', `/admin/drivers/${id.value}/approve`, undefined, t('drivers.toast.approved'))
const reinstate = () => run('reinstate', `/admin/drivers/${id.value}/reinstate`, undefined, t('drivers.toast.reinstated'))
const assign = (userId: string | null) =>
  run('assign', `/admin/drivers/${id.value}/assign`, { user_id: userId }, t(userId ? 'verification.toast.assigned' : 'verification.toast.unassigned'))
const setInduction = (done: boolean) =>
  run('induction', `/admin/drivers/${id.value}/induction`, { done }, t(done ? 'verification.induction.done' : 'verification.induction.undone'))

const reverifyOpen = ref(false)
async function reverify() {
  if (await run('reverify', `/admin/drivers/${id.value}/reverify`, undefined, t('verification.reverify.sent'))) reverifyOpen.value = false
}

// One reason modal shared by "reject profile" and "suspend profile".
type ReasonTarget = { type: 'reject' | 'suspend' }
const reasonTarget = ref<ReasonTarget | null>(null)
const reason = ref('')
const reasonOpen = computed({
  get: () => reasonTarget.value !== null,
  set: (open: boolean) => {
    if (!open) reasonTarget.value = null
  },
})
const reasonTitle = computed(() => (reasonTarget.value ? t(`drivers.actions.${reasonTarget.value.type}Title`) : ''))

function askReason(target: ReasonTarget) {
  reason.value = ''
  reasonTarget.value = target
}

async function confirmReason() {
  const target = reasonTarget.value
  const text = reason.value.trim()
  if (!target || !text) return
  const ok = await run(
    target.type,
    `/admin/drivers/${id.value}/${target.type}`,
    { reason: text },
    t(target.type === 'reject' ? 'drivers.toast.rejected' : 'drivers.toast.suspended'),
  )
  if (ok) reasonTarget.value = null
}

// ---- Documents: review with checklist, predefined reasons and expiry (doc 12) ----------------

const reviewing = ref<DriverDocument | null>(null)
const reviewOpen = computed({
  get: () => reviewing.value !== null,
  set: (open: boolean) => {
    if (!open) reviewing.value = null
  },
})
const rejecting = ref(false)
const ticked = ref<Record<string, boolean>>({})
const expiresOn = ref('')
const rejectText = ref('')
const viewer = reactive({ zoom: 1, rotation: 0 })

const reviewChecklist = computed(() => (reviewing.value ? documentChecklist(reviewing.value.kind, expiring.value) : []))
const reviewReasons = computed(() => (reviewing.value ? documentReasons(reviewing.value.kind, expiring.value) : []))
const reviewNeedsExpiry = computed(() => !!reviewing.value && expiring.value.includes(reviewing.value.kind))
const reviewExpiryIssue = computed(() => {
  if (!reviewNeedsExpiry.value) return null
  if (!isDay(expiresOn.value)) return 'required'
  return expiresOn.value < today ? 'past' : null
})
const canApproveDocument = computed(() => checklistComplete(reviewChecklist.value, ticked.value) && !reviewExpiryIssue.value)

function openReview(doc: DriverDocument, reject = false) {
  ticked.value = {}
  expiresOn.value = doc.expires_on ?? ''
  rejectText.value = ''
  rejecting.value = reject
  viewer.zoom = 1
  viewer.rotation = 0
  reviewing.value = doc
}

async function reviewDocument(docStatus: 'approved' | 'rejected') {
  const doc = reviewing.value
  if (!doc) return
  const body: Record<string, unknown> = { status: docStatus, reason: docStatus === 'rejected' ? rejectText.value.trim() : null }
  if (docStatus === 'approved' && isDay(expiresOn.value)) body.expires_on = expiresOn.value
  const ok = await run(
    `doc-${doc.id}`,
    `/admin/drivers/${id.value}/documents/${doc.id}/review`,
    body,
    t(docStatus === 'approved' ? 'drivers.documents.approved' : 'drivers.documents.rejected'),
  )
  if (ok) reviewing.value = null
}

const preview = ref<DriverDocument | null>(null)
const previewOpen = computed({
  get: () => preview.value !== null,
  set: (open: boolean) => {
    if (!open) preview.value = null
  },
})

function openDocument(doc: DriverDocument) {
  if (!doc.download_url) return
  if (isPreviewableImage(doc.content_type)) {
    viewer.zoom = 1
    viewer.rotation = 0
    preview.value = doc
  }
  else {
    window.open(doc.download_url, '_blank', 'noopener,noreferrer')
  }
}

const failedThumbs = reactive(new Set<string>())

const checkIcon = (check: DriverCheck) => ({
  selfie: 'i-lucide-scan-face',
  reverification: 'i-lucide-shield-alert',
  document_renewal: 'i-lucide-file-clock',
  vehicle_change: 'i-lucide-bike',
})[check.kind]
</script>

<template>
  <UDashboardPanel id="driver-detail">
    <template #header>
      <UDashboardNavbar :title="driver?.user?.full_name || driver?.user?.email || t('nav.drivers')">
        <template #leading>
          <UButton
            icon="i-lucide-arrow-left"
            color="neutral"
            variant="ghost"
            :aria-label="t('common.back')"
            to="/drivers"
          />
        </template>
        <template #trailing>
          <UBadge
            v-if="driver"
            :color="driverStatusColor[driver.status]"
            variant="subtle"
          >
            {{ t(`drivers.statuses.${driver.status}`) }}
          </UBadge>
        </template>
        <template #right>
          <template v-if="driver">
            <UButton
              v-if="actions.includes('approve')"
              icon="i-lucide-check"
              :label="t('drivers.actions.approve')"
              :loading="busy === 'approve'"
              @click="approve"
            />
            <UButton
              v-if="actions.includes('reject')"
              icon="i-lucide-x"
              color="error"
              variant="soft"
              :label="t('drivers.actions.reject')"
              @click="askReason({ type: 'reject' })"
            />
            <UButton
              v-if="actions.includes('suspend')"
              icon="i-lucide-ban"
              color="warning"
              variant="soft"
              :label="t('drivers.actions.suspend')"
              :title="t('drivers.profileSuspensionHelp')"
              @click="askReason({ type: 'suspend' })"
            />
            <UButton
              v-if="driver.status === 'approved' && canReview"
              icon="i-lucide-scan-face"
              color="neutral"
              variant="outline"
              :label="t('verification.reverify.button')"
              @click="reverifyOpen = true"
            />
            <UButton
              v-if="actions.includes('reinstate')"
              icon="i-lucide-rotate-ccw"
              :label="t('drivers.actions.reinstate')"
              :loading="busy === 'reinstate'"
              @click="reinstate"
            />
          </template>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <UAlert
        v-if="error && !driver"
        color="error"
        variant="subtle"
        icon="i-lucide-circle-alert"
        :title="apiError(error)"
      />
      <div
        v-else-if="status === 'pending' && !driver"
        class="grid gap-4 lg:grid-cols-2"
      >
        <USkeleton class="h-48" />
        <USkeleton class="h-48" />
      </div>

      <div
        v-if="driver"
        class="grid gap-6"
      >
        <UAlert
          v-if="driver.rejection_reason && (driver.status === 'rejected' || driver.status === 'suspended')"
          :color="driver.status === 'rejected' ? 'error' : 'warning'"
          variant="subtle"
          icon="i-lucide-message-square-warning"
          :title="driver.status === 'rejected' ? t('drivers.rejectionReason') : t('drivers.suspensionReason')"
          :description="driver.rejection_reason"
        />
        <p
          v-if="driver.status === 'suspended'"
          class="-mt-4 text-xs text-(--ui-text-muted)"
        >
          {{ t('drivers.profileSuspensionHelp') }}
        </p>

        <UAlert
          v-if="inductionMissing"
          color="warning"
          variant="subtle"
          icon="i-lucide-graduation-cap"
          :title="t('verification.induction.missing')"
        />

        <!-- Doc 12: the same cédula, RIF, plate, phone, Binance Pay ID or device on another account -->
        <UAlert
          v-if="driver.duplicates?.length"
          color="error"
          variant="subtle"
          icon="i-lucide-copy"
          :title="t('verification.duplicates.title', { n: driver.duplicates.length })"
        >
          <template #description>
            <p class="mb-2">
              {{ t('verification.duplicates.help') }}
            </p>
            <ul class="space-y-1">
              <li
                v-for="dup in driver.duplicates"
                :key="`${dup.kind}-${dup.user_id}`"
                class="flex flex-wrap items-center gap-2"
              >
                <UBadge
                  color="error"
                  variant="outline"
                  size="sm"
                >
                  {{ t(`verification.duplicates.kinds.${dup.kind}`) }}
                </UBadge>
                <NuxtLink
                  v-if="dup.driver_id"
                  :to="`/drivers/${dup.driver_id}`"
                  class="font-medium hover:underline"
                >
                  {{ dup.name || '—' }}
                </NuxtLink>
                <NuxtLink
                  v-else-if="!dup.deleted"
                  :to="`/users/${dup.user_id}`"
                  class="font-medium hover:underline"
                >
                  {{ dup.name || '—' }}
                </NuxtLink>
                <span
                  v-else
                  class="font-medium"
                >{{ dup.name || '—' }}</span>
                <span class="text-(--ui-text-muted)">{{ dup.email ?? t('verification.duplicates.erased') }}</span>
                <UBadge
                  v-if="dup.deleted"
                  color="neutral"
                  variant="subtle"
                  size="sm"
                >
                  {{ t('verification.duplicates.deleted') }}
                </UBadge>
                <UBadge
                  v-if="dup.suspended"
                  color="error"
                  variant="solid"
                  size="sm"
                >
                  {{ t('verification.duplicates.suspended') }}
                </UBadge>
                <UBadge
                  v-if="dup.driver_status"
                  :color="driverStatusColor[dup.driver_status]"
                  variant="subtle"
                  size="sm"
                >
                  {{ t(`drivers.statuses.${dup.driver_status}`) }}
                </UBadge>
              </li>
            </ul>
          </template>
        </UAlert>

        <div class="grid gap-6 lg:grid-cols-2">
          <UCard>
            <template #header>
              <h2 class="font-semibold">
                {{ t('drivers.personal') }}
              </h2>
            </template>
            <dl class="grid grid-cols-2 gap-4 text-sm">
              <div>
                <dt class="text-(--ui-text-muted)">
                  {{ t('drivers.name') }}
                </dt>
                <dd>{{ driver.user?.full_name || '—' }}</dd>
              </div>
              <div>
                <dt class="text-(--ui-text-muted)">
                  {{ t('drivers.email') }}
                </dt>
                <dd class="break-all">
                  <NuxtLink
                    :to="`/users/${driver.user_id}`"
                    class="text-primary hover:underline"
                  >
                    {{ driver.user?.email ?? '—' }}
                  </NuxtLink>
                </dd>
              </div>
              <div>
                <dt class="text-(--ui-text-muted)">
                  {{ t('drivers.nationalId') }}
                </dt>
                <dd>{{ driver.national_id ?? '—' }}</dd>
              </div>
              <div>
                <dt class="text-(--ui-text-muted)">
                  {{ t('drivers.rif') }}
                </dt>
                <dd>{{ driver.rif ?? '—' }}</dd>
              </div>
              <div>
                <dt class="text-(--ui-text-muted)">
                  {{ t('drivers.phone') }}
                </dt>
                <dd>{{ driver.phone ?? '—' }}</dd>
              </div>
              <div>
                <dt class="text-(--ui-text-muted)">
                  {{ t('drivers.city') }}
                </dt>
                <dd class="capitalize">
                  {{ driver.city ?? '—' }}
                </dd>
              </div>
              <div>
                <dt class="text-(--ui-text-muted)">
                  {{ t('drivers.birthDate') }}
                </dt>
                <dd>{{ formatDay(driver.birth_date, locale) }}</dd>
              </div>
              <div>
                <dt class="text-(--ui-text-muted)">
                  {{ t('drivers.age') }}
                </dt>
                <dd class="flex items-center gap-2">
                  {{ age ?? '—' }}
                  <UBadge
                    v-if="!driver.requirements.age_ok"
                    color="error"
                    variant="subtle"
                    size="sm"
                  >
                    {{ t('drivers.belowMinAge') }}
                  </UBadge>
                </dd>
              </div>
              <div v-if="rating">
                <dt class="text-(--ui-text-muted)">
                  {{ t('drivers.rating') }}
                </dt>
                <dd class="flex items-center gap-1">
                  <UIcon
                    name="i-lucide-star"
                    class="size-4 text-warning"
                  />
                  {{ rating }}
                  <span class="text-(--ui-text-muted)">({{ t('drivers.ratingCount', { n: driver.rating_count ?? 0 }) }})</span>
                </dd>
              </div>
            </dl>
          </UCard>

          <UCard>
            <template #header>
              <h2 class="font-semibold">
                {{ t('drivers.vehicle') }}
              </h2>
            </template>
            <dl
              v-if="driver.vehicle"
              class="grid grid-cols-2 gap-4 text-sm"
            >
              <div>
                <dt class="text-(--ui-text-muted)">
                  {{ t('drivers.vehicleType') }}
                </dt>
                <dd>{{ t(`vehicleTypes.${driver.vehicle.type}`) }}</dd>
              </div>
              <div>
                <dt class="text-(--ui-text-muted)">
                  {{ t('drivers.plate') }}
                </dt>
                <dd class="font-mono">
                  {{ driver.vehicle.plate }}
                </dd>
              </div>
              <div>
                <dt class="text-(--ui-text-muted)">
                  {{ t('drivers.brandModel') }}
                </dt>
                <dd>{{ driver.vehicle.brand }} {{ driver.vehicle.model }}</dd>
              </div>
              <div>
                <dt class="text-(--ui-text-muted)">
                  {{ t('drivers.year') }}
                </dt>
                <dd class="flex items-center gap-2">
                  {{ driver.vehicle.year }}
                  <UBadge
                    v-if="!driver.requirements.vehicle_ok"
                    color="error"
                    variant="subtle"
                    size="sm"
                  >
                    {{ t('drivers.vehicleNotOk') }}
                  </UBadge>
                </dd>
              </div>
              <div>
                <dt class="text-(--ui-text-muted)">
                  {{ t('drivers.color') }}
                </dt>
                <dd>{{ driver.vehicle.color }}</dd>
              </div>
            </dl>
            <p
              v-else
              class="text-sm text-(--ui-text-muted)"
            >
              {{ t('drivers.noVehicle') }}
            </p>
            <div
              v-if="driver.pending_vehicle"
              class="mt-4 rounded-md border border-warning/40 bg-warning/5 p-3 text-sm"
            >
              <div class="flex flex-wrap items-center justify-between gap-2">
                <p class="flex items-center gap-2 font-medium">
                  <UIcon
                    name="i-lucide-repeat"
                    class="size-4 text-warning"
                  />
                  {{ t('verification.pendingVehicle') }}
                </p>
                <UButton
                  v-if="pendingVehicleCheck"
                  size="xs"
                  color="neutral"
                  variant="outline"
                  trailing-icon="i-lucide-arrow-right"
                  :label="t('verification.openCheck')"
                  :to="`/drivers/checks/${pendingVehicleCheck.id}`"
                />
              </div>
              <p class="mt-1">
                {{ t(`vehicleTypes.${driver.pending_vehicle.type}`) }} · {{ driver.pending_vehicle.brand }} {{ driver.pending_vehicle.model }}
                · {{ driver.pending_vehicle.year }} · {{ driver.pending_vehicle.color }} ·
                <span class="font-mono">{{ driver.pending_vehicle.plate }}</span>
              </p>
            </div>
          </UCard>

          <UCard class="lg:col-span-2">
            <dl class="grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
              <div>
                <dt class="text-(--ui-text-muted)">
                  {{ t('drivers.submittedAt') }}
                </dt>
                <dd>{{ formatDate(driver.submitted_at, locale) }}</dd>
              </div>
              <div>
                <dt class="text-(--ui-text-muted)">
                  {{ t('drivers.reviewedAt') }}
                </dt>
                <dd>{{ formatDate(driver.reviewed_at, locale) }}</dd>
              </div>
              <div>
                <dt class="text-(--ui-text-muted)">
                  {{ t('drivers.approvedAt') }}
                </dt>
                <dd>{{ formatDate(driver.approved_at, locale) }}</dd>
              </div>
              <div>
                <dt class="text-(--ui-text-muted)">
                  {{ t('drivers.vehiclePhotos') }}
                </dt>
                <dd>
                  {{ driver.requirements.vehicle_photos }} / {{ driver.requirements.vehicle_photos_required }}
                </dd>
              </div>
            </dl>
          </UCard>
        </div>

        <!-- Doc 12: ongoing verification -->
        <div class="grid gap-6 lg:grid-cols-2">
          <UCard>
            <template #header>
              <h2 class="font-semibold">
                {{ t('verification.card.title') }}
              </h2>
            </template>
            <div class="space-y-4 text-sm">
              <div class="flex flex-wrap items-center gap-2">
                <span class="text-(--ui-text-muted)">{{ t('verification.card.reviewer') }}:</span>
                <span>{{ driver.assigned_to ? (driver.assigned_to.id === me ? t('verification.me') : (driver.assigned_to.full_name || driver.assigned_to.email)) : t('verification.unassigned') }}</span>
                <template v-if="canReview">
                  <UButton
                    v-if="me && driver.assigned_to?.id !== me"
                    size="xs"
                    icon="i-lucide-hand"
                    color="neutral"
                    variant="outline"
                    :label="t('verification.take')"
                    :loading="busy === 'assign'"
                    @click="assign(me)"
                  />
                  <UButton
                    v-if="driver.assigned_to"
                    size="xs"
                    color="neutral"
                    variant="ghost"
                    :label="t('verification.release')"
                    :loading="busy === 'assign'"
                    @click="assign(null)"
                  />
                </template>
              </div>

              <div
                v-if="inductionVisible"
                class="space-y-1"
              >
                <USwitch
                  :model-value="!!driver.induction_completed_at"
                  :label="t('verification.induction.label')"
                  :description="driver.induction_completed_at ? t('verification.induction.doneAt', { date: formatDate(driver.induction_completed_at, locale) }) : t('verification.induction.help')"
                  :disabled="!canReview || busy === 'induction'"
                  @update:model-value="setInduction($event)"
                />
              </div>

              <div
                v-if="driver.verification"
                class="space-y-2"
              >
                <p class="flex items-center gap-2">
                  <UIcon
                    v-if="driver.verification.can_go_online"
                    name="i-lucide-circle-check"
                    class="size-4 text-success"
                  />
                  <UIcon
                    v-else
                    name="i-lucide-circle-x"
                    class="size-4 text-error"
                  />
                  {{ driver.verification.can_go_online ? t('verification.card.canGoOnline') : t('verification.card.blocked') }}
                </p>
                <div
                  v-if="driver.verification.expired.length || driver.verification.missing_expiry.length || driver.verification.required_check_kind"
                  class="flex flex-wrap gap-2"
                >
                  <UBadge
                    v-for="kind in driver.verification.expired"
                    :key="`expired-${kind}`"
                    color="error"
                    variant="subtle"
                    size="sm"
                  >
                    {{ t('verification.card.expired', { kind: t(`drivers.kinds.${kind}`) }) }}
                  </UBadge>
                  <UBadge
                    v-for="kind in driver.verification.missing_expiry"
                    :key="`missing-${kind}`"
                    color="warning"
                    variant="subtle"
                    size="sm"
                  >
                    {{ t('verification.card.missingExpiry', { kind: t(`drivers.kinds.${kind}`) }) }}
                  </UBadge>
                  <UBadge
                    v-if="driver.verification.required_check_kind"
                    color="warning"
                    variant="subtle"
                    size="sm"
                  >
                    {{ t('verification.card.requiredCheck', { kind: t(`verification.kinds.${driver.verification.required_check_kind}`) }) }}
                  </UBadge>
                </div>
              </div>

              <ul
                v-if="openChecks.length"
                class="space-y-1"
              >
                <li
                  v-for="check in openChecks"
                  :key="check.id"
                >
                  <NuxtLink
                    :to="`/drivers/checks/${check.id}`"
                    class="flex items-center gap-2 text-primary hover:underline"
                  >
                    <UIcon
                      :name="checkIcon(check)"
                      class="size-4"
                    />
                    {{ t(`verification.kinds.${check.kind}`) }} · {{ t(`verification.statuses.${check.status}`) }}
                  </NuxtLink>
                </li>
              </ul>
            </div>
          </UCard>

          <UCard>
            <template #header>
              <h2 class="font-semibold">
                {{ t('verification.timeline.title') }}
              </h2>
            </template>
            <p
              v-if="!checks.length"
              class="text-sm text-(--ui-text-muted)"
            >
              {{ t('verification.timeline.empty') }}
            </p>
            <ol
              v-else
              class="relative space-y-4 border-l border-(--ui-border) pl-5"
            >
              <li
                v-for="check in checks"
                :key="check.id"
                class="relative text-sm"
              >
                <span class="absolute -left-[1.85rem] flex size-5 items-center justify-center rounded-full bg-(--ui-bg-elevated)">
                  <UIcon
                    :name="checkIcon(check)"
                    class="size-3.5"
                  />
                </span>
                <div class="flex flex-wrap items-center gap-2">
                  <NuxtLink
                    :to="`/drivers/checks/${check.id}`"
                    class="font-medium hover:underline"
                  >
                    {{ t(`verification.kinds.${check.kind}`) }}
                  </NuxtLink>
                  <UBadge
                    :color="checkStatusColor[check.status]"
                    variant="subtle"
                    size="sm"
                  >
                    {{ t(`verification.statuses.${check.status}`) }}
                  </UBadge>
                </div>
                <p class="text-xs text-(--ui-text-muted)">
                  {{ checkReason(check.reason) }} · {{ formatDate(check.requested_at, locale) }}
                  <template v-if="check.reviewed_at">
                    · {{ t('verification.timeline.reviewed', { date: formatDate(check.reviewed_at, locale) }) }}
                  </template>
                </p>
                <p
                  v-if="check.result_reason"
                  class="text-xs text-error"
                >
                  {{ check.result_reason }}
                </p>
              </li>
            </ol>
          </UCard>
        </div>

        <!-- Phase 1E: account suspension (moderation, any role) — separate from the profile suspension above -->
        <div class="grid gap-6 lg:grid-cols-2">
          <AccountSuspensionCard
            :user-id="driver.user_id"
            :name="driver.user?.full_name || driver.user?.email"
            @changed="refresh"
          />
          <ReportsList :user-id="driver.user_id" />
        </div>

        <!-- Phase 1D: wallet & subscription -->
        <DriverWalletCard
          :user-id="driver.user_id"
          :name="driver.user?.full_name"
        />

        <section class="space-y-3">
          <div class="flex flex-wrap items-center gap-2">
            <h2 class="font-semibold">
              {{ t('drivers.documents.title') }}
            </h2>
            <UBadge
              v-for="kind in driver.requirements.missing_documents"
              :key="kind"
              color="error"
              variant="outline"
              size="sm"
              icon="i-lucide-file-x"
            >
              {{ t('drivers.documents.missing', { kind: t(`drivers.kinds.${kind}`) }) }}
            </UBadge>
          </div>

          <p
            v-if="!documents.length"
            class="text-sm text-(--ui-text-muted)"
          >
            {{ t('drivers.documents.none') }}
          </p>

          <div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
            <UCard
              v-for="doc in documents"
              :key="doc.id"
              :ui="{ body: 'p-0 sm:p-0' }"
            >
              <button
                type="button"
                class="flex aspect-[4/3] w-full items-center justify-center overflow-hidden rounded-t-[calc(var(--ui-radius)*2)] bg-(--ui-bg-elevated) disabled:cursor-not-allowed"
                :disabled="!doc.download_url"
                :aria-label="t('drivers.documents.open')"
                @click="openDocument(doc)"
              >
                <img
                  v-if="doc.download_url && isPreviewableImage(doc.content_type) && !failedThumbs.has(doc.id)"
                  :src="doc.download_url"
                  :alt="t(`drivers.kinds.${doc.kind}`)"
                  loading="lazy"
                  class="size-full object-cover"
                  @error="failedThumbs.add(doc.id)"
                >
                <div
                  v-else
                  class="flex flex-col items-center gap-2 text-(--ui-text-muted)"
                >
                  <UIcon
                    :name="doc.content_type === 'application/pdf' ? 'i-lucide-file-text' : 'i-lucide-file-image'"
                    class="size-10"
                  />
                  <span class="text-xs">{{ doc.download_url ? t('drivers.documents.openNewTab') : t('drivers.documents.unavailable') }}</span>
                </div>
              </button>

              <div class="space-y-3 p-4">
                <div class="flex items-start justify-between gap-2">
                  <div>
                    <p class="font-medium">
                      {{ t(`drivers.kinds.${doc.kind}`) }}
                    </p>
                    <p class="text-xs text-(--ui-text-muted)">
                      {{ formatDate(doc.created_at, locale) }}
                    </p>
                  </div>
                  <UBadge
                    :color="documentStatusColor[doc.status]"
                    variant="subtle"
                    size="sm"
                  >
                    {{ t(`drivers.documents.statuses.${doc.status}`) }}
                  </UBadge>
                </div>
                <div
                  v-if="doc.expires_on || expiryBadges[doc.id]"
                  class="flex flex-wrap items-center gap-1.5 text-xs"
                >
                  <span
                    v-if="doc.expires_on"
                    class="text-(--ui-text-muted)"
                  >{{ t('verification.expiry.until', { date: formatDay(doc.expires_on, locale) }) }}</span>
                  <UBadge
                    v-if="expiryBadges[doc.id]"
                    :color="expiryBadges[doc.id]!.color"
                    variant="subtle"
                    size="sm"
                  >
                    {{ t(`verification.expiry.${expiryBadges[doc.id]!.key}`, { n: Math.abs(expiryBadges[doc.id]!.days ?? 0) }) }}
                  </UBadge>
                  <UBadge
                    v-if="expiryUnconfirmed(doc)"
                    color="info"
                    variant="subtle"
                    size="sm"
                  >
                    {{ t('verification.expiry.unconfirmed') }}
                  </UBadge>
                </div>
                <p
                  v-if="doc.status === 'rejected' && doc.rejection_reason"
                  class="text-xs text-error"
                >
                  {{ doc.rejection_reason }}
                </p>
                <div
                  v-if="canReviewDocuments"
                  class="flex gap-2"
                >
                  <UButton
                    v-if="doc.status !== 'approved' || expiryUnconfirmed(doc) || (!doc.expires_on && expiring.includes(doc.kind))"
                    size="xs"
                    icon="i-lucide-check"
                    variant="soft"
                    :label="doc.status === 'approved' ? t('verification.expiry.confirm') : t('drivers.documents.approve')"
                    :disabled="busy !== null"
                    @click="openReview(doc)"
                  />
                  <UButton
                    v-if="doc.status !== 'rejected'"
                    size="xs"
                    icon="i-lucide-x"
                    color="error"
                    variant="soft"
                    :label="t('drivers.documents.reject')"
                    :disabled="busy !== null"
                    @click="openReview(doc, true)"
                  />
                </div>
              </div>
            </UCard>
          </div>

          <div v-if="replacedDocuments.length">
            <UButton
              color="neutral"
              variant="ghost"
              size="sm"
              :icon="showHistory ? 'i-lucide-chevron-down' : 'i-lucide-chevron-right'"
              :label="t('verification.history', { n: replacedDocuments.length })"
              @click="showHistory = !showHistory"
            />
            <ul
              v-if="showHistory"
              class="mt-2 divide-y divide-(--ui-border) rounded-md border border-(--ui-border) text-sm"
            >
              <li
                v-for="doc in replacedDocuments"
                :key="doc.id"
                class="flex flex-wrap items-center gap-3 p-3"
              >
                <span class="font-medium">{{ t(`drivers.kinds.${doc.kind}`) }}</span>
                <span class="text-xs text-(--ui-text-muted)">{{ formatDate(doc.created_at, locale) }}</span>
                <span
                  v-if="doc.expires_on"
                  class="text-xs text-(--ui-text-muted)"
                >{{ t('verification.expiry.until', { date: formatDay(doc.expires_on, locale) }) }}</span>
                <UBadge
                  :color="documentStatusColor[doc.status]"
                  variant="subtle"
                  size="sm"
                >
                  {{ t(`drivers.documents.statuses.${doc.status}`) }}
                </UBadge>
                <UBadge
                  color="neutral"
                  variant="outline"
                  size="sm"
                >
                  {{ t('verification.replaced') }}
                </UBadge>
                <div class="flex-1" />
                <UButton
                  v-if="doc.download_url"
                  size="xs"
                  color="neutral"
                  variant="ghost"
                  icon="i-lucide-eye"
                  :label="t('drivers.documents.open')"
                  @click="openDocument(doc)"
                />
              </li>
            </ul>
          </div>
        </section>

        <AuditHistoryCard
          entity-type="driver"
          :entity-id="driver.id"
        />
      </div>

      <UModal
        v-model:open="reasonOpen"
        :title="reasonTitle"
        :description="reasonTarget?.type === 'suspend' ? `${t('drivers.reasonHelp')} ${t('drivers.profileSuspensionHelp')}` : t('drivers.reasonHelp')"
      >
        <template #body>
          <form
            id="reason-form"
            @submit.prevent="confirmReason"
          >
            <UFormField
              :label="t('drivers.reason')"
              required
            >
              <UTextarea
                v-model="reason"
                class="w-full"
                :rows="4"
                maxlength="500"
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
              @click="reasonOpen = false"
            />
            <UButton
              type="submit"
              form="reason-form"
              :color="reasonTarget?.type === 'suspend' ? 'warning' : 'error'"
              :label="t('common.confirm')"
              :disabled="!reason.trim()"
              :loading="busy !== null"
            />
          </div>
        </template>
      </UModal>

      <UModal
        v-model:open="previewOpen"
        :title="preview ? t(`drivers.kinds.${preview.kind}`) : ''"
        :ui="{ content: 'sm:max-w-4xl' }"
      >
        <template #body>
          <ImageViewer
            v-if="preview"
            v-model:zoom="viewer.zoom"
            v-model:rotation="viewer.rotation"
            :src="preview.download_url"
            :content-type="preview.content_type"
            :alt="t(`drivers.kinds.${preview.kind}`)"
            height="h-[70vh]"
          />
        </template>
      </UModal>

      <!-- Doc 12: document review with checklist, expiry and predefined reasons -->
      <UModal
        v-model:open="reviewOpen"
        :title="reviewing ? t('verification.documentReview.title', { kind: t(`drivers.kinds.${reviewing.kind}`) }) : ''"
        :ui="{ content: 'sm:max-w-5xl' }"
      >
        <template #body>
          <div
            v-if="reviewing"
            class="grid gap-6 md:grid-cols-[minmax(0,1fr)_20rem]"
          >
            <ImageViewer
              v-model:zoom="viewer.zoom"
              v-model:rotation="viewer.rotation"
              :src="reviewing.download_url"
              :content-type="reviewing.content_type"
              :alt="t(`drivers.kinds.${reviewing.kind}`)"
            />
            <div class="space-y-4">
              <template v-if="!rejecting">
                <UFormField
                  v-if="reviewNeedsExpiry || reviewing.expires_on"
                  :label="t('verification.expiresOn')"
                  :help="t('verification.expiresOnHelp')"
                  :error="reviewExpiryIssue ? t(`verification.expiryIssues.${reviewExpiryIssue}`) : undefined"
                  :required="reviewNeedsExpiry"
                >
                  <UInput
                    v-model="expiresOn"
                    type="date"
                  />
                </UFormField>
                <VerificationChecklist
                  v-model="ticked"
                  :items="reviewChecklist"
                />
              </template>
              <RejectionReasonPicker
                v-else
                v-model="rejectText"
                :reasons="reviewReasons"
              />
            </div>
          </div>
        </template>
        <template #footer>
          <div class="flex w-full flex-wrap justify-end gap-2">
            <UButton
              color="neutral"
              variant="ghost"
              :label="t('common.cancel')"
              @click="reviewOpen = false"
            />
            <template v-if="!rejecting">
              <UButton
                v-if="reviewing?.status !== 'rejected'"
                color="error"
                variant="soft"
                icon="i-lucide-x"
                :label="t('drivers.documents.reject')"
                @click="rejecting = true"
              />
              <UButton
                icon="i-lucide-check"
                :label="reviewing?.status === 'approved' ? t('verification.expiry.confirm') : t('drivers.documents.approve')"
                :disabled="!canApproveDocument"
                :loading="busy !== null"
                @click="reviewDocument('approved')"
              />
            </template>
            <template v-else>
              <UButton
                color="neutral"
                variant="outline"
                icon="i-lucide-list-checks"
                :label="t('verification.documentReview.backToChecklist')"
                @click="rejecting = false"
              />
              <UButton
                color="error"
                icon="i-lucide-x"
                :label="t('drivers.documents.reject')"
                :disabled="!rejectText.trim()"
                :loading="busy !== null"
                @click="reviewDocument('rejected')"
              />
            </template>
          </div>
        </template>
      </UModal>

      <UModal
        v-model:open="reverifyOpen"
        :title="t('verification.reverify.title')"
        :description="t('verification.reverify.help')"
      >
        <template #footer>
          <div class="flex w-full justify-end gap-2">
            <UButton
              color="neutral"
              variant="ghost"
              :label="t('common.cancel')"
              @click="reverifyOpen = false"
            />
            <UButton
              icon="i-lucide-scan-face"
              :label="t('verification.reverify.confirm')"
              :loading="busy === 'reverify'"
              @click="reverify"
            />
          </div>
        </template>
      </UModal>
    </template>
  </UDashboardPanel>
</template>
