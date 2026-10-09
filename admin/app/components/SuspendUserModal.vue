<script setup lang="ts">
import type { Suspension, SuspendInput } from '~/types/api'
import type { SuspensionPreset } from '~/utils/reports'

/**
 * Account suspension (POST /admin/users/{id}/suspend). Reusable from the user, driver and report pages; with
 * `reportId` the API leaves a note on that report.
 */
const props = defineProps<{
  userId: string
  name?: string | null
  reportId?: string | null
  /** Suspension in force, if any: a new one replaces it. */
  current?: Suspension | null
}>()
const open = defineModel<boolean>('open', { default: false })
const emit = defineEmits<{ suspended: [] }>()

const { t, locale } = useI18n()
const { request } = useApi()
const toast = useToast()
const apiError = useApiError()

const reason = ref('')
const preset = ref<SuspensionPreset>('7d')
const customDay = ref('')
const busy = ref(false)

const today = computed(() => caracasToday())

watch(open, (value) => {
  if (value) {
    reason.value = ''
    preset.value = '7d'
    customDay.value = addDays(today.value, 7)
  }
}, { immediate: true })

const presetItems = computed(() => SUSPENSION_PRESETS.map(value => ({ label: t(`suspensions.presets.${value}`), value })))

const until = computed(() => suspensionUntil(preset.value, customDay.value))
const customInvalid = computed(() => preset.value === 'custom' && (!isDay(customDay.value) || customDay.value < today.value))
const reasonLength = computed(() => reason.value.trim().length)
const canSubmit = computed(() =>
  reasonLength.value >= SUSPENSION_REASON_MIN && reasonLength.value <= SUSPENSION_REASON_MAX && !customInvalid.value,
)

async function submit() {
  if (!canSubmit.value) return
  const body: SuspendInput = {
    reason: reason.value.trim(),
    ...(until.value ? { until: until.value } : {}),
    ...(props.reportId ? { report_id: props.reportId } : {}),
  }
  busy.value = true
  try {
    await request(`/admin/users/${props.userId}/suspend`, { method: 'POST', body })
    toast.add({ title: t('suspensions.toast.suspended'), color: 'success' })
    open.value = false
    emit('suspended')
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    busy.value = false
  }
}
</script>

<template>
  <UModal
    v-model:open="open"
    :title="t('suspensions.modal.title', { name: name || t('suspensions.thisPerson') })"
    :description="t('suspensions.modal.description')"
  >
    <template #body>
      <form
        id="suspend-user-form"
        class="space-y-4"
        @submit.prevent="submit"
      >
        <UAlert
          color="neutral"
          variant="subtle"
          icon="i-lucide-info"
          :description="t('suspensions.modal.effects')"
        />
        <UAlert
          v-if="current"
          color="warning"
          variant="subtle"
          icon="i-lucide-triangle-alert"
          :title="t('suspensions.modal.replaces')"
          :description="current.reason"
        />
        <UAlert
          v-if="reportId"
          color="info"
          variant="subtle"
          icon="i-lucide-flag"
          :description="t('suspensions.modal.fromReport')"
        />

        <UFormField
          :label="t('suspensions.reason')"
          :help="t('suspensions.reasonHelp')"
          required
        >
          <UTextarea
            v-model="reason"
            class="w-full"
            :rows="3"
            :maxlength="SUSPENSION_REASON_MAX"
            autofocus
            required
          />
        </UFormField>

        <UFormField
          :label="t('suspensions.duration')"
          required
        >
          <URadioGroup
            v-model="preset"
            :items="presetItems"
            orientation="horizontal"
            variant="table"
            class="w-full"
            :ui="{ fieldset: 'flex-wrap' }"
          />
        </UFormField>

        <UFormField
          v-if="preset === 'custom'"
          :label="t('suspensions.customUntil')"
          :help="t('suspensions.customUntilHelp')"
          :error="customInvalid ? t('suspensions.customInvalid') : undefined"
        >
          <UInput
            v-model="customDay"
            type="date"
            :min="today"
            class="w-48"
          />
        </UFormField>

        <p class="text-sm">
          <template v-if="until">
            {{ t('suspensions.willEnd', { date: formatDate(until, locale) }) }}
          </template>
          <template v-else-if="preset === 'indefinite'">
            {{ t('suspensions.willNotEnd') }}
          </template>
        </p>
      </form>
    </template>
    <template #footer>
      <div class="flex w-full justify-end gap-2">
        <UButton
          color="neutral"
          variant="ghost"
          :label="t('common.cancel')"
          @click="open = false"
        />
        <UButton
          type="submit"
          form="suspend-user-form"
          color="error"
          icon="i-lucide-user-x"
          :label="t('suspensions.suspend')"
          :disabled="!canSubmit"
          :loading="busy"
        />
      </div>
    </template>
  </UModal>
</template>
