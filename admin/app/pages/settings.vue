<script setup lang="ts">
import type { AppConfig, ApprovalHeld, DocumentKind, VehicleType } from '~/types/api'
import { DOCUMENT_KINDS, PAYMENT_METHODS, RATE_SOURCES, VEHICLE_TYPES } from '~/types/api'
import type { MapRectangle } from '~/utils/geo'
import type { SettingsForm } from '~/utils/settings'

definePageMeta({ permission: 'config.view' })

const { t, locale } = useI18n()
const { request } = useApi()
const auth = useAuth()
const toast = useToast()
const apiError = useApiError()
const approvals = useApprovalCount()

const { data: config, status, error } = await useAsyncData('app-config', () => request<AppConfig>('/admin/config'))

const form = reactive<SettingsForm>(defaultSettings())

function load(value: AppConfig) {
  Object.assign(form, settingsFromConfig(value))
}
watch(config, (value) => {
  if (value) load(value)
}, { immediate: true })

const readOnly = computed(() => !auth.isAdmin.value)

// Which build is running: helps confirm a deploy replaced the old containers.
const runtime = useRuntimeConfig().public
const shortCommit = (commit?: string | null) => (commit ? commit.slice(0, 7) : '—')
const { data: apiVersion } = await useAsyncData('api-version', () =>
  $fetch<{ commit: string | null }>(`${runtime.apiBase.replace(/\/v1\/?$/, '')}/health/live`).catch(() => null),
)
const currentYear = new Date().getFullYear()

const vehicleTypeItems = computed(() => VEHICLE_TYPES.map(v => ({ label: t(`vehicleTypes.${v}`), value: v })))
const documentItems = computed(() => DOCUMENT_KINDS.map(k => ({ label: t(`drivers.kinds.${k}`), value: k })))
const paymentItems = computed(() => PAYMENT_METHODS.map(m => ({ label: t(`paymentMethods.${m}`), value: m })))
const roundingItems = computed(() => {
  const values = FARE_ROUNDINGS.includes(form.fare_rounding) ? FARE_ROUNDINGS : [...FARE_ROUNDINGS, form.fare_rounding]
  return values.map(value => ({ label: `$${value}`, value }))
})

// 0 = Monday … 6 = Sunday (contract). 2024-01-01 was a Monday.
const weekdayItems = computed(() =>
  Array.from({ length: 7 }, (_, day) => ({
    label: new Intl.DateTimeFormat(locale.value, { weekday: 'short', timeZone: 'UTC' }).format(new Date(Date.UTC(2024, 0, 1 + day))),
    value: day,
  })),
)

const payload = computed(() => settingsToPayload(form))
const original = computed(() => (config.value ? settingsToPayload(settingsFromConfig(config.value)) : null))
const changes = computed(() => (original.value ? changedSettings(payload.value, original.value) : {}))
const dirty = computed(() => Object.keys(changes.value).length > 0)
const issues = computed(() => validateSettings(form))

const saving = ref(false)
async function save() {
  if (issues.value.length) {
    toast.add({ title: t('settings.fixErrors'), color: 'error' })
    return
  }
  saving.value = true
  try {
    // Only the keys that changed: never overwrite settings this screen did not touch.
    const result = await request<AppConfig | ApprovalHeld>('/admin/config', { method: 'PATCH', body: changes.value })
    if (isHeld(result)) {
      // Nothing changed yet: show the saved values again until someone approves.
      reset()
      await approvals.notifyHeld(result)
      return
    }
    config.value = result
    toast.add({ title: t('common.saved'), color: 'success' })
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    saving.value = false
  }
}

function reset() {
  if (config.value) load(config.value)
}

const isRequired = (kind: DocumentKind) => form.driver_required_documents.includes(kind)

// ---- Ongoing driver verification (doc 12) ------------------------------------------------------

const paperDocumentItems = computed(() => PAPER_DOCUMENTS.map(k => ({ label: t(`drivers.kinds.${k}`), value: k })))
// Typed as "30, 7, 1"; the form keeps the parsed numbers (invalid text keeps the save disabled).
const noticeText = ref(form.verification.expiry_notice_days.join(', '))
watch(() => form.verification.expiry_notice_days, (days) => {
  if (JSON.stringify(parseNoticeDays(noticeText.value)) !== JSON.stringify(days)) noticeText.value = days.join(', ')
})
const noticeInvalid = computed(() => parseNoticeDays(noticeText.value) === null)
watch(noticeText, (text) => {
  const days = parseNoticeDays(text)
  if (days) form.verification.expiry_notice_days = days
})
const isEnabled = (type: VehicleType) => form.enabled_vehicle_types.includes(type)

// ---- Surge rules ----------------------------------------------------------------------------

function addSurgeRule() {
  form.surge_rules.push({ days: [0, 1, 2, 3, 4], start: '17:00', end: '20:00', multiplier: 1.2 })
}
function removeSurgeRule(index: number) {
  form.surge_rules.splice(index, 1)
}
function toggleDay(rule: SettingsForm['surge_rules'][number], day: number) {
  rule.days = rule.days.includes(day) ? rule.days.filter(d => d !== day) : [...rule.days, day].sort((a, b) => a - b)
}
const isOvernight = (start: string, end: string) => !!start && !!end && start > end

// ---- Search radii ---------------------------------------------------------------------------

function addRadius() {
  const last = form.search_radius_m.at(-1) ?? 0
  form.search_radius_m.push(last + 2000)
}
function removeRadius(index: number) {
  form.search_radius_m.splice(index, 1)
}

// ---- Service areas (one box per city) --------------------------------------------------------

function addArea() {
  // A small box around Caracas to start from; the admin moves it to the new city.
  form.service_areas.push({ name: '', min_lat: 10.45, max_lat: 10.52, min_lng: -66.95, max_lng: -66.8 })
}
function removeArea(index: number) {
  form.service_areas.splice(index, 1)
}
function areaRectangles(a: SettingsForm['service_areas'][number]): MapRectangle[] {
  if (![a.min_lat, a.max_lat, a.min_lng, a.max_lng].every(Number.isFinite)) return []
  return [{ id: 'area', bounds: [[a.min_lat, a.min_lng], [a.max_lat, a.max_lng]], color: MAP_COLORS.serviceArea }]
}

const moneyFormat = { minimumFractionDigits: 2, maximumFractionDigits: 2 }
const multiplierFormat = { minimumFractionDigits: 2, maximumFractionDigits: 2 }
const coordFormat = { minimumFractionDigits: 2, maximumFractionDigits: 6, useGrouping: false }
</script>

<template>
  <UDashboardPanel id="settings">
    <template #header>
      <UDashboardNavbar :title="t('nav.settings')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <UAlert
        v-if="error && !config"
        color="error"
        variant="subtle"
        icon="i-lucide-circle-alert"
        :title="apiError(error)"
      />
      <USkeleton
        v-else-if="status === 'pending' && !config"
        class="h-96 max-w-3xl"
      />

      <form
        v-if="config"
        class="grid max-w-3xl gap-6"
        @submit.prevent="save"
      >
        <UAlert
          v-if="readOnly"
          color="neutral"
          variant="subtle"
          icon="i-lucide-lock"
          :title="t('settings.readOnly')"
        />

        <UCard>
          <template #header>
            <h2 class="font-semibold">
              {{ t('settings.drivers') }}
            </h2>
          </template>
          <div class="grid gap-4 sm:grid-cols-2">
            <UFormField
              :label="t('settings.minAge')"
              :help="t('settings.minAgeHelp')"
            >
              <UInputNumber
                v-model="form.driver_min_age"
                :min="18"
                :max="99"
                :disabled="readOnly"
              />
            </UFormField>
            <UFormField
              :label="t('settings.minPhotos')"
              :help="t('settings.minPhotosHelp')"
            >
              <UInputNumber
                v-model="form.vehicle_photo_min_count"
                :min="0"
                :max="10"
                :disabled="readOnly"
              />
            </UFormField>
          </div>
        </UCard>

        <UCard>
          <template #header>
            <h2 class="font-semibold">
              {{ t('settings.vehicles') }}
            </h2>
          </template>
          <div class="space-y-6">
            <UFormField
              :label="t('settings.enabledTypes')"
              :help="t('settings.enabledTypesHelp')"
            >
              <UCheckboxGroup
                v-model="form.enabled_vehicle_types"
                :items="vehicleTypeItems"
                orientation="horizontal"
                :disabled="readOnly"
              />
            </UFormField>
            <div class="grid gap-4 sm:grid-cols-2">
              <UFormField
                v-for="type in VEHICLE_TYPES"
                :key="type"
                :label="t('settings.minYear', { type: t(`vehicleTypes.${type}`) })"
                :hint="isEnabled(type) ? undefined : t('settings.typeDisabled')"
              >
                <UInputNumber
                  v-model="form.vehicle_min_year[type]"
                  :min="1950"
                  :max="currentYear + 1"
                  :format-options="{ useGrouping: false }"
                  :disabled="readOnly"
                />
              </UFormField>
            </div>
          </div>
        </UCard>

        <UCard>
          <template #header>
            <h2 class="font-semibold">
              {{ t('settings.requiredDocuments') }}
            </h2>
            <p class="text-sm text-(--ui-text-muted)">
              {{ t('settings.requiredDocumentsHelp') }}
            </p>
          </template>
          <UCheckboxGroup
            v-model="form.driver_required_documents"
            :items="documentItems"
            :disabled="readOnly"
            :ui="{ fieldset: 'grid gap-3 sm:grid-cols-2' }"
          />
          <p
            v-if="!isRequired('selfie') || !isRequired('id_card')"
            class="mt-4 text-sm text-warning"
          >
            {{ t('settings.identityWarning') }}
          </p>
        </UCard>

        <!-- Phase 1B: fares -->
        <UCard>
          <template #header>
            <h2 class="font-semibold">
              {{ t('settings.fares.title') }}
            </h2>
            <p class="text-sm text-(--ui-text-muted)">
              {{ t('settings.fares.help') }}
            </p>
          </template>
          <div class="space-y-6">
            <div
              v-for="type in VEHICLE_TYPES"
              :key="type"
              class="space-y-3"
            >
              <div class="flex items-center gap-2">
                <h3 class="text-sm font-medium">
                  {{ t(`vehicleTypes.${type}`) }}
                </h3>
                <UBadge
                  v-if="!isEnabled(type)"
                  color="neutral"
                  variant="subtle"
                  size="sm"
                >
                  {{ t('settings.typeDisabled') }}
                </UBadge>
              </div>
              <div class="grid gap-4 sm:grid-cols-4">
                <UFormField
                  v-for="field in FARE_FIELDS"
                  :key="field"
                  :label="t(`settings.fares.${field}`)"
                >
                  <UInputNumber
                    v-model="form.fares[type][field]"
                    :min="0"
                    :max="1000"
                    :step="0.01"
                    :format-options="moneyFormat"
                    :disabled="readOnly"
                  />
                </UFormField>
              </div>
            </div>
            <div class="grid gap-4 border-t border-(--ui-border) pt-4 sm:grid-cols-2">
              <UFormField
                :label="t('settings.fares.rounding')"
                :help="t('settings.fares.roundingHelp')"
              >
                <USelect
                  v-model="form.fare_rounding"
                  :items="roundingItems"
                  class="w-40"
                  :disabled="readOnly"
                />
              </UFormField>
            </div>
          </div>
        </UCard>

        <!-- Phase 1B: surge -->
        <UCard>
          <template #header>
            <h2 class="font-semibold">
              {{ t('settings.surge.title') }}
            </h2>
            <p class="text-sm text-(--ui-text-muted)">
              {{ t('settings.surge.help') }}
            </p>
          </template>
          <div class="space-y-6">
            <UFormField
              :label="t('settings.surge.manual')"
              :help="t('settings.surge.manualHelp')"
            >
              <UInputNumber
                v-model="form.surge_manual_multiplier"
                :min="SURGE_MIN"
                :max="SURGE_MAX"
                :step="0.05"
                :format-options="multiplierFormat"
                :disabled="readOnly"
              />
            </UFormField>

            <div class="space-y-3 border-t border-(--ui-border) pt-4">
              <h3 class="text-sm font-medium">
                {{ t('settings.surge.rules') }}
              </h3>
              <p
                v-if="!form.surge_rules.length"
                class="text-sm text-(--ui-text-muted)"
              >
                {{ t('settings.surge.noRules') }}
              </p>
              <div
                v-for="(rule, index) in form.surge_rules"
                :key="index"
                class="space-y-3 rounded-md border border-(--ui-border) p-3"
              >
                <div class="flex items-start justify-between gap-2">
                  <div
                    role="group"
                    :aria-label="t('settings.surge.days')"
                    class="flex flex-wrap gap-1"
                  >
                    <UButton
                      v-for="day in weekdayItems"
                      :key="day.value"
                      size="xs"
                      :color="rule.days.includes(day.value) ? 'primary' : 'neutral'"
                      :variant="rule.days.includes(day.value) ? 'solid' : 'outline'"
                      :aria-pressed="rule.days.includes(day.value)"
                      :label="day.label"
                      :disabled="readOnly"
                      class="min-w-12 justify-center capitalize"
                      @click="toggleDay(rule, day.value)"
                    />
                  </div>
                  <UButton
                    v-if="!readOnly"
                    icon="i-lucide-trash-2"
                    color="error"
                    variant="ghost"
                    size="sm"
                    :aria-label="t('settings.surge.remove')"
                    @click="removeSurgeRule(index)"
                  />
                </div>
                <div class="grid gap-4 sm:grid-cols-3">
                  <UFormField :label="t('settings.surge.start')">
                    <UInput
                      v-model="rule.start"
                      type="time"
                      :disabled="readOnly"
                    />
                  </UFormField>
                  <UFormField
                    :label="t('settings.surge.end')"
                    :hint="isOvernight(rule.start, rule.end) ? t('settings.surge.overnight') : undefined"
                  >
                    <UInput
                      v-model="rule.end"
                      type="time"
                      :disabled="readOnly"
                    />
                  </UFormField>
                  <UFormField :label="t('settings.surge.multiplier')">
                    <UInputNumber
                      v-model="rule.multiplier"
                      :min="SURGE_MIN"
                      :max="SURGE_MAX"
                      :step="0.05"
                      :format-options="multiplierFormat"
                      :disabled="readOnly"
                    />
                  </UFormField>
                </div>
              </div>
              <UButton
                v-if="!readOnly"
                icon="i-lucide-plus"
                color="neutral"
                variant="outline"
                size="sm"
                :label="t('settings.surge.add')"
                @click="addSurgeRule"
              />
            </div>
          </div>
        </UCard>

        <!-- Phase 1B: payments -->
        <UCard>
          <template #header>
            <h2 class="font-semibold">
              {{ t('settings.payments.title') }}
            </h2>
            <p class="text-sm text-(--ui-text-muted)">
              {{ t('settings.payments.help') }}
            </p>
          </template>
          <UCheckboxGroup
            v-model="form.payment_methods"
            :items="paymentItems"
            :disabled="readOnly"
            :ui="{ fieldset: 'grid gap-3 sm:grid-cols-2' }"
          />
        </UCard>

        <!-- Phase 1B: service area -->
        <UCard>
          <template #header>
            <h2 class="font-semibold">
              {{ t('settings.area.title') }}
            </h2>
            <p class="text-sm text-(--ui-text-muted)">
              {{ t('settings.area.help') }}
            </p>
          </template>
          <div class="space-y-6">
            <div
              v-for="(area, index) in form.service_areas"
              :key="index"
              class="space-y-4 border-b border-(--ui-border) pb-6 last:border-b-0 last:pb-0"
            >
              <div class="flex items-end gap-2">
                <UFormField
                  :label="t('settings.area.name')"
                  class="flex-1"
                >
                  <UInput
                    v-model="area.name"
                    :maxlength="60"
                    :placeholder="t('settings.area.namePlaceholder')"
                    :disabled="readOnly"
                    class="w-full"
                  />
                </UFormField>
                <UButton
                  v-if="!readOnly && form.service_areas.length > 1"
                  icon="i-lucide-trash-2"
                  color="neutral"
                  variant="ghost"
                  :aria-label="t('settings.area.remove')"
                  @click="removeArea(index)"
                />
              </div>
              <div class="grid gap-4 sm:grid-cols-2">
                <UFormField :label="t('settings.area.minLat')">
                  <UInputNumber
                    v-model="area.min_lat"
                    :min="-90"
                    :max="90"
                    :step="0.01"
                    :format-options="coordFormat"
                    :disabled="readOnly"
                  />
                </UFormField>
                <UFormField :label="t('settings.area.maxLat')">
                  <UInputNumber
                    v-model="area.max_lat"
                    :min="-90"
                    :max="90"
                    :step="0.01"
                    :format-options="coordFormat"
                    :disabled="readOnly"
                  />
                </UFormField>
                <UFormField :label="t('settings.area.minLng')">
                  <UInputNumber
                    v-model="area.min_lng"
                    :min="-180"
                    :max="180"
                    :step="0.01"
                    :format-options="coordFormat"
                    :disabled="readOnly"
                  />
                </UFormField>
                <UFormField :label="t('settings.area.maxLng')">
                  <UInputNumber
                    v-model="area.max_lng"
                    :min="-180"
                    :max="180"
                    :step="0.01"
                    :format-options="coordFormat"
                    :disabled="readOnly"
                  />
                </UFormField>
              </div>
              <div class="h-56">
                <MapView :rectangles="areaRectangles(area)" />
              </div>
            </div>
            <UButton
              v-if="!readOnly && form.service_areas.length < 20"
              icon="i-lucide-plus"
              color="neutral"
              variant="outline"
              size="sm"
              :label="t('settings.area.add')"
              @click="addArea"
            />
          </div>
        </UCard>

        <!-- Phase 1B: dispatch -->
        <UCard>
          <template #header>
            <h2 class="font-semibold">
              {{ t('settings.dispatch.title') }}
            </h2>
          </template>
          <div class="space-y-6">
            <div class="grid gap-4 sm:grid-cols-3">
              <UFormField
                :label="t('settings.dispatch.offerTimeout')"
                :help="t('settings.dispatch.offerTimeoutHelp')"
              >
                <UInputNumber
                  v-model="form.offer_timeout_seconds"
                  :min="5"
                  :max="120"
                  :disabled="readOnly"
                />
              </UFormField>
              <UFormField
                :label="t('settings.dispatch.searchTimeout')"
                :help="t('settings.dispatch.searchTimeoutHelp')"
              >
                <UInputNumber
                  v-model="form.search_timeout_seconds"
                  :min="30"
                  :max="1800"
                  :disabled="readOnly"
                />
              </UFormField>
              <UFormField
                :label="t('settings.dispatch.quoteTtl')"
                :help="t('settings.dispatch.quoteTtlHelp')"
              >
                <UInputNumber
                  v-model="form.quote_ttl_seconds"
                  :min="30"
                  :max="3600"
                  :disabled="readOnly"
                />
              </UFormField>
            </div>
            <UFormField
              :label="t('settings.dispatch.radii')"
              :help="t('settings.dispatch.radiiHelp')"
            >
              <div class="flex flex-wrap items-center gap-2">
                <div
                  v-for="(_, index) in form.search_radius_m"
                  :key="index"
                  class="flex items-center gap-1"
                >
                  <UInputNumber
                    v-model="form.search_radius_m[index]"
                    :min="100"
                    :max="50000"
                    :step="500"
                    :format-options="{ useGrouping: false }"
                    class="w-32"
                    :disabled="readOnly"
                  />
                  <UButton
                    v-if="!readOnly && form.search_radius_m.length > 1"
                    icon="i-lucide-x"
                    color="neutral"
                    variant="ghost"
                    size="xs"
                    :aria-label="t('settings.dispatch.removeRadius')"
                    @click="removeRadius(index)"
                  />
                </div>
                <UButton
                  v-if="!readOnly && form.search_radius_m.length < 6"
                  icon="i-lucide-plus"
                  color="neutral"
                  variant="outline"
                  size="sm"
                  :label="t('settings.dispatch.addRadius')"
                  @click="addRadius"
                />
              </div>
            </UFormField>
          </div>
        </UCard>

        <!-- Phase 1C: exchange rates & promotions -->
        <UCard>
          <template #header>
            <h2 class="font-semibold">
              {{ t('settings.rates.title') }}
            </h2>
            <p class="text-sm text-(--ui-text-muted)">
              {{ t('settings.rates.help') }}
            </p>
          </template>
          <div class="space-y-6">
            <div class="grid gap-4 sm:grid-cols-3">
              <UFormField
                v-for="source in RATE_SOURCES"
                :key="source"
                :label="t('settings.rates.staleMinutes', { source: t(`rates.sources.${source}`) })"
                :hint="formatMinutes(form.rates_stale_minutes[source])"
              >
                <UInputNumber
                  v-model="form.rates_stale_minutes[source]"
                  :min="RATE_STALE_MIN"
                  :max="RATE_STALE_MAX"
                  :step="15"
                  :format-options="{ useGrouping: false }"
                  :disabled="readOnly"
                />
              </UFormField>
              <UFormField
                :label="t('settings.rates.manualHold')"
                :help="t('settings.rates.manualHoldHelp')"
              >
                <UInputNumber
                  v-model="form.rates_manual_hold_hours"
                  :min="MANUAL_HOLD_MIN"
                  :max="MANUAL_HOLD_MAX"
                  :disabled="readOnly"
                />
              </UFormField>
            </div>
            <p class="text-sm text-(--ui-text-muted)">
              {{ t('settings.rates.staleHelp') }}
            </p>
            <div class="grid gap-4 border-t border-(--ui-border) pt-4 sm:grid-cols-2">
              <UFormField
                :label="t('settings.rates.pairThreshold')"
                :help="t('settings.rates.pairThresholdHelp')"
              >
                <UInputNumber
                  v-model="form.promo_pair_alert_threshold"
                  :min="PAIR_THRESHOLD_MIN"
                  :max="PAIR_THRESHOLD_MAX"
                  :disabled="readOnly"
                />
              </UFormField>
              <UFormField
                :label="t('settings.rates.pairDays')"
                :help="t('settings.rates.pairDaysHelp')"
              >
                <UInputNumber
                  v-model="form.promo_pair_alert_days"
                  :min="PAIR_DAYS_MIN"
                  :max="PAIR_DAYS_MAX"
                  :disabled="readOnly"
                />
              </UFormField>
            </div>
          </div>
        </UCard>

        <!-- Phase 1D: wallet & subscription -->
        <UCard>
          <template #header>
            <h2 class="font-semibold">
              {{ t('settings.wallet.title') }}
            </h2>
            <p class="text-sm text-(--ui-text-muted)">
              {{ t('settings.wallet.help') }}
            </p>
          </template>
          <div class="space-y-6">
            <div class="space-y-4">
              <h3 class="text-sm font-medium">
                {{ t('settings.wallet.topUps') }}
              </h3>
              <UAlert
                v-if="!form.topup_binance_pay_id.trim()"
                color="warning"
                variant="subtle"
                icon="i-lucide-triangle-alert"
                :title="t('settings.wallet.payIdMissing')"
              />
              <div class="grid gap-4 sm:grid-cols-2">
                <UFormField
                  :label="t('settings.wallet.payId')"
                  :help="t('settings.wallet.payIdHelp')"
                >
                  <UInput
                    v-model="form.topup_binance_pay_id"
                    inputmode="numeric"
                    maxlength="20"
                    class="w-full font-mono"
                    :disabled="readOnly"
                  />
                </UFormField>
                <UFormField
                  :label="t('settings.wallet.accountName')"
                  :help="t('settings.wallet.accountNameHelp')"
                >
                  <UInput
                    v-model="form.topup_account_name"
                    :maxlength="ACCOUNT_NAME_MAX"
                    class="w-full"
                    :disabled="readOnly"
                  />
                </UFormField>
                <UFormField
                  :label="t('settings.wallet.minAmount')"
                  :help="t('settings.wallet.minAmountHelp')"
                >
                  <UInputNumber
                    v-model="form.topup_min_amount"
                    :min="TOPUP_MIN_MIN"
                    :max="TOPUP_MIN_MAX"
                    :step="1"
                    :format-options="moneyFormat"
                    :disabled="readOnly"
                  />
                </UFormField>
              </div>
            </div>
            <div class="grid gap-4 border-t border-(--ui-border) pt-4 sm:grid-cols-2">
              <UFormField
                :label="t('settings.wallet.transferLimit')"
                :help="t('settings.wallet.transferLimitHelp')"
              >
                <UInputNumber
                  v-model="form.transfer_monthly_limit"
                  :min="0"
                  :max="TRANSFER_LIMIT_MAX"
                  :step="5"
                  :format-options="moneyFormat"
                  :disabled="readOnly"
                />
              </UFormField>
            </div>
            <div class="space-y-4 border-t border-(--ui-border) pt-4">
              <h3 class="text-sm font-medium">
                {{ t('settings.wallet.subscription') }}
              </h3>
              <div class="grid gap-4 sm:grid-cols-2">
                <UFormField
                  :label="t('settings.wallet.freeMonths')"
                  :help="t('settings.wallet.freeMonthsHelp')"
                >
                  <UInputNumber
                    v-model="form.subscription_free_months"
                    :min="0"
                    :max="FREE_MONTHS_MAX"
                    :disabled="readOnly"
                  />
                </UFormField>
                <UFormField
                  :label="t('settings.wallet.graceDays')"
                  :help="t('settings.wallet.graceDaysHelp')"
                >
                  <UInputNumber
                    v-model="form.subscription_grace_days"
                    :min="0"
                    :max="GRACE_DAYS_MAX"
                    :disabled="readOnly"
                  />
                </UFormField>
              </div>
              <p class="text-sm text-(--ui-text-muted)">
                {{ t('settings.wallet.tiersHint') }}
                <NuxtLink
                  to="/subscriptions?tab=schedules"
                  class="text-primary hover:underline"
                >{{ t('nav.subscriptions') }}</NuxtLink>
              </p>
            </div>
          </div>
        </UCard>

        <!-- Doc 10: links and location intervals the app reads at start (no app update needed) -->
        <UCard>
          <template #header>
            <h2 class="font-semibold">
              {{ t('settings.app.title') }}
            </h2>
            <p class="text-sm text-(--ui-text-muted)">
              {{ t('settings.app.help') }}
              <NuxtLink
                v-if="auth.can('app_status.view')"
                to="/app-status"
                class="text-primary hover:underline"
              >{{ t('settings.app.statusLink') }}</NuxtLink>
            </p>
          </template>
          <div class="space-y-6">
            <div class="grid gap-4 sm:grid-cols-2">
              <UFormField
                :label="t('settings.app.whatsapp')"
                :help="t('settings.app.whatsappHelp')"
              >
                <UInput
                  v-model="form.app_links.support_whatsapp"
                  inputmode="tel"
                  maxlength="20"
                  placeholder="+584121234567"
                  class="w-full font-mono"
                  :disabled="readOnly"
                />
              </UFormField>
              <UFormField :label="t('settings.app.supportEmail')">
                <UInput
                  v-model="form.app_links.support_email"
                  type="email"
                  :maxlength="SUPPORT_EMAIL_MAX"
                  class="w-full"
                  :disabled="readOnly"
                />
              </UFormField>
              <UFormField
                :label="t('settings.app.emergencyNumber')"
                :help="t('settings.app.emergencyNumberHelp')"
              >
                <UInput
                  v-model="form.app_links.emergency_number"
                  inputmode="numeric"
                  maxlength="10"
                  class="w-full font-mono"
                  :disabled="readOnly"
                />
              </UFormField>
            </div>
            <div class="grid gap-4">
              <UFormField :label="t('settings.app.termsUrl')">
                <UInput
                  v-model="form.app_links.terms_url"
                  type="url"
                  :maxlength="LINK_MAX"
                  placeholder="https://"
                  class="w-full"
                  :disabled="readOnly"
                />
              </UFormField>
              <UFormField :label="t('settings.app.privacyUrl')">
                <UInput
                  v-model="form.app_links.privacy_url"
                  type="url"
                  :maxlength="LINK_MAX"
                  placeholder="https://"
                  class="w-full"
                  :disabled="readOnly"
                />
              </UFormField>
            </div>
            <div>
              <h3 class="text-sm font-medium">
                {{ t('settings.app.intervals') }}
              </h3>
              <p class="mb-3 text-sm text-(--ui-text-muted)">
                {{ t('settings.app.intervalsHelp') }}
              </p>
              <div class="grid gap-4 sm:grid-cols-2">
                <UFormField
                  :label="t('settings.app.onlineSeconds')"
                  :help="t('settings.app.secondsRange', { min: ONLINE_SECONDS_MIN, max: ONLINE_SECONDS_MAX })"
                >
                  <UInputNumber
                    v-model="form.location_intervals.online_seconds"
                    :min="ONLINE_SECONDS_MIN"
                    :max="ONLINE_SECONDS_MAX"
                    :disabled="readOnly"
                  />
                </UFormField>
                <UFormField
                  :label="t('settings.app.onRideSeconds')"
                  :help="t('settings.app.secondsRange', { min: ON_RIDE_SECONDS_MIN, max: ON_RIDE_SECONDS_MAX })"
                >
                  <UInputNumber
                    v-model="form.location_intervals.on_ride_seconds"
                    :min="ON_RIDE_SECONDS_MIN"
                    :max="ON_RIDE_SECONDS_MAX"
                    :disabled="readOnly"
                  />
                </UFormField>
              </div>
            </div>
          </div>
        </UCard>

        <!-- Doc 06: four-eyes approvals -->
        <UCard>
          <template #header>
            <h2 class="font-semibold">
              {{ t('settings.approvals.title') }}
            </h2>
            <p class="text-sm text-(--ui-text-muted)">
              {{ t('settings.approvals.help') }}
            </p>
          </template>
          <div class="space-y-4">
            <UFormField
              :label="t('settings.approvals.adjustLimit')"
              :help="t('settings.approvals.adjustLimitHelp')"
            >
              <UInputNumber
                v-model="form.approval_adjust_limit"
                :min="0"
                :max="APPROVAL_LIMIT_MAX"
                :step="5"
                :format-options="moneyFormat"
                :disabled="readOnly"
              />
            </UFormField>
            <USwitch
              v-model="form.approval_fares"
              :label="t('settings.approvals.fares')"
              :description="t('settings.approvals.faresHelp')"
              :disabled="readOnly"
            />
            <USwitch
              v-model="form.approval_broadcasts"
              :label="t('settings.approvals.broadcasts')"
              :description="t('settings.approvals.broadcastsHelp')"
              :disabled="readOnly"
            />
          </div>
        </UCard>

        <!-- Doc 11: trip safety -->
        <UCard>
          <template #header>
            <h2 class="font-semibold">
              {{ t('settings.safety.title') }}
            </h2>
            <p class="text-sm text-(--ui-text-muted)">
              {{ t('settings.safety.help') }}
            </p>
          </template>
          <div class="space-y-6">
            <USwitch
              v-model="form.safety.sos_team_alert"
              :label="t('settings.safety.sosTeam')"
              :description="t('settings.safety.sosTeamHelp')"
              :disabled="readOnly"
            />
            <UFormField
              :label="t('settings.safety.pinAreas')"
              :help="t('settings.safety.pinAreasHelp')"
            >
              <UCheckboxGroup
                v-model="form.safety.pin_areas"
                :items="form.service_areas.filter(a => a.name.trim()).map(a => ({ label: a.name, value: a.name.trim() }))"
                orientation="horizontal"
                :disabled="readOnly"
              />
            </UFormField>
            <div class="grid gap-4 sm:grid-cols-3">
              <UFormField :label="t('settings.safety.passengerPhoto')">
                <USelect
                  v-model="form.safety.passenger_photo"
                  :items="(['off', 'night', 'always'] as const).map(value => ({ label: t(`settings.safety.photo.${value}`), value }))"
                  class="w-full"
                  :disabled="readOnly"
                />
              </UFormField>
              <UFormField :label="t('settings.safety.nightStart')">
                <UInput
                  v-model="form.safety.night_start"
                  type="time"
                  :disabled="readOnly"
                />
              </UFormField>
              <UFormField :label="t('settings.safety.nightEnd')">
                <UInput
                  v-model="form.safety.night_end"
                  type="time"
                  :disabled="readOnly"
                />
              </UFormField>
            </div>
            <div>
              <h3 class="text-sm font-medium">
                {{ t('settings.safety.anomalies') }}
              </h3>
              <p class="mb-3 text-sm text-(--ui-text-muted)">
                {{ t('settings.safety.anomaliesHelp') }}
              </p>
              <div class="grid gap-4 sm:grid-cols-3">
                <UFormField
                  v-for="key in SAFETY_NUMBERS"
                  :key="key"
                  :label="t(`settings.safety.numbers.${key}`)"
                  :help="t('settings.safety.range', { min: SAFETY_LIMITS[key][0], max: SAFETY_LIMITS[key][1] })"
                >
                  <UInputNumber
                    v-model="form.safety[key]"
                    :min="SAFETY_LIMITS[key][0]"
                    :max="SAFETY_LIMITS[key][1]"
                    :step="key === 'overtime_factor' ? 0.1 : 1"
                    :disabled="readOnly"
                  />
                </UFormField>
              </div>
            </div>
          </div>
        </UCard>

        <!-- Doc 12: ongoing driver verification -->
        <UCard>
          <template #header>
            <h2 class="font-semibold">
              {{ t('settings.verification.title') }}
            </h2>
            <p class="text-sm text-(--ui-text-muted)">
              {{ t('settings.verification.help') }}
            </p>
          </template>
          <div class="space-y-6">
            <UFormField
              :label="t('settings.verification.expiring')"
              :help="t('settings.verification.expiringHelp')"
            >
              <UCheckboxGroup
                v-model="form.verification.expiring_documents"
                :items="paperDocumentItems"
                :disabled="readOnly"
                :ui="{ fieldset: 'grid gap-3 sm:grid-cols-2' }"
              />
            </UFormField>
            <UFormField
              :label="t('settings.verification.optional')"
              :help="t('settings.verification.optionalHelp')"
            >
              <UCheckboxGroup
                v-model="form.verification.optional_documents"
                :items="paperDocumentItems"
                :disabled="readOnly"
                :ui="{ fieldset: 'grid gap-3 sm:grid-cols-2' }"
              />
            </UFormField>
            <div class="grid gap-4 sm:grid-cols-2">
              <UFormField
                :label="t('settings.verification.noticeDays')"
                :help="t('settings.verification.noticeDaysHelp', { max: NOTICE_DAYS_MAX })"
                :error="noticeInvalid ? t('settings.verification.noticeDaysInvalid') : undefined"
              >
                <UInput
                  v-model="noticeText"
                  placeholder="30, 7, 1"
                  :disabled="readOnly"
                />
              </UFormField>
              <UFormField
                v-for="key in VERIFICATION_NUMBERS"
                :key="key"
                :label="t(`settings.verification.numbers.${key}`)"
                :help="key === 'selfie_every_days' ? t('settings.verification.selfieHelp') : t('settings.safety.range', { min: VERIFICATION_LIMITS[key][0], max: VERIFICATION_LIMITS[key][1] })"
              >
                <UInputNumber
                  v-model="form.verification[key]"
                  :min="VERIFICATION_LIMITS[key][0]"
                  :max="VERIFICATION_LIMITS[key][1]"
                  :disabled="readOnly"
                />
              </UFormField>
            </div>
            <USwitch
              v-model="form.verification.induction_required"
              :label="t('settings.verification.induction')"
              :description="t('settings.verification.inductionHelp')"
              :disabled="readOnly"
            />
          </div>
        </UCard>

        <!-- Doc 13: support -->
        <UCard>
          <template #header>
            <h2 class="font-semibold">
              {{ t('settings.support.title') }}
            </h2>
            <p class="text-sm text-(--ui-text-muted)">
              {{ t('settings.support.help') }}
            </p>
          </template>
          <div class="space-y-6">
            <div class="grid gap-4 sm:grid-cols-3">
              <UFormField
                v-for="key in SUPPORT_NUMBERS"
                :key="key"
                :label="t(`settings.support.numbers.${key}`)"
                :help="t(`settings.support.numbersHelp.${key}`, { min: SUPPORT_LIMITS[key][0], max: SUPPORT_LIMITS[key][1] })"
              >
                <UInputNumber
                  v-model="form.support[key]"
                  :min="SUPPORT_LIMITS[key][0]"
                  :max="SUPPORT_LIMITS[key][1]"
                  :disabled="readOnly"
                />
              </UFormField>
            </div>
            <div class="grid gap-4 sm:grid-cols-2">
              <UFormField
                v-for="lang in (['es', 'en'] as const)"
                :key="lang"
                :label="t(`settings.support.promise.${lang}`)"
                :help="t('settings.support.promiseHelp', { max: PROMISE_MAX })"
              >
                <UInput
                  v-model="form.support[`response_promise_${lang}`]"
                  class="w-full"
                  :maxlength="PROMISE_MAX"
                  :disabled="readOnly"
                />
              </UFormField>
            </div>
            <USwitch
              v-model="form.support.auto_assign"
              :label="t('settings.support.autoAssign')"
              :description="t('settings.support.autoAssignHelp')"
              :disabled="readOnly"
            />
          </div>
        </UCard>

        <!-- Doc 14: notifications -->
        <UCard>
          <template #header>
            <h2 class="font-semibold">
              {{ t('settings.notifications.title') }}
            </h2>
            <p class="text-sm text-(--ui-text-muted)">
              {{ t('settings.notifications.help') }}
            </p>
          </template>
          <div class="space-y-6">
            <div>
              <div class="grid gap-4 sm:grid-cols-3">
                <UFormField :label="t('settings.notifications.quietStart')">
                  <UInput
                    v-model="form.notifications.quiet_start"
                    type="time"
                    :disabled="readOnly"
                  />
                </UFormField>
                <UFormField :label="t('settings.notifications.quietEnd')">
                  <UInput
                    v-model="form.notifications.quiet_end"
                    type="time"
                    :disabled="readOnly"
                  />
                </UFormField>
              </div>
              <p class="mt-1 text-xs text-(--ui-text-muted)">
                {{ form.notifications.quiet_start === form.notifications.quiet_end ? t('settings.notifications.quietOff') : t('settings.notifications.quietHelp') }}
              </p>
            </div>
            <div class="grid gap-4 sm:grid-cols-3">
              <UFormField
                v-for="key in NOTIFICATION_NUMBERS"
                :key="key"
                :label="t(`settings.notifications.numbers.${key}`)"
                :help="t(`settings.notifications.numbersHelp.${key}`, { min: NOTIFICATION_LIMITS[key][0], max: NOTIFICATION_LIMITS[key][1] })"
              >
                <UInputNumber
                  v-model="form.notifications[key]"
                  :min="NOTIFICATION_LIMITS[key][0]"
                  :max="NOTIFICATION_LIMITS[key][1]"
                  :disabled="readOnly"
                />
              </UFormField>
            </div>
            <USwitch
              v-model="form.notifications.monthly_summary"
              :label="t('settings.notifications.monthlySummary')"
              :description="t('settings.notifications.monthlySummaryHelp')"
              :disabled="readOnly"
            />
          </div>
        </UCard>

        <!-- Doc 15: cancellations and service quality -->
        <UCard>
          <template #header>
            <h2 class="font-semibold">
              {{ t('settings.quality.title') }}
            </h2>
            <p class="text-sm text-(--ui-text-muted)">
              {{ t('settings.quality.help') }}
            </p>
          </template>
          <div class="space-y-6">
            <div
              v-for="section in QUALITY_SECTIONS"
              :key="section.key"
            >
              <h3 class="mb-2 text-sm font-medium">
                {{ t(`settings.quality.sections.${section.key}`) }}
              </h3>
              <div class="grid gap-4 sm:grid-cols-3">
                <UFormField
                  v-for="key in section.fields"
                  :key="key"
                  :label="t(`settings.quality.numbers.${key}`)"
                  :help="t(`settings.quality.numbersHelp.${key}`, { min: QUALITY_LIMITS[key][0], max: QUALITY_LIMITS[key][1] })"
                >
                  <UInputNumber
                    v-model="form.quality[key]"
                    :min="QUALITY_LIMITS[key][0]"
                    :max="QUALITY_LIMITS[key][1]"
                    :step="key === 'rating_review_below' ? 0.1 : 1"
                    :format-options="QUALITY_PERCENT_FIELDS.includes(key) || key === 'rating_review_below' ? { maximumFractionDigits: 1 } : undefined"
                    :disabled="readOnly"
                  />
                </UFormField>
              </div>
            </div>
          </div>
        </UCard>

        <!-- Doc 16: anti-fraud -->
        <UCard>
          <template #header>
            <h2 class="font-semibold">
              {{ t('settings.risk.title') }}
            </h2>
            <p class="text-sm text-(--ui-text-muted)">
              {{ t('settings.risk.help') }}
            </p>
          </template>
          <div class="space-y-6">
            <div
              v-for="section in RISK_SECTIONS"
              :key="section.key"
            >
              <h3 class="mb-2 text-sm font-medium">
                {{ t(`settings.risk.sections.${section.key}`) }}
              </h3>
              <div class="grid gap-4 sm:grid-cols-3">
                <UFormField
                  v-for="key in section.fields"
                  :key="key"
                  :label="t(`settings.risk.numbers.${key}`)"
                  :help="t(`settings.risk.numbersHelp.${key}`, { min: RISK_LIMITS[key][0], max: RISK_LIMITS[key][1] })"
                >
                  <UInputNumber
                    v-model="form.risk[key]"
                    :min="RISK_LIMITS[key][0]"
                    :max="RISK_LIMITS[key][1]"
                    :format-options="RISK_PERCENT_FIELDS.includes(key) ? { maximumFractionDigits: 1 } : undefined"
                    :disabled="readOnly"
                  />
                </UFormField>
              </div>
            </div>
          </div>
        </UCard>

        <UAlert
          v-if="!readOnly && dirty && issues.length"
          color="error"
          variant="subtle"
          icon="i-lucide-circle-alert"
          :title="t('settings.fixErrors')"
        >
          <template #description>
            <ul class="list-disc pl-4">
              <li
                v-for="issue in issues"
                :key="issue.key + JSON.stringify(issue.params ?? {})"
              >
                {{ t(`settings.errors.${issue.key}`, { ...issue.params, type: issue.params?.type ? t(`vehicleTypes.${issue.params.type}`) : '' }) }}
              </li>
            </ul>
          </template>
        </UAlert>

        <div
          v-if="!readOnly"
          class="sticky bottom-0 flex gap-2 bg-(--ui-bg) py-3"
        >
          <UButton
            type="submit"
            :loading="saving"
            :disabled="!dirty || issues.length > 0 || noticeInvalid"
            :label="t('common.save')"
          />
          <UButton
            color="neutral"
            variant="ghost"
            :disabled="!dirty || saving"
            :label="t('common.discard')"
            @click="reset"
          />
        </div>
      </form>
      <p class="pt-4 text-xs text-(--ui-text-muted)">
        {{ t('settings.version', { api: shortCommit(apiVersion?.commit), admin: shortCommit(runtime.commit) }) }}
      </p>
    </template>
  </UDashboardPanel>
</template>
