<script setup lang="ts">
import type { AppConfig, DiscountType, Promotion } from '~/types/api'
import { VEHICLE_TYPES } from '~/types/api'
import type { PromotionForm } from '~/utils/promotions'

/** Create form when `promotion` is absent; edit form (PATCH of the changed keys only) otherwise. */
const props = defineProps<{ promotion?: Promotion | null }>()
const emit = defineEmits<{ saved: [promotion: Promotion] }>()

const { t, locale } = useI18n()
const { request } = useApi()
const toast = useToast()
const apiError = useApiError()

// Cities and vehicle types come from the app configuration.
const { data: config } = await useAsyncData('promotion-form-config', () => request<AppConfig>('/admin/config').catch(() => null))

const form = reactive<PromotionForm>(props.promotion ? promotionToForm(props.promotion) : defaultPromotionForm())
const isEdit = computed(() => !!props.promotion)

function load() {
  Object.assign(form, props.promotion ? promotionToForm(props.promotion) : defaultPromotionForm())
}
watch(() => props.promotion, load)

// Codes are uppercase letters and digits; normalise as the admin types.
watch(() => form.code, (value) => {
  const normalized = normalizeCode(value)
  if (normalized !== value) form.code = normalized
})

const committed = computed(() => committedBudget(props.promotion?.stats))
const payload = computed(() => promotionToPayload(form))
const original = computed(() => (props.promotion ? promotionToPayload(promotionToForm(props.promotion)) : null))
const changes = computed(() => (original.value ? changedPromotion(payload.value, original.value) : payload.value))
const dirty = computed(() => !isEdit.value || Object.keys(changes.value).length > 0)
const issues = computed(() => validatePromotion(form, committed.value))
const showIssues = ref(false)

const discountTypeItems = computed(() => (['percent', 'fixed'] as DiscountType[]).map(value => ({
  label: t(`promotions.discountTypes.${value}`),
  value,
})))

const areaItems = computed(() => {
  const configured = (config.value?.service_areas ?? []).map(a => a.name)
  // Keep areas the promotion already uses even if they were removed from the configuration.
  const extra = form.service_areas.filter(name => !configured.includes(name))
  return [
    ...configured.map(name => ({ label: name, value: name })),
    ...extra.map(name => ({ label: t('promotions.form.unknownArea', { name }), value: name })),
  ]
})

const vehicleItems = computed(() => {
  const enabled = config.value?.enabled_vehicle_types ?? VEHICLE_TYPES
  const values = VEHICLE_TYPES.filter(v => enabled.includes(v) || form.vehicle_types.includes(v))
  return values.map(value => ({
    label: enabled.includes(value) ? t(`vehicleTypes.${value}`) : `${t(`vehicleTypes.${value}`)} (${t('settings.typeDisabled')})`,
    value,
  }))
})

const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone

const saving = ref(false)
async function save() {
  showIssues.value = true
  if (issues.value.length) {
    toast.add({ title: t('promotions.form.fixErrors'), color: 'error' })
    return
  }
  saving.value = true
  try {
    const saved = isEdit.value
      ? await request<Promotion>(`/admin/promotions/${props.promotion!.id}`, { method: 'PATCH', body: changes.value })
      : await request<Promotion>('/admin/promotions', { method: 'POST', body: payload.value })
    toast.add({ title: isEdit.value ? t('common.saved') : t('promotions.form.created'), color: 'success' })
    emit('saved', saved)
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    saving.value = false
  }
}

const moneyFormat = { minimumFractionDigits: 2, maximumFractionDigits: 2 }
const percentFormat = { minimumFractionDigits: 0, maximumFractionDigits: 2 }
</script>

<template>
  <form
    class="grid max-w-3xl gap-6"
    novalidate
    @submit.prevent="save"
  >
    <UCard>
      <template #header>
        <h2 class="font-semibold">
          {{ t('promotions.form.general') }}
        </h2>
      </template>
      <div class="grid gap-4 sm:grid-cols-2">
        <UFormField
          :label="t('promotions.name')"
          required
          class="sm:col-span-2"
        >
          <UInput
            v-model="form.name"
            :maxlength="PROMO_NAME_MAX"
            :placeholder="t('promotions.form.namePlaceholder')"
            class="w-full"
          />
        </UFormField>
        <UFormField
          :label="t('promotions.description')"
          :help="t('promotions.form.descriptionHelp')"
          class="sm:col-span-2"
        >
          <UTextarea
            v-model="form.description"
            :rows="2"
            :maxlength="PROMO_DESCRIPTION_MAX"
            class="w-full"
          />
        </UFormField>
        <UFormField
          :label="t('promotions.code')"
          :help="form.code ? t('promotions.form.codeHelp') : t('promotions.form.automaticHelp')"
        >
          <UInput
            v-model="form.code"
            :maxlength="20"
            :placeholder="t('promotions.form.codePlaceholder')"
            class="w-full font-mono"
            autocomplete="off"
            spellcheck="false"
          />
        </UFormField>
        <UFormField
          :label="t('promotions.form.state')"
          :help="t('promotions.form.activeHelp')"
        >
          <USwitch
            v-model="form.is_active"
            :label="form.is_active ? t('promotions.form.enabled') : t('promotions.form.disabled')"
          />
        </UFormField>
      </div>
    </UCard>

    <UCard>
      <template #header>
        <h2 class="font-semibold">
          {{ t('promotions.form.discount') }}
        </h2>
        <p class="text-sm text-(--ui-text-muted)">
          {{ t('promotions.form.discountHelp') }}
        </p>
      </template>
      <div class="space-y-4">
        <URadioGroup
          v-model="form.discount_type"
          :items="discountTypeItems"
          orientation="horizontal"
        />
        <div class="grid gap-4 sm:grid-cols-3">
          <UFormField
            :label="form.discount_type === 'percent' ? t('promotions.form.percent') : t('promotions.form.fixed')"
            required
          >
            <UInputNumber
              v-if="form.discount_type === 'percent'"
              v-model="form.discount_value"
              :min="1"
              :max="100"
              :step="1"
              :format-options="percentFormat"
            />
            <UInputNumber
              v-else
              v-model="form.discount_value"
              :min="0.01"
              :step="0.05"
              :format-options="moneyFormat"
            />
          </UFormField>
          <UFormField
            v-if="form.discount_type === 'percent'"
            :label="t('promotions.maxDiscount')"
            :help="t('promotions.form.maxDiscountHelp')"
          >
            <UInputNumber
              v-model="form.max_discount"
              :min="0.01"
              :step="0.05"
              :format-options="moneyFormat"
              :placeholder="t('promotions.form.noLimit')"
            />
          </UFormField>
          <UFormField
            :label="t('promotions.minFare')"
            :help="t('promotions.form.minFareHelp')"
          >
            <UInputNumber
              v-model="form.min_fare"
              :min="0"
              :step="0.05"
              :format-options="moneyFormat"
            />
          </UFormField>
        </div>
      </div>
    </UCard>

    <UCard>
      <template #header>
        <h2 class="font-semibold">
          {{ t('promotions.form.validity') }}
        </h2>
        <p class="text-sm text-(--ui-text-muted)">
          {{ t('promotions.form.validityHelp', { zone: timeZone }) }}
        </p>
      </template>
      <div class="grid gap-4 sm:grid-cols-2">
        <UFormField
          :label="t('promotions.startsAt')"
          required
        >
          <UInput
            v-model="form.starts_at"
            type="datetime-local"
            class="w-full"
          />
        </UFormField>
        <UFormField
          :label="t('promotions.endsAt')"
          required
        >
          <UInput
            v-model="form.ends_at"
            type="datetime-local"
            :min="form.starts_at || undefined"
            class="w-full"
          />
        </UFormField>
      </div>
    </UCard>

    <UCard>
      <template #header>
        <h2 class="font-semibold">
          {{ t('promotions.form.limits') }}
        </h2>
      </template>
      <div class="space-y-4">
        <div class="grid gap-4 sm:grid-cols-3">
          <UFormField
            :label="t('promotions.budget')"
            :help="isEdit && committed > 0
              ? t('promotions.form.budgetCommitted', { amount: formatMoney(committed, locale) })
              : t('promotions.form.budgetHelp')"
            required
          >
            <UInputNumber
              v-model="form.budget"
              :min="0.01"
              :step="10"
              :format-options="moneyFormat"
            />
          </UFormField>
          <UFormField
            :label="t('promotions.maxUsesPerPassenger')"
            required
          >
            <UInputNumber
              v-model="form.max_uses_per_passenger"
              :min="1"
              :max="PROMO_USES_PER_PASSENGER_MAX"
            />
          </UFormField>
          <UFormField
            :label="t('promotions.maxTotalUses')"
            :help="t('promotions.form.emptyNoLimit')"
          >
            <UInputNumber
              v-model="form.max_total_uses"
              :min="1"
              :max="PROMO_TOTAL_USES_MAX"
              :placeholder="t('promotions.form.noLimit')"
            />
          </UFormField>
        </div>
        <UCheckbox
          v-model="form.first_ride_only"
          :label="t('promotions.firstRideOnly')"
          :description="t('promotions.form.firstRideOnlyHelp')"
        />
      </div>
    </UCard>

    <UCard>
      <template #header>
        <h2 class="font-semibold">
          {{ t('promotions.form.scope') }}
        </h2>
        <p class="text-sm text-(--ui-text-muted)">
          {{ t('promotions.form.scopeHelp') }}
        </p>
      </template>
      <div class="grid gap-6 sm:grid-cols-2">
        <UFormField :label="t('promotions.serviceAreas')">
          <UCheckboxGroup
            v-model="form.service_areas"
            :items="areaItems"
          />
          <p
            v-if="!areaItems.length"
            class="text-sm text-(--ui-text-muted)"
          >
            {{ t('promotions.form.noAreas') }}
          </p>
        </UFormField>
        <UFormField :label="t('promotions.vehicleTypes')">
          <UCheckboxGroup
            v-model="form.vehicle_types"
            :items="vehicleItems"
          />
        </UFormField>
      </div>
    </UCard>

    <UAlert
      v-if="showIssues && issues.length"
      color="error"
      variant="subtle"
      icon="i-lucide-circle-alert"
      :title="t('promotions.form.fixErrors')"
    >
      <template #description>
        <ul class="list-disc pl-4">
          <li
            v-for="issue in issues"
            :key="issue.key"
          >
            {{ t(`promotions.errors.${issue.key}`, { ...issue.params, amount: issue.params?.amount ? formatMoney(issue.params.amount, locale) : '' }) }}
          </li>
        </ul>
      </template>
    </UAlert>

    <div class="sticky bottom-0 flex gap-2 bg-(--ui-bg) py-3">
      <UButton
        type="submit"
        :loading="saving"
        :disabled="!dirty"
        :label="isEdit ? t('common.save') : t('promotions.form.create')"
      />
      <UButton
        v-if="isEdit"
        color="neutral"
        variant="ghost"
        :disabled="!dirty || saving"
        :label="t('common.discard')"
        @click="load"
      />
    </div>
  </form>
</template>
