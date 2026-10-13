<script setup lang="ts">
import type { ApprovalHeld, AudienceCount, CampaignRead, CampaignTestResult, CampaignUpdate } from '~/types/api'
import { CAMPAIGN_AUDIENCES, CAMPAIGN_CHANNELS } from '~/types/api'
import type { CampaignForm } from '~/utils/campaigns'

definePageMeta({ permission: 'notifications.send' })

const { t, locale } = useI18n()
const { request } = useApi()
const route = useRoute()
const toast = useToast()
const apiError = useApiError()
const approvals = useApprovalCount()

const id = computed(() => route.params.id as string)
const isNew = computed(() => id.value === 'new')

const { data: campaign, status, error } = await useAsyncData(
  `campaign-${id.value}`,
  () => (isNew.value ? Promise.resolve(null) : request<CampaignRead>(`/admin/campaigns/${id.value}`)),
)
const areas = await useServiceAreaNames()

const form = reactive<CampaignForm>(defaultCampaignForm())
const original = ref<string | null>(null)
function load(value: CampaignRead) {
  Object.assign(form, campaignFormFrom(value))
  original.value = JSON.stringify(campaignPayload(form))
}
// Polling brings the same campaign back: only reload the form when it really changed on the server.
watch(campaign, (value, old) => {
  if (value && (!old || old.id !== value.id || old.updated_at !== value.updated_at || old.status !== value.status)) load(value)
}, { immediate: true })

const editable = computed(() => isNew.value || (!!campaign.value && isCampaignEditable(campaign.value.status)))
const dirty = computed(() => isNew.value || JSON.stringify(campaignPayload(form)) !== original.value)
const showIssues = ref(false)
const issues = computed(() => validateCampaign(form))
const sendIssues = computed(() => validateCampaign(form, { forSend: true }))
const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone

// ---- Pickers ------------------------------------------------------------------------------------

const audienceItems = computed(() => CAMPAIGN_AUDIENCES.map(value => ({ label: t(`campaigns.audiences.${value}`), value })))
const areaItems = computed(() => {
  const names = [...areas.value, ...form.cities.filter(c => !areas.value.includes(c))]
  return names.map(name => ({ label: name, value: name }))
})
const localeItems = computed(() => [
  { label: t('campaigns.segment.anyLocale'), value: 'any' },
  { label: t('control.spanish'), value: 'es' },
  { label: t('control.english'), value: 'en' },
])
const channelItems = computed(() => CAMPAIGN_CHANNELS.map(value => ({
  label: t(`campaigns.channels.${value}`),
  description: t(`campaigns.channelsHelp.${value}`),
  value,
})))
const whenItems = computed(() => [
  { label: t('campaigns.schedule.now'), value: 'now' },
  { label: t('campaigns.schedule.later'), value: 'later' },
])

// ---- Live audience count ------------------------------------------------------------------------

const audience = ref<AudienceCount | null>(null)
const counting = ref(false)
const countFailed = ref(false)
const segmentJson = computed(() => JSON.stringify(segmentFromForm(form)))
const segmentValid = computed(() => segmentIssues(form).length === 0)
let countTimer: ReturnType<typeof setTimeout> | undefined
let countSeq = 0
async function countAudience(json: string) {
  const seq = ++countSeq
  counting.value = true
  try {
    const result = await request<AudienceCount>('/admin/campaigns/audience-count', { query: { segment: json } })
    if (seq === countSeq) {
      audience.value = result
      countFailed.value = false
    }
  }
  catch {
    if (seq === countSeq) countFailed.value = true
  }
  finally {
    if (seq === countSeq) counting.value = false
  }
}
watch([segmentJson, segmentValid, editable], ([json, valid, canEdit]) => {
  clearTimeout(countTimer)
  if (!canEdit || !valid) return
  countTimer = setTimeout(() => countAudience(json), 500)
}, { immediate: true })
onBeforeUnmount(() => clearTimeout(countTimer))

// ---- Results polling ----------------------------------------------------------------------------

// Every 5 s while it goes out (or a scheduled one is due), only while the tab is visible.
let pollTimer: ReturnType<typeof setInterval> | undefined
const stopPolling = () => {
  clearInterval(pollTimer)
  pollTimer = undefined
}
async function poll() {
  const current = campaign.value
  if (!current || document.visibilityState !== 'visible') return
  if (current.status === 'scheduled' && current.scheduled_at && new Date(current.scheduled_at).getTime() > Date.now()) return
  try {
    campaign.value = await request<CampaignRead>(`/admin/campaigns/${current.id}`)
  }
  catch {
    // Try again on the next tick.
  }
}
watch(() => campaign.value?.status, (value) => {
  stopPolling()
  if (value === 'sending' || value === 'scheduled') pollTimer = setInterval(poll, CAMPAIGN_POLL_MS)
}, { immediate: true })
onBeforeUnmount(stopPolling)

const rates = computed(() => campaignRates(campaign.value?.stats))

// ---- Actions ------------------------------------------------------------------------------------

const busy = ref<'save' | 'test' | 'send' | 'cancel' | 'duplicate' | 'delete' | null>(null)

/** Creates or updates the campaign when needed; returns it, or null when something failed. */
async function persist(): Promise<CampaignRead | null> {
  if (issues.value.length) {
    showIssues.value = true
    return null
  }
  if (!isNew.value && !dirty.value && campaign.value) return campaign.value
  const body = campaignPayload(form)
  try {
    if (isNew.value) return await request<CampaignRead>('/admin/campaigns', { method: 'POST', body })
    // A scheduled campaign keeps its date: the send button changes it.
    const patch: CampaignUpdate = { ...body }
    if (campaign.value?.status === 'scheduled') delete patch.scheduled_at
    const updated = await request<CampaignRead>(`/admin/campaigns/${id.value}`, { method: 'PATCH', body: patch })
    campaign.value = updated
    return updated
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
    return null
  }
}

/** A new campaign moves to its own address once saved. */
async function openSaved(saved: CampaignRead) {
  if (isNew.value) await navigateTo(`/campaigns/${saved.id}`, { replace: true })
}

async function saveDraft() {
  busy.value = 'save'
  try {
    const saved = await persist()
    if (!saved) return
    toast.add({ title: t('campaigns.toast.saved'), color: 'success' })
    await openSaved(saved)
  }
  finally {
    busy.value = null
  }
}

async function sendTest() {
  busy.value = 'test'
  try {
    const saved = await persist()
    if (!saved) return
    try {
      const result = await request<CampaignTestResult>(`/admin/campaigns/${saved.id}/test`, { method: 'POST' })
      const ways = [result.pushed ? t('campaigns.channels.push') : t('campaigns.channels.inbox'), ...(result.emailed ? [t('campaigns.channels.email')] : [])]
      toast.add({ title: t('campaigns.toast.testSent'), description: t('campaigns.toast.testWays', { ways: listOf(ways, locale.value) }), color: 'success' })
    }
    catch (err) {
      toast.add({ title: apiError(err), color: 'error' })
    }
    await openSaved(saved)
  }
  finally {
    busy.value = null
  }
}

const confirmSendOpen = ref(false)
function askSend() {
  showIssues.value = true
  if (sendIssues.value.length) return
  confirmSendOpen.value = true
}
async function send() {
  busy.value = 'send'
  try {
    const saved = await persist()
    if (!saved) return
    try {
      const result = await request<CampaignRead | ApprovalHeld>(`/admin/campaigns/${saved.id}/schedule`, {
        method: 'POST',
        body: { scheduled_at: scheduledAtFrom(form) },
      })
      confirmSendOpen.value = false
      if (isHeld(result)) {
        await approvals.notifyHeld(result)
        if (!isNew.value) campaign.value = await request<CampaignRead>(`/admin/campaigns/${saved.id}`)
      }
      else {
        toast.add({ title: t(form.when === 'later' ? 'campaigns.toast.scheduled' : 'campaigns.toast.sending'), color: 'success' })
        if (!isNew.value) campaign.value = result
      }
    }
    catch (err) {
      toast.add({ title: apiError(err), color: 'error' })
    }
    await openSaved(saved)
  }
  finally {
    busy.value = null
  }
}

const confirmCancelOpen = ref(false)
async function cancelCampaign() {
  busy.value = 'cancel'
  try {
    campaign.value = await request<CampaignRead>(`/admin/campaigns/${id.value}/cancel`, { method: 'POST' })
    confirmCancelOpen.value = false
    toast.add({ title: t('campaigns.toast.cancelled'), color: 'success' })
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    busy.value = null
  }
}

async function duplicate() {
  busy.value = 'duplicate'
  try {
    const copy = await request<CampaignRead>(`/admin/campaigns/${id.value}/duplicate`, { method: 'POST' })
    toast.add({ title: t('campaigns.toast.duplicated'), color: 'success' })
    await navigateTo(`/campaigns/${copy.id}`)
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    busy.value = null
  }
}

const confirmDeleteOpen = ref(false)
async function remove() {
  busy.value = 'delete'
  try {
    await request(`/admin/campaigns/${id.value}`, { method: 'DELETE' })
    toast.add({ title: t('campaigns.toast.deleted'), color: 'success' })
    await navigateTo('/campaigns')
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    busy.value = null
  }
}

const sendLabel = computed(() => t(form.when === 'later' ? 'campaigns.actions.schedule' : 'campaigns.actions.sendNow'))
const sendWhen = computed(() => {
  const at = scheduledAtFrom(form)
  return at ? t('campaigns.confirmSend.at', { date: formatDate(at, locale.value) }) : t('campaigns.confirmSend.now')
})

const resultTiles = computed(() => {
  const s = campaign.value?.stats
  if (!s) return []
  return [
    { key: 'targeted', value: formatNumber(s.targeted, locale.value) },
    { key: 'sent', value: formatNumber(s.sent, locale.value) },
    { key: 'pushed', value: formatNumber(s.pushed, locale.value) },
    { key: 'delivered', value: formatNumber(s.delivered, locale.value), hint: formatPercent(rates.value.deliveryRate, locale.value) },
    { key: 'emailed', value: formatNumber(s.emailed, locale.value) },
    { key: 'opened', value: formatNumber(s.opened, locale.value) },
    { key: 'openRate', value: formatPercent(rates.value.openRate, locale.value) },
    { key: 'skipped', value: formatNumber(s.skipped, locale.value) },
  ]
})
</script>

<template>
  <UDashboardPanel id="campaign">
    <template #header>
      <UDashboardNavbar :title="isNew ? t('campaigns.new') : (campaign?.name ?? t('nav.campaigns'))">
        <template #leading>
          <UButton
            icon="i-lucide-arrow-left"
            color="neutral"
            variant="ghost"
            :aria-label="t('common.back')"
            to="/campaigns"
          />
          <UBadge
            v-if="campaign"
            :color="CAMPAIGN_STATUS_COLORS[campaign.status]"
            variant="subtle"
          >
            {{ t(`campaigns.statuses.${campaign.status}`) }}
          </UBadge>
        </template>
        <template #right>
          <UButton
            v-if="campaign && canDeleteCampaign(campaign.status)"
            icon="i-lucide-trash-2"
            color="error"
            variant="ghost"
            :label="t('campaigns.actions.delete')"
            @click="confirmDeleteOpen = true"
          />
          <UButton
            v-if="campaign && canCancelCampaign(campaign.status)"
            icon="i-lucide-circle-stop"
            color="warning"
            variant="ghost"
            :label="t('campaigns.actions.cancel')"
            @click="confirmCancelOpen = true"
          />
          <UButton
            v-if="campaign"
            icon="i-lucide-copy"
            color="neutral"
            variant="ghost"
            :label="t('campaigns.actions.duplicate')"
            :loading="busy === 'duplicate'"
            @click="duplicate"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <UAlert
        v-if="error"
        color="error"
        variant="subtle"
        icon="i-lucide-circle-alert"
        :title="apiError(error)"
      />
      <USkeleton
        v-else-if="status === 'pending' && !isNew"
        class="h-96"
      />

      <!-- Editing: new, draft, scheduled or waiting for approval -->
      <form
        v-else-if="editable"
        class="grid gap-6 lg:grid-cols-3"
        @submit.prevent="saveDraft"
      >
        <div class="grid content-start gap-6 lg:col-span-2">
          <UAlert
            v-if="campaign?.status === 'pending_approval'"
            color="warning"
            variant="subtle"
            icon="i-lucide-hourglass"
            :title="t('campaigns.pendingTitle')"
            :description="t('campaigns.pendingHelp')"
            :actions="[{ label: t('nav.approvals'), to: '/approvals', color: 'warning', variant: 'outline' }]"
          />
          <UAlert
            v-else-if="campaign?.status === 'scheduled'"
            color="info"
            variant="subtle"
            icon="i-lucide-calendar-clock"
            :title="t('campaigns.scheduledTitle', { date: formatDate(campaign.scheduled_at, locale) })"
            :description="t('campaigns.scheduledHelp')"
          />

          <UCard>
            <UFormField
              :label="t('campaigns.name')"
              :help="t('campaigns.nameHelp')"
              required
            >
              <UInput
                v-model="form.name"
                class="w-full"
                :maxlength="CAMPAIGN_NAME_MAX"
              />
            </UFormField>
          </UCard>

          <!-- Segment builder -->
          <UCard>
            <template #header>
              <h2 class="font-semibold">
                {{ t('campaigns.segment.title') }}
              </h2>
              <p class="text-sm text-(--ui-text-muted)">
                {{ t('campaigns.segment.help') }}
              </p>
            </template>
            <div class="space-y-5">
              <div class="grid gap-4 sm:grid-cols-2">
                <UFormField :label="t('campaigns.segment.audience')">
                  <URadioGroup
                    v-model="form.audience"
                    :items="audienceItems"
                    orientation="horizontal"
                  />
                </UFormField>
                <UFormField :label="t('campaigns.segment.locale')">
                  <USelect
                    v-model="form.locale"
                    :items="localeItems"
                    class="w-full"
                  />
                </UFormField>
              </div>
              <UFormField
                :label="t('campaigns.segment.cities')"
                :help="areaItems.length ? t('campaigns.segment.citiesHelp') : t('flags.rules.noAreas')"
              >
                <UCheckboxGroup
                  v-model="form.cities"
                  :items="areaItems"
                  orientation="horizontal"
                />
              </UFormField>

              <div class="space-y-3">
                <div class="flex flex-wrap items-center gap-3">
                  <UCheckbox
                    v-model="form.activeOn"
                    :label="t('campaigns.segment.active')"
                  />
                  <UInputNumber
                    v-if="form.activeOn"
                    v-model="form.active_days"
                    :min="SEGMENT_DAYS_MIN"
                    :max="SEGMENT_DAYS_MAX"
                    class="w-32"
                    :aria-label="t('campaigns.segment.days')"
                  />
                  <span
                    v-if="form.activeOn"
                    class="text-sm text-(--ui-text-muted)"
                  >{{ t('campaigns.segment.days') }}</span>
                </div>
                <div class="flex flex-wrap items-center gap-3">
                  <UCheckbox
                    v-model="form.inactiveOn"
                    :label="t('campaigns.segment.inactive')"
                  />
                  <UInputNumber
                    v-if="form.inactiveOn"
                    v-model="form.inactive_days"
                    :min="SEGMENT_DAYS_MIN"
                    :max="SEGMENT_DAYS_MAX"
                    class="w-32"
                    :aria-label="t('campaigns.segment.days')"
                  />
                  <span
                    v-if="form.inactiveOn"
                    class="text-sm text-(--ui-text-muted)"
                  >{{ t('campaigns.segment.days') }}</span>
                </div>
                <div class="flex flex-wrap items-center gap-3">
                  <UCheckbox
                    v-model="form.newOn"
                    :label="t('campaigns.segment.newWithoutRide')"
                  />
                  <UInputNumber
                    v-if="form.newOn"
                    v-model="form.new_without_ride_days"
                    :min="SEGMENT_DAYS_MIN"
                    :max="SEGMENT_DAYS_MAX"
                    class="w-32"
                    :aria-label="t('campaigns.segment.days')"
                  />
                  <span
                    v-if="form.newOn"
                    class="text-sm text-(--ui-text-muted)"
                  >{{ t('campaigns.segment.days') }}</span>
                </div>
                <div class="flex flex-wrap items-center gap-3">
                  <UCheckbox
                    v-model="form.versionOn"
                    :label="t('campaigns.segment.versionBelow')"
                  />
                  <UInput
                    v-if="form.versionOn"
                    v-model="form.app_version_below"
                    placeholder="1.4.0"
                    class="w-32 font-mono"
                    maxlength="16"
                    :aria-label="t('campaigns.segment.versionBelow')"
                  />
                </div>
                <UCheckbox
                  v-if="form.audience !== 'passengers'"
                  v-model="form.fee_pending"
                  :label="t('campaigns.segment.feePending')"
                  :description="t('campaigns.segment.feePendingHelp')"
                />
              </div>

              <p class="rounded-md bg-(--ui-bg-elevated) p-3 text-sm">
                <span class="text-(--ui-text-muted)">{{ t('campaigns.segment.summary') }}</span>
                {{ segmentSummary(segmentFromForm(form), t, locale) }}
              </p>
            </div>
          </UCard>

          <!-- Message -->
          <UCard>
            <template #header>
              <h2 class="font-semibold">
                {{ t('campaigns.message.title') }}
              </h2>
            </template>
            <div class="space-y-5">
              <UFormField
                :label="t('campaigns.message.channels')"
                required
              >
                <UCheckboxGroup
                  v-model="form.channels"
                  :items="channelItems"
                />
              </UFormField>
              <div class="grid gap-4 sm:grid-cols-2">
                <div class="space-y-3">
                  <p class="text-sm font-medium">
                    {{ t('campaigns.message.spanish') }}
                  </p>
                  <UFormField
                    :label="t('campaigns.message.titleField')"
                    required
                  >
                    <UInput
                      v-model="form.title_es"
                      class="w-full"
                      :maxlength="CAMPAIGN_TITLE_MAX"
                    />
                  </UFormField>
                  <UFormField :label="t('campaigns.message.body')">
                    <UTextarea
                      v-model="form.body_es"
                      class="w-full"
                      :rows="4"
                      autoresize
                      :maxlength="CAMPAIGN_BODY_MAX"
                    />
                  </UFormField>
                </div>
                <div class="space-y-3">
                  <p class="text-sm font-medium">
                    {{ t('campaigns.message.english') }}
                  </p>
                  <UFormField
                    :label="t('campaigns.message.titleField')"
                    :help="t('campaigns.message.englishHelp')"
                  >
                    <UInput
                      v-model="form.title_en"
                      class="w-full"
                      :maxlength="CAMPAIGN_TITLE_MAX"
                    />
                  </UFormField>
                  <UFormField :label="t('campaigns.message.body')">
                    <UTextarea
                      v-model="form.body_en"
                      class="w-full"
                      :rows="4"
                      autoresize
                      :maxlength="CAMPAIGN_BODY_MAX"
                    />
                  </UFormField>
                </div>
              </div>
              <UFormField
                :label="t('campaigns.message.deepLink')"
                :help="t('campaigns.message.deepLinkHelp')"
              >
                <UInput
                  v-model="form.deep_link"
                  class="w-full font-mono"
                  placeholder="/wallet"
                  :maxlength="DEEP_LINK_MAX"
                />
              </UFormField>
              <div class="flex flex-wrap gap-2">
                <UButton
                  v-for="link in SUGGESTED_LINKS"
                  :key="link.path"
                  size="xs"
                  :color="form.deep_link === link.path ? 'primary' : 'neutral'"
                  :variant="form.deep_link === link.path ? 'soft' : 'outline'"
                  :label="t(`campaigns.links.${link.key}`)"
                  @click="form.deep_link = link.path"
                />
              </div>
            </div>
          </UCard>

          <!-- When -->
          <UCard>
            <template #header>
              <h2 class="font-semibold">
                {{ t('campaigns.schedule.title') }}
              </h2>
            </template>
            <div class="space-y-3">
              <URadioGroup
                v-model="form.when"
                :items="whenItems"
                orientation="horizontal"
              />
              <div v-if="form.when === 'later'">
                <UInput
                  v-model="form.scheduled_at"
                  type="datetime-local"
                  class="w-64"
                  :aria-label="t('campaigns.schedule.later')"
                />
                <p class="mt-1 text-xs text-(--ui-text-muted)">
                  {{ t('campaigns.schedule.timeZone', { zone: timeZone }) }}
                </p>
              </div>
            </div>
          </UCard>

          <UAlert
            v-if="showIssues && sendIssues.length"
            color="error"
            variant="subtle"
            icon="i-lucide-circle-alert"
            :title="t('campaigns.fixErrors')"
          >
            <template #description>
              <ul class="list-disc pl-4">
                <li
                  v-for="issue in sendIssues"
                  :key="issue"
                >
                  {{ t(`campaigns.errors.${issue}`, { min: SEGMENT_DAYS_MIN, max: SEGMENT_DAYS_MAX }) }}
                </li>
              </ul>
            </template>
          </UAlert>

          <div class="sticky bottom-0 flex flex-wrap gap-2 bg-(--ui-bg) py-3">
            <UButton
              icon="i-lucide-send"
              :label="sendLabel"
              :loading="busy === 'send'"
              :disabled="!!busy"
              @click="askSend"
            />
            <UButton
              type="submit"
              color="neutral"
              variant="outline"
              icon="i-lucide-save"
              :label="campaign?.status === 'scheduled' ? t('common.save') : t('campaigns.actions.saveDraft')"
              :loading="busy === 'save'"
              :disabled="!!busy || !dirty"
            />
            <UButton
              color="neutral"
              variant="ghost"
              icon="i-lucide-flask-conical"
              :label="t('campaigns.actions.test')"
              :loading="busy === 'test'"
              :disabled="!!busy"
              @click="sendTest"
            />
          </div>
        </div>

        <div class="grid content-start gap-6">
          <UCard>
            <template #header>
              <div class="flex items-center justify-between gap-2">
                <h2 class="font-semibold">
                  {{ t('campaigns.reach.title') }}
                </h2>
                <UIcon
                  v-if="counting"
                  name="i-lucide-loader-circle"
                  class="size-4 animate-spin text-(--ui-text-muted)"
                />
              </div>
            </template>
            <p
              v-if="!segmentValid"
              class="text-sm text-(--ui-text-muted)"
            >
              {{ t('campaigns.reach.fixSegment') }}
            </p>
            <p
              v-else-if="countFailed && !audience"
              class="text-sm text-error"
            >
              {{ t('campaigns.reach.failed') }}
            </p>
            <template v-else>
              <p class="text-3xl font-semibold tabular-nums">
                {{ audience ? formatNumber(audience.total, locale) : '—' }}
              </p>
              <p class="text-sm text-(--ui-text-muted)">
                {{ t('campaigns.reach.people') }}
              </p>
              <dl class="mt-4 grid grid-cols-3 gap-2 text-sm">
                <div>
                  <dt class="text-(--ui-text-muted)">
                    {{ t('campaigns.reach.withPush') }}
                  </dt>
                  <dd class="font-medium tabular-nums">
                    {{ audience ? formatNumber(audience.with_push, locale) : '—' }}
                  </dd>
                </div>
                <div>
                  <dt class="text-(--ui-text-muted)">
                    {{ t('campaigns.reach.passengers') }}
                  </dt>
                  <dd class="font-medium tabular-nums">
                    {{ audience ? formatNumber(audience.passengers, locale) : '—' }}
                  </dd>
                </div>
                <div>
                  <dt class="text-(--ui-text-muted)">
                    {{ t('campaigns.reach.drivers') }}
                  </dt>
                  <dd class="font-medium tabular-nums">
                    {{ audience ? formatNumber(audience.drivers, locale) : '—' }}
                  </dd>
                </div>
              </dl>
              <p class="mt-3 text-xs text-(--ui-text-muted)">
                {{ t('campaigns.reach.help') }}
              </p>
            </template>
          </UCard>

          <UCard>
            <CampaignsPreview
              :title-es="form.title_es"
              :body-es="form.body_es"
              :title-en="form.title_en"
              :body-en="form.body_en"
              :deep-link="form.deep_link"
              :channels="form.channels"
            />
          </UCard>

          <UAlert
            color="neutral"
            variant="subtle"
            icon="i-lucide-info"
            :title="t('campaigns.rules.title')"
          >
            <template #description>
              <ul class="list-disc space-y-1 pl-4">
                <li>{{ t('campaigns.rules.cap') }}</li>
                <li>{{ t('campaigns.rules.quiet') }}</li>
                <li>{{ t('campaigns.rules.optOut') }}</li>
              </ul>
            </template>
          </UAlert>
        </div>
      </form>

      <!-- Results: sending, sent or cancelled -->
      <div
        v-else-if="campaign"
        class="grid gap-6 lg:grid-cols-3"
      >
        <div class="grid content-start gap-6 lg:col-span-2">
          <UCard>
            <template #header>
              <div class="flex flex-wrap items-center justify-between gap-2">
                <h2 class="font-semibold">
                  {{ t('campaigns.stats.title') }}
                </h2>
                <span
                  v-if="campaign.status === 'sending'"
                  class="flex items-center gap-1 text-xs text-(--ui-text-muted)"
                >
                  <UIcon
                    name="i-lucide-refresh-cw"
                    class="size-3 animate-spin"
                  />
                  {{ t('campaigns.stats.live') }}
                </span>
              </div>
            </template>
            <div class="space-y-5">
              <div v-if="campaign.status === 'sending'">
                <UProgress :model-value="Math.round((rates.progress ?? 0) * 100)" />
                <p class="mt-1 text-xs text-(--ui-text-muted)">
                  {{ t('campaigns.stats.progress', { done: formatNumber(campaign.stats.sent + campaign.stats.skipped, locale), total: formatNumber(campaign.stats.targeted, locale), pending: formatNumber(campaign.stats.pending, locale) }) }}
                </p>
              </div>
              <dl class="grid grid-cols-2 gap-4 sm:grid-cols-4">
                <div
                  v-for="tile in resultTiles"
                  :key="tile.key"
                >
                  <dt class="text-sm text-(--ui-text-muted)">
                    {{ t(`campaigns.stats.${tile.key}`) }}
                  </dt>
                  <dd class="text-2xl font-semibold tabular-nums">
                    {{ tile.value }}
                  </dd>
                  <dd
                    v-if="tile.hint"
                    class="text-xs text-(--ui-text-muted)"
                  >
                    {{ t('campaigns.stats.ofPushed', { rate: tile.hint }) }}
                  </dd>
                </div>
              </dl>
              <div>
                <p class="mb-2 text-sm font-medium">
                  {{ t('campaigns.stats.skippedWhy') }}
                </p>
                <dl class="grid gap-2 text-sm sm:grid-cols-3">
                  <div
                    v-for="reason in (['skipped_opt_out', 'skipped_cap', 'skipped_no_channel'] as const)"
                    :key="reason"
                    class="rounded-md bg-(--ui-bg-elevated) p-3"
                  >
                    <dt class="text-(--ui-text-muted)">
                      {{ t(`campaigns.stats.${reason}`) }}
                    </dt>
                    <dd class="text-lg font-semibold tabular-nums">
                      {{ formatNumber(campaign.stats[reason], locale) }}
                    </dd>
                  </div>
                </dl>
              </div>
              <p class="text-xs text-(--ui-text-muted)">
                {{ t('campaigns.stats.help') }}
              </p>
            </div>
          </UCard>

          <UCard>
            <template #header>
              <h2 class="font-semibold">
                {{ t('campaigns.details') }}
              </h2>
            </template>
            <dl class="grid gap-4 text-sm sm:grid-cols-2">
              <div class="sm:col-span-2">
                <dt class="text-(--ui-text-muted)">
                  {{ t('campaigns.audience') }}
                </dt>
                <dd>{{ segmentSummary(campaign.segment, t, locale) }}</dd>
              </div>
              <div>
                <dt class="text-(--ui-text-muted)">
                  {{ t('campaigns.message.channels') }}
                </dt>
                <dd>{{ listOf(campaign.channels.map(c => t(`campaigns.channels.${c}`)), locale) }}</dd>
              </div>
              <div>
                <dt class="text-(--ui-text-muted)">
                  {{ t('campaigns.message.deepLink') }}
                </dt>
                <dd class="font-mono">
                  {{ campaign.deep_link || '—' }}
                </dd>
              </div>
              <div>
                <dt class="text-(--ui-text-muted)">
                  {{ t('campaigns.when.scheduledFor') }}
                </dt>
                <dd>{{ formatDate(campaign.scheduled_at, locale) }}</dd>
              </div>
              <div>
                <dt class="text-(--ui-text-muted)">
                  {{ t('campaigns.when.startedAt') }}
                </dt>
                <dd>{{ formatDate(campaign.started_at, locale) }}</dd>
              </div>
              <div>
                <dt class="text-(--ui-text-muted)">
                  {{ t(campaign.status === 'cancelled' ? 'campaigns.when.cancelledAt' : 'campaigns.when.sentAt') }}
                </dt>
                <dd>{{ formatDate(campaign.finished_at, locale) }}</dd>
              </div>
              <div>
                <dt class="text-(--ui-text-muted)">
                  {{ t('campaigns.createdBy') }}
                </dt>
                <dd>{{ campaign.created_by_name || '—' }}</dd>
              </div>
            </dl>
          </UCard>
        </div>

        <div class="grid content-start gap-6">
          <UCard>
            <CampaignsPreview
              :title-es="campaign.title_es"
              :body-es="campaign.body_es"
              :title-en="campaign.title_en"
              :body-en="campaign.body_en"
              :deep-link="campaign.deep_link"
              :channels="campaign.channels"
            />
          </UCard>
        </div>
      </div>

      <!-- Confirm send -->
      <UModal
        v-model:open="confirmSendOpen"
        :title="t('campaigns.confirmSend.title')"
      >
        <template #body>
          <div class="space-y-3 text-sm">
            <p>
              {{ audience ? t('campaigns.confirmSend.reach', { n: formatNumber(audience.total, locale), when: sendWhen }) : t('campaigns.confirmSend.noCount', { when: sendWhen }) }}
            </p>
            <p class="text-(--ui-text-muted)">
              {{ t('campaigns.confirmSend.rules') }}
            </p>
          </div>
        </template>
        <template #footer>
          <div class="flex w-full justify-end gap-2">
            <UButton
              color="neutral"
              variant="ghost"
              :label="t('common.cancel')"
              @click="confirmSendOpen = false"
            />
            <UButton
              icon="i-lucide-send"
              :label="sendLabel"
              :loading="busy === 'send'"
              @click="send"
            />
          </div>
        </template>
      </UModal>

      <!-- Confirm cancel -->
      <UModal
        v-model:open="confirmCancelOpen"
        :title="t('campaigns.confirmCancel.title')"
        :description="t('campaigns.confirmCancel.body')"
      >
        <template #footer>
          <div class="flex w-full justify-end gap-2">
            <UButton
              color="neutral"
              variant="ghost"
              :label="t('common.back')"
              @click="confirmCancelOpen = false"
            />
            <UButton
              color="warning"
              icon="i-lucide-circle-stop"
              :label="t('campaigns.actions.cancel')"
              :loading="busy === 'cancel'"
              @click="cancelCampaign"
            />
          </div>
        </template>
      </UModal>

      <!-- Confirm delete -->
      <UModal
        v-model:open="confirmDeleteOpen"
        :title="t('campaigns.confirmDelete.title')"
        :description="t('campaigns.confirmDelete.body', { name: campaign?.name ?? '' })"
      >
        <template #footer>
          <div class="flex w-full justify-end gap-2">
            <UButton
              color="neutral"
              variant="ghost"
              :label="t('common.cancel')"
              @click="confirmDeleteOpen = false"
            />
            <UButton
              color="error"
              icon="i-lucide-trash-2"
              :label="t('campaigns.actions.delete')"
              :loading="busy === 'delete'"
              @click="remove"
            />
          </div>
        </template>
      </UModal>
    </template>
  </UDashboardPanel>
</template>
