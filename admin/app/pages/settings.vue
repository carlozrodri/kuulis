<script setup lang="ts">
import type { AppConfig, DocumentKind, VehicleType } from '~/types/api'
import { DOCUMENT_KINDS, PAYMENT_METHODS, VEHICLE_TYPES } from '~/types/api'
import type { MapRectangle } from '~/utils/geo'
import type { SettingsForm } from '~/utils/settings'

const { t, locale } = useI18n()
const { request } = useApi()
const auth = useAuth()
const toast = useToast()
const apiError = useApiError()

const { data: config, status, error } = await useAsyncData('app-config', () => request<AppConfig>('/admin/config'))

const form = reactive<SettingsForm>(defaultSettings())

function load(value: AppConfig) {
  Object.assign(form, settingsFromConfig(value))
}
watch(config, (value) => {
  if (value) load(value)
}, { immediate: true })

const readOnly = computed(() => !auth.isAdmin.value)
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
    config.value = await request<AppConfig>('/admin/config', { method: 'PATCH', body: changes.value })
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

const areaRectangles = computed<MapRectangle[]>(() => {
  const a = form.service_area
  if (![a.min_lat, a.max_lat, a.min_lng, a.max_lng].every(Number.isFinite)) return []
  return [{ id: 'area', bounds: [[a.min_lat, a.min_lng], [a.max_lat, a.max_lng]], color: MAP_COLORS.serviceArea }]
})

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
          <div class="space-y-4">
            <div class="grid gap-4 sm:grid-cols-2">
              <UFormField :label="t('settings.area.minLat')">
                <UInputNumber
                  v-model="form.service_area.min_lat"
                  :min="-90"
                  :max="90"
                  :step="0.01"
                  :format-options="coordFormat"
                  :disabled="readOnly"
                />
              </UFormField>
              <UFormField :label="t('settings.area.maxLat')">
                <UInputNumber
                  v-model="form.service_area.max_lat"
                  :min="-90"
                  :max="90"
                  :step="0.01"
                  :format-options="coordFormat"
                  :disabled="readOnly"
                />
              </UFormField>
              <UFormField :label="t('settings.area.minLng')">
                <UInputNumber
                  v-model="form.service_area.min_lng"
                  :min="-180"
                  :max="180"
                  :step="0.01"
                  :format-options="coordFormat"
                  :disabled="readOnly"
                />
              </UFormField>
              <UFormField :label="t('settings.area.maxLng')">
                <UInputNumber
                  v-model="form.service_area.max_lng"
                  :min="-180"
                  :max="180"
                  :step="0.01"
                  :format-options="coordFormat"
                  :disabled="readOnly"
                />
              </UFormField>
            </div>
            <div class="h-64">
              <MapView :rectangles="areaRectangles" />
            </div>
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
            :disabled="!dirty || issues.length > 0"
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
    </template>
  </UDashboardPanel>
</template>
