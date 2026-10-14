<script setup lang="ts">
import type { RiskUserDetail } from '~/types/api'

/**
 * Bans an account (doc 16): suspends it with no end and blocks its email, cédula, RIF, plate, phones and
 * Binance Pay ID so they cannot open a new account.
 */
const props = defineProps<{ userId: string, name?: string | null }>()
const open = defineModel<boolean>('open', { default: false })
const emit = defineEmits<{ banned: [detail: RiskUserDetail] }>()

const { t } = useI18n()
const { request } = useApi()
const toast = useToast()
const apiError = useApiError()

const reason = ref('')
const busy = ref(false)
watch(open, (value) => {
  if (value) reason.value = ''
})
const length = computed(() => reason.value.trim().length)
const canSubmit = computed(() => length.value >= RISK_BAN_REASON_MIN && length.value <= RISK_BAN_REASON_MAX)

async function submit() {
  if (!canSubmit.value) return
  busy.value = true
  try {
    const detail = await request<RiskUserDetail>(`/admin/risk/users/${props.userId}/ban`, { method: 'POST', body: { reason: reason.value.trim() } })
    toast.add({ title: t('risk.ban.done'), color: 'success' })
    open.value = false
    emit('banned', detail)
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
    :title="t('risk.ban.title', { name: name || t('suspensions.thisPerson') })"
  >
    <template #body>
      <form
        id="risk-ban-form"
        class="space-y-4"
        @submit.prevent="submit"
      >
        <UAlert
          color="error"
          variant="subtle"
          icon="i-lucide-ban"
          :description="t('risk.ban.effects')"
        />
        <UFormField
          :label="t('risk.ban.reason')"
          :help="t('risk.ban.reasonHelp', { min: RISK_BAN_REASON_MIN })"
          required
        >
          <UTextarea
            v-model="reason"
            class="w-full"
            :rows="3"
            :maxlength="RISK_BAN_REASON_MAX"
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
          @click="open = false"
        />
        <UButton
          type="submit"
          form="risk-ban-form"
          color="error"
          icon="i-lucide-ban"
          :label="t('risk.ban.submit')"
          :disabled="!canSubmit"
          :loading="busy"
        />
      </div>
    </template>
  </UModal>
</template>
