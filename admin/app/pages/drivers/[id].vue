<script setup lang="ts">
import type { AdminDriver, DocumentKind, DriverDocument } from '~/types/api'
import { DOCUMENT_KINDS } from '~/types/api'
import type { DriverAction } from '~/utils/drivers'

const { t, locale } = useI18n()
const route = useRoute()
const { request } = useApi()
const toast = useToast()
const apiError = useApiError()

const id = computed(() => route.params.id as string)
const { data: driver, refresh, status, error } = await useAsyncData(
  `driver-${id.value}`,
  () => request<AdminDriver>(`/admin/drivers/${id.value}`),
)

const age = computed(() => ageFrom(driver.value?.birth_date))
const actions = computed<DriverAction[]>(() => (driver.value ? driverActions[driver.value.status] : []))
// Documents can be reviewed once the driver has submitted (not while still a draft).
const canReviewDocuments = computed(() => !!driver.value && driver.value.status !== 'draft')

const documents = computed(() => {
  const order = (kind: DocumentKind) => DOCUMENT_KINDS.indexOf(kind)
  return [...(driver.value?.documents ?? [])].sort(
    (a, b) => order(a.kind) - order(b.kind) || a.created_at.localeCompare(b.created_at),
  )
})

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

// One reason modal shared by "reject profile", "suspend profile" and "reject document".
type ReasonTarget = { type: 'reject' | 'suspend' } | { type: 'document', doc: DriverDocument }
const reasonTarget = ref<ReasonTarget | null>(null)
const reason = ref('')
const reasonOpen = computed({
  get: () => reasonTarget.value !== null,
  set: (open: boolean) => {
    if (!open) reasonTarget.value = null
  },
})
const reasonTitle = computed(() => {
  const target = reasonTarget.value
  if (!target) return ''
  if (target.type === 'document') return t('drivers.documents.rejectTitle', { kind: t(`drivers.kinds.${target.doc.kind}`) })
  return t(`drivers.actions.${target.type}Title`)
})

function askReason(target: ReasonTarget) {
  reason.value = ''
  reasonTarget.value = target
}

async function confirmReason() {
  const target = reasonTarget.value
  const text = reason.value.trim()
  if (!target || !text) return
  let ok: boolean
  if (target.type === 'document') {
    ok = await reviewDocument(target.doc, 'rejected', text)
  }
  else {
    ok = await run(
      target.type,
      `/admin/drivers/${id.value}/${target.type}`,
      { reason: text },
      t(target.type === 'reject' ? 'drivers.toast.rejected' : 'drivers.toast.suspended'),
    )
  }
  if (ok) reasonTarget.value = null
}

// ---- Documents -----------------------------------------------------------------------------

function reviewDocument(doc: DriverDocument, docStatus: 'approved' | 'rejected', why: string | null = null) {
  return run(
    `doc-${doc.id}`,
    `/admin/drivers/${id.value}/documents/${doc.id}/review`,
    { status: docStatus, reason: why },
    t(docStatus === 'approved' ? 'drivers.documents.approved' : 'drivers.documents.rejected'),
  )
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
  if (isPreviewableImage(doc.content_type)) preview.value = doc
  else window.open(doc.download_url, '_blank', 'noopener,noreferrer')
}

const failedThumbs = reactive(new Set<string>())
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
              @click="askReason({ type: 'suspend' })"
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
                    v-if="doc.status !== 'approved'"
                    size="xs"
                    icon="i-lucide-check"
                    variant="soft"
                    :label="t('drivers.documents.approve')"
                    :loading="busy === `doc-${doc.id}`"
                    :disabled="busy !== null && busy !== `doc-${doc.id}`"
                    @click="reviewDocument(doc, 'approved')"
                  />
                  <UButton
                    v-if="doc.status !== 'rejected'"
                    size="xs"
                    icon="i-lucide-x"
                    color="error"
                    variant="soft"
                    :label="t('drivers.documents.reject')"
                    :disabled="busy !== null"
                    @click="askReason({ type: 'document', doc })"
                  />
                </div>
              </div>
            </UCard>
          </div>
        </section>
      </div>

      <UModal
        v-model:open="reasonOpen"
        :title="reasonTitle"
        :description="t('drivers.reasonHelp')"
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
          <img
            v-if="preview?.download_url"
            :src="preview.download_url"
            :alt="t(`drivers.kinds.${preview.kind}`)"
            class="mx-auto max-h-[75vh] w-auto rounded-md object-contain"
          >
        </template>
        <template #footer>
          <UButton
            v-if="preview?.download_url"
            :to="preview.download_url"
            target="_blank"
            rel="noopener noreferrer"
            icon="i-lucide-external-link"
            color="neutral"
            variant="outline"
            :label="t('drivers.documents.openNewTab')"
          />
        </template>
      </UModal>
    </template>
  </UDashboardPanel>
</template>
