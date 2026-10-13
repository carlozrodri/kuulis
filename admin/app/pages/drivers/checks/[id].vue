<script setup lang="ts">
import type { DriverCheckAdmin, Page } from '~/types/api'

definePageMeta({ permission: 'drivers.view' })

const { t, te, locale } = useI18n()
const route = useRoute()
const { request } = useApi()
const auth = useAuth()
const toast = useToast()
const apiError = useApiError()
const settings = useVerificationSettings()

const id = computed(() => route.params.id as string)
const { data: check, refresh, status, error } = await useAsyncData(
  () => `driver-check-${id.value}`,
  () => request<DriverCheckAdmin>(`/admin/drivers/checks/${id.value}`),
  { watch: [id] },
)
// The pending queue (oldest first), for "N: next".
const { data: queue, refresh: refreshQueue } = useAsyncData('driver-checks-queue', () =>
  request<Page<DriverCheckAdmin>>('/admin/drivers/checks', { query: { status: 'pending', limit: 100 } }).catch(() => null),
)

const me = computed(() => auth.user.value?.id ?? null)
const canReview = computed(() => auth.can('drivers.review'))
const pending = computed(() => check.value?.status === 'pending')
const decidable = computed(() => canReview.value && pending.value)
const suspends = computed(() => !!check.value && checkSuspends(check.value.kind))
const documentKind = computed(() => check.value?.document?.kind ?? null)
const expiring = computed(() => settings.value.expiring_documents)
const reasonLabel = (reason: string) => (te(`verification.why.${reason}`) ? t(`verification.why.${reason}`) : reason)
const kindLabel = (kind: string) => t(`drivers.kinds.${kind}`)

// ---- Images: what the driver sent (left) and the approved references (right) ----------------

interface Shot { key: string, label: string, url: string | null, contentType: string }

const newShots = computed<Shot[]>(() => {
  const c = check.value
  if (!c) return []
  const shots: Shot[] = c.files.map((file, index) => ({
    key: `file-${index}`,
    label: kindLabel(file.kind),
    url: file.download_url ?? null,
    contentType: file.content_type,
  }))
  if (c.document && !shots.some(s => s.url && s.url === c.document?.download_url)) {
    shots.unshift({ key: c.document.id, label: kindLabel(c.document.kind), url: c.document.download_url ?? null, contentType: c.document.content_type })
  }
  return shots
})
const refShots = computed<Shot[]>(() =>
  (check.value?.references ?? []).map(doc => ({
    key: doc.id,
    label: kindLabel(doc.kind),
    url: doc.download_url ?? null,
    contentType: doc.content_type,
  })),
)

type PaneKey = 'new' | 'ref'
const panes = reactive<Record<PaneKey, { index: number, zoom: number, rotation: number }>>({
  new: { index: 0, zoom: 1, rotation: 0 },
  ref: { index: 0, zoom: 1, rotation: 0 },
})
const activePane = ref<PaneKey>('new')
const shotsOf = (pane: PaneKey) => (pane === 'new' ? newShots.value : refShots.value)
const current = (pane: PaneKey) => shotsOf(pane)[panes[pane].index] ?? null

function select(pane: PaneKey, index: number) {
  activePane.value = pane
  panes[pane].index = index
  panes[pane].zoom = 1
  panes[pane].rotation = 0
}
function step(pane: PaneKey, delta: number) {
  const count = shotsOf(pane).length
  if (count) select(pane, (panes[pane].index + delta + count) % count)
}

// ---- Decision -------------------------------------------------------------------------------

const checklist = computed(() => (check.value ? checkChecklist(check.value.kind, documentKind.value, expiring.value) : []))
const reasons = computed(() => (check.value ? checkReasons(check.value.kind, documentKind.value, expiring.value) : []))
const ticked = ref<Record<string, boolean>>({})
const expiresOn = ref('')
const needsExpiry = computed(() => !!check.value && checkNeedsExpiry(check.value.kind, documentKind.value, expiring.value))
const expiryIssue = computed(() => {
  if (!needsExpiry.value) return null
  if (!isDay(expiresOn.value)) return 'required'
  return expiresOn.value < caracasToday() ? 'past' : null
})
const canApprove = computed(() => decidable.value && checklistComplete(checklist.value, ticked.value) && !expiryIssue.value)

// A new check (not a refresh of this one after assigning): start the review over.
watch(() => check.value?.id, () => {
  ticked.value = {}
  expiresOn.value = check.value?.expires_on ?? ''
  select('new', 0)
  panes.ref.index = 0
  activePane.value = 'new'
}, { immediate: true })

const busy = ref<string | null>(null)
const rejectOpen = ref(false)
const rejectText = ref('')

const nextId = computed(() => nextInQueue((queue.value?.items ?? []).map(c => c.id), id.value))

async function goNext() {
  await refreshQueue()
  if (nextId.value && nextId.value !== id.value) await navigateTo(`/drivers/checks/${nextId.value}`)
  else await navigateTo('/drivers/checks')
}

async function review(decision: 'approved' | 'rejected') {
  if (!check.value) return
  busy.value = decision
  try {
    await request(`/admin/drivers/checks/${check.value.id}/review`, {
      method: 'POST',
      body: {
        status: decision,
        ...(decision === 'rejected' ? { reason: rejectText.value.trim() } : {}),
        ...(decision === 'approved' && needsExpiry.value ? { expires_on: expiresOn.value } : {}),
      },
    })
    toast.add({ title: t(decision === 'approved' ? 'verification.toast.approved' : 'verification.toast.rejected'), color: 'success' })
    rejectOpen.value = false
    await goNext()
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
    await refresh()
  }
  finally {
    busy.value = null
  }
}

function askReject() {
  if (!decidable.value) return
  rejectText.value = ''
  rejectOpen.value = true
}

async function assign(userId: string | null) {
  if (!check.value) return
  busy.value = 'assign'
  try {
    check.value = await request<DriverCheckAdmin>(`/admin/drivers/checks/${check.value.id}/assign`, { method: 'POST', body: { user_id: userId } })
    toast.add({ title: t(userId ? 'verification.toast.assigned' : 'verification.toast.unassigned'), color: 'success' })
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    busy.value = null
  }
}

// ---- Keyboard ---------------------------------------------------------------------------------

function onKey(event: KeyboardEvent) {
  if (rejectOpen.value || busy.value) return
  const index = checklistKey(event, checklist.value.length)
  if (index !== null) {
    if (!decidable.value) return
    const item = checklist.value[index]!
    ticked.value = { ...ticked.value, [item]: !ticked.value[item] }
    event.preventDefault()
    return
  }
  const action = shortcutFor(event)
  if (!action) return
  event.preventDefault()
  const pane = panes[activePane.value]
  switch (action) {
    case 'approve':
      if (canApprove.value) review('approved')
      break
    case 'reject':
      askReject()
      break
    case 'zoomIn':
      pane.zoom = zoomBy(pane.zoom, 1)
      break
    case 'zoomOut':
      pane.zoom = zoomBy(pane.zoom, -1)
      break
    case 'rotate':
      pane.rotation = rotateBy(pane.rotation)
      break
    case 'reset':
      pane.zoom = 1
      pane.rotation = 0
      break
    case 'prev':
      step(activePane.value, -1)
      break
    case 'next':
      step(activePane.value, 1)
      break
    case 'nextCheck':
      if (nextId.value) navigateTo(`/drivers/checks/${nextId.value}`)
      break
  }
}
onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <UDashboardPanel id="driver-check">
    <template #header>
      <UDashboardNavbar :title="check ? t(`verification.kinds.${check.kind}`) : t('nav.driverChecks')">
        <template #leading>
          <UButton
            icon="i-lucide-arrow-left"
            color="neutral"
            variant="ghost"
            :aria-label="t('common.back')"
            to="/drivers/checks"
          />
        </template>
        <template #trailing>
          <UBadge
            v-if="check"
            :color="checkStatusColor[check.status]"
            variant="subtle"
          >
            {{ t(`verification.statuses.${check.status}`) }}
          </UBadge>
        </template>
        <template #right>
          <UButton
            v-if="nextId"
            icon="i-lucide-skip-forward"
            color="neutral"
            variant="outline"
            :label="t('verification.nextCheck')"
            :to="`/drivers/checks/${nextId}`"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <UAlert
        v-if="error && !check"
        color="error"
        variant="subtle"
        icon="i-lucide-circle-alert"
        :title="apiError(error)"
      />
      <div
        v-else-if="status === 'pending' && !check"
        class="grid gap-4 lg:grid-cols-2"
      >
        <USkeleton class="h-96" />
        <USkeleton class="h-96" />
      </div>

      <div
        v-if="check"
        class="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_22rem]"
      >
        <!-- New photos and references, side by side -->
        <section
          v-for="pane in (['new', 'ref'] as const)"
          :key="pane"
          class="min-w-0 space-y-2"
          @click="activePane = pane"
        >
          <div class="flex items-center justify-between gap-2">
            <h2 class="font-semibold">
              {{ pane === 'new' ? t('verification.review.sent') : t('verification.review.references') }}
            </h2>
            <span
              v-if="current(pane)"
              class="text-sm text-(--ui-text-muted)"
            >
              {{ current(pane)!.label }} · {{ panes[pane].index + 1 }} / {{ shotsOf(pane).length }}
            </span>
          </div>
          <ImageViewer
            v-if="current(pane)"
            v-model:zoom="panes[pane].zoom"
            v-model:rotation="panes[pane].rotation"
            :src="current(pane)!.url"
            :content-type="current(pane)!.contentType"
            :alt="current(pane)!.label"
            :active="activePane === pane"
          />
          <p
            v-else
            class="rounded-md border border-dashed border-(--ui-border) p-6 text-center text-sm text-(--ui-text-muted)"
          >
            {{ pane === 'new' ? (check.status === 'requested' ? t('verification.review.waitingPhotos') : t('verification.review.noFiles')) : t('verification.review.noReferences') }}
          </p>
          <div
            v-if="shotsOf(pane).length > 1"
            class="flex flex-wrap gap-2"
          >
            <button
              v-for="(shot, index) in shotsOf(pane)"
              :key="shot.key"
              type="button"
              class="flex size-16 items-center justify-center overflow-hidden rounded-md border bg-(--ui-bg-elevated)"
              :class="panes[pane].index === index ? 'border-primary ring-1 ring-primary' : 'border-(--ui-border)'"
              :title="shot.label"
              :aria-label="shot.label"
              @click.stop="select(pane, index)"
            >
              <img
                v-if="shot.url && isPreviewableImage(shot.contentType)"
                :src="shot.url"
                :alt="shot.label"
                class="size-full object-cover"
              >
              <UIcon
                v-else
                name="i-lucide-file-text"
                class="size-6 text-(--ui-text-muted)"
              />
            </button>
          </div>
        </section>

        <!-- Decision -->
        <aside class="space-y-4">
          <UCard>
            <dl class="grid gap-3 text-sm">
              <div>
                <dt class="text-(--ui-text-muted)">
                  {{ t('verification.driver') }}
                </dt>
                <dd>
                  <NuxtLink
                    :to="`/drivers/${check.driver.id}`"
                    class="font-medium text-primary hover:underline"
                  >
                    {{ check.driver.full_name || check.driver.email }}
                  </NuxtLink>
                  <UBadge
                    :color="driverStatusColor[check.driver.status]"
                    variant="subtle"
                    size="sm"
                    class="ml-2"
                  >
                    {{ t(`drivers.statuses.${check.driver.status}`) }}
                  </UBadge>
                  <p class="text-xs text-(--ui-text-muted)">
                    {{ check.driver.email }}
                  </p>
                </dd>
              </div>
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <dt class="text-(--ui-text-muted)">
                    {{ t('verification.why.title') }}
                  </dt>
                  <dd>{{ reasonLabel(check.reason) }}</dd>
                </div>
                <div>
                  <dt class="text-(--ui-text-muted)">
                    {{ t('verification.currentPlate') }}
                  </dt>
                  <dd class="font-mono">
                    {{ check.driver.plate ?? '—' }}
                  </dd>
                </div>
                <div>
                  <dt class="text-(--ui-text-muted)">
                    {{ t('verification.requestedAt') }}
                  </dt>
                  <dd>{{ formatDate(check.requested_at, locale) }}</dd>
                </div>
                <div>
                  <dt class="text-(--ui-text-muted)">
                    {{ t('verification.sentAt') }}
                  </dt>
                  <dd>{{ formatDate(check.submitted_at, locale) }}</dd>
                </div>
              </div>
              <div>
                <dt class="text-(--ui-text-muted)">
                  {{ t('verification.assignedTo') }}
                </dt>
                <dd class="flex flex-wrap items-center gap-2">
                  <span>{{ check.assigned_to ? (check.assigned_to.id === me ? t('verification.me') : (check.assigned_to.full_name || check.assigned_to.email)) : t('verification.unassigned') }}</span>
                  <template v-if="canReview && (pending || check.status === 'requested')">
                    <UButton
                      v-if="check.assigned_to?.id !== me && me"
                      size="xs"
                      icon="i-lucide-hand"
                      color="neutral"
                      variant="outline"
                      :label="t('verification.take')"
                      :loading="busy === 'assign'"
                      @click="assign(me)"
                    />
                    <UButton
                      v-if="check.assigned_to"
                      size="xs"
                      color="neutral"
                      variant="ghost"
                      :label="t('verification.release')"
                      :loading="busy === 'assign'"
                      @click="assign(null)"
                    />
                  </template>
                </dd>
              </div>
              <div v-if="check.reviewed_at">
                <dt class="text-(--ui-text-muted)">
                  {{ t('verification.reviewedBy') }}
                </dt>
                <dd>
                  {{ check.reviewed_by?.full_name || check.reviewed_by?.email || '—' }} · {{ formatDate(check.reviewed_at, locale) }}
                </dd>
              </div>
              <div v-if="check.result_reason">
                <dt class="text-(--ui-text-muted)">
                  {{ t('drivers.reason') }}
                </dt>
                <dd class="text-error">
                  {{ check.result_reason }}
                </dd>
              </div>
            </dl>
          </UCard>

          <!-- The new moto -->
          <UCard v-if="check.vehicle">
            <template #header>
              <h3 class="text-sm font-medium">
                {{ t('verification.review.newVehicle') }}
              </h3>
            </template>
            <dl class="grid grid-cols-2 gap-3 text-sm">
              <div>
                <dt class="text-(--ui-text-muted)">
                  {{ t('drivers.plate') }}
                </dt>
                <dd class="font-mono">
                  {{ check.vehicle.plate }}
                </dd>
              </div>
              <div>
                <dt class="text-(--ui-text-muted)">
                  {{ t('drivers.vehicleType') }}
                </dt>
                <dd>{{ t(`vehicleTypes.${check.vehicle.type}`) }}</dd>
              </div>
              <div>
                <dt class="text-(--ui-text-muted)">
                  {{ t('drivers.brandModel') }}
                </dt>
                <dd>{{ check.vehicle.brand }} {{ check.vehicle.model }}</dd>
              </div>
              <div>
                <dt class="text-(--ui-text-muted)">
                  {{ t('drivers.year') }}
                </dt>
                <dd>{{ check.vehicle.year }}</dd>
              </div>
              <div>
                <dt class="text-(--ui-text-muted)">
                  {{ t('drivers.color') }}
                </dt>
                <dd>{{ check.vehicle.color }}</dd>
              </div>
            </dl>
          </UCard>

          <UCard v-if="pending">
            <div class="space-y-4">
              <UAlert
                v-if="suspends"
                color="warning"
                variant="subtle"
                icon="i-lucide-triangle-alert"
                :description="t('verification.review.suspendWarning')"
              />
              <UFormField
                v-if="needsExpiry"
                :label="t('verification.expiresOn')"
                :help="t('verification.expiresOnHelp')"
                :error="decidable && expiryIssue ? t(`verification.expiryIssues.${expiryIssue}`) : undefined"
                required
              >
                <UInput
                  v-model="expiresOn"
                  type="date"
                  :disabled="!decidable"
                />
              </UFormField>
              <VerificationChecklist
                v-model="ticked"
                :items="checklist"
                :disabled="!decidable"
              />
              <div class="flex gap-2">
                <UButton
                  icon="i-lucide-check"
                  :label="t('verification.approve')"
                  :disabled="!canApprove"
                  :loading="busy === 'approved'"
                  class="flex-1 justify-center"
                  @click="review('approved')"
                >
                  <template #trailing>
                    <UKbd size="sm">
                      A
                    </UKbd>
                  </template>
                </UButton>
                <UButton
                  icon="i-lucide-x"
                  color="error"
                  variant="soft"
                  :label="t('verification.reject')"
                  :disabled="!decidable || busy !== null"
                  class="flex-1 justify-center"
                  @click="askReject"
                >
                  <template #trailing>
                    <UKbd size="sm">
                      R
                    </UKbd>
                  </template>
                </UButton>
              </div>
              <p
                v-if="decidable && !canApprove"
                class="text-xs text-(--ui-text-muted)"
              >
                {{ t('verification.review.approveHint') }}
              </p>
              <p
                v-if="!canReview"
                class="text-xs text-(--ui-text-muted)"
              >
                {{ t('verification.review.readOnly') }}
              </p>
            </div>
          </UCard>

          <UCard>
            <template #header>
              <h3 class="text-sm font-medium">
                {{ t('verification.shortcuts.title') }}
              </h3>
            </template>
            <ul class="space-y-1.5 text-sm">
              <li
                v-for="shortcut in SHORTCUTS"
                :key="shortcut.action"
                class="flex items-center justify-between gap-2"
              >
                <span class="text-(--ui-text-muted)">{{ t(`verification.shortcuts.${shortcut.action}`) }}</span>
                <span class="flex gap-1">
                  <UKbd
                    v-for="key in shortcut.keys"
                    :key="key"
                    size="sm"
                  >
                    {{ key }}
                  </UKbd>
                </span>
              </li>
            </ul>
            <p class="mt-3 text-xs text-(--ui-text-muted)">
              {{ t('verification.shortcuts.help') }}
            </p>
          </UCard>
        </aside>
      </div>

      <UModal
        v-model:open="rejectOpen"
        :title="check ? t('verification.review.rejectTitle', { kind: t(`verification.kinds.${check.kind}`) }) : ''"
      >
        <template #body>
          <form
            id="check-reject-form"
            class="space-y-4"
            @submit.prevent="review('rejected')"
          >
            <UAlert
              v-if="suspends"
              color="error"
              variant="subtle"
              icon="i-lucide-shield-x"
              :title="t('verification.review.suspendConfirmTitle')"
              :description="t('verification.review.suspendWarning')"
            />
            <RejectionReasonPicker
              v-model="rejectText"
              :reasons="reasons"
            />
          </form>
        </template>
        <template #footer>
          <div class="flex w-full justify-end gap-2">
            <UButton
              color="neutral"
              variant="ghost"
              :label="t('common.cancel')"
              @click="rejectOpen = false"
            />
            <UButton
              type="submit"
              form="check-reject-form"
              color="error"
              :label="suspends ? t('verification.review.rejectAndSuspend') : t('verification.reject')"
              :disabled="!rejectText.trim()"
              :loading="busy === 'rejected'"
            />
          </div>
        </template>
      </UModal>
    </template>
  </UDashboardPanel>
</template>
