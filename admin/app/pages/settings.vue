<script setup lang="ts">
import type { AppConfig, DocumentKind, VehicleType } from '~/types/api'
import { DOCUMENT_KINDS, VEHICLE_TYPES } from '~/types/api'

const { t } = useI18n()
const { request } = useApi()
const auth = useAuth()
const toast = useToast()
const apiError = useApiError()

const { data: config, status, error } = await useAsyncData('app-config', () => request<AppConfig>('/admin/config'))

const form = reactive<AppConfig>({
  driver_min_age: 21,
  vehicle_min_year: { moto: 2013, car: 1993 },
  enabled_vehicle_types: ['moto'],
  driver_required_documents: [],
  vehicle_photo_min_count: 2,
})

function load(value: AppConfig) {
  Object.assign(form, {
    driver_min_age: value.driver_min_age,
    vehicle_min_year: { ...form.vehicle_min_year, ...value.vehicle_min_year },
    enabled_vehicle_types: [...value.enabled_vehicle_types],
    driver_required_documents: [...value.driver_required_documents],
    vehicle_photo_min_count: value.vehicle_photo_min_count,
  })
}
watch(config, (value) => {
  if (value) load(value)
}, { immediate: true })

const readOnly = computed(() => !auth.isAdmin.value)
const currentYear = new Date().getFullYear()

const vehicleTypeItems = computed(() => VEHICLE_TYPES.map(v => ({ label: t(`vehicleTypes.${v}`), value: v })))
const documentItems = computed(() => DOCUMENT_KINDS.map(k => ({ label: t(`drivers.kinds.${k}`), value: k })))

const dirty = computed(() => !!config.value && JSON.stringify(normalize(form)) !== JSON.stringify(normalize(config.value)))
function normalize(value: AppConfig) {
  return {
    ...value,
    enabled_vehicle_types: [...value.enabled_vehicle_types].sort(),
    driver_required_documents: [...value.driver_required_documents].sort(),
  }
}

const saving = ref(false)
async function save() {
  if (!form.enabled_vehicle_types.length) {
    toast.add({ title: t('settings.needVehicleType'), color: 'error' })
    return
  }
  saving.value = true
  try {
    config.value = await request<AppConfig>('/admin/config', {
      method: 'PATCH',
      body: {
        ...form,
        // Keep the catalogue order so diffs/audit logs are stable.
        enabled_vehicle_types: VEHICLE_TYPES.filter(v => form.enabled_vehicle_types.includes(v)),
        driver_required_documents: DOCUMENT_KINDS.filter(k => form.driver_required_documents.includes(k)),
      },
    })
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

        <div
          v-if="!readOnly"
          class="flex gap-2"
        >
          <UButton
            type="submit"
            :loading="saving"
            :disabled="!dirty"
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
