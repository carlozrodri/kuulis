<script setup lang="ts">
/** Admin-only manual balance adjustment (POST /admin/wallets/{user_id}/adjust). */
const props = defineProps<{ userId: string, balance: string | number | null | undefined, name?: string | null }>()
const emit = defineEmits<{ adjusted: [] }>()
const open = defineModel<boolean>('open', { default: false })

const { t, locale } = useI18n()
const { request } = useApi()
const toast = useToast()
const apiError = useApiError()

const ADJUST_MAX = 10_000
const amount = ref<number | null>(null)
const reason = ref('')
const saving = ref(false)

watch(open, (value) => {
  if (value) {
    amount.value = null
    reason.value = ''
  }
})

const current = computed(() => sumAmounts([props.balance]))
const resulting = computed(() => sumAmounts([props.balance, amount.value ?? 0]))
const validAmount = computed(() => amount.value !== null && Number.isFinite(amount.value) && amount.value !== 0 && Math.abs(amount.value) <= ADJUST_MAX)
const negative = computed(() => validAmount.value && resulting.value < 0)
const canSubmit = computed(() => validAmount.value && !negative.value && !!reason.value.trim())

async function submit() {
  if (!canSubmit.value || amount.value === null) return
  saving.value = true
  try {
    await request(`/admin/wallets/${props.userId}/adjust`, {
      method: 'POST',
      body: { amount: amount.value.toFixed(2), reason: reason.value.trim() },
    })
    toast.add({ title: t('wallet.adjust.done'), color: 'success' })
    open.value = false
    emit('adjusted')
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    saving.value = false
  }
}

const moneyFormat = { minimumFractionDigits: 2, maximumFractionDigits: 2, signDisplay: 'exceptZero' as const }
</script>

<template>
  <UModal
    v-model:open="open"
    :title="t('wallet.adjust.title')"
    :description="name ? t('wallet.adjust.descriptionFor', { name }) : t('wallet.adjust.description')"
  >
    <template #body>
      <form
        id="adjust-form"
        class="space-y-4"
        @submit.prevent="submit"
      >
        <UFormField
          :label="t('wallet.adjust.amount')"
          :help="t('wallet.adjust.amountHelp')"
          required
        >
          <UInputNumber
            v-model="amount"
            :min="-ADJUST_MAX"
            :max="ADJUST_MAX"
            :step="1"
            :format-options="moneyFormat"
            class="w-full"
          />
        </UFormField>
        <dl class="grid grid-cols-2 gap-4 rounded-md bg-(--ui-bg-elevated) p-3 text-sm">
          <div>
            <dt class="text-(--ui-text-muted)">
              {{ t('wallet.balance') }}
            </dt>
            <dd class="tabular-nums">
              {{ formatUsdt(current, locale) }}
            </dd>
          </div>
          <div>
            <dt class="text-(--ui-text-muted)">
              {{ t('wallet.adjust.resulting') }}
            </dt>
            <dd
              class="font-medium tabular-nums"
              :class="{ 'text-error': negative }"
            >
              {{ formatUsdt(resulting, locale) }}
            </dd>
          </div>
        </dl>
        <p
          v-if="negative"
          class="text-sm text-error"
        >
          {{ t('wallet.adjust.negative') }}
        </p>
        <UFormField
          :label="t('wallet.adjust.reason')"
          :help="t('wallet.adjust.reasonHelp')"
          required
        >
          <UTextarea
            v-model="reason"
            class="w-full"
            :rows="3"
            maxlength="500"
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
          form="adjust-form"
          :label="t('wallet.adjust.submit')"
          :disabled="!canSubmit"
          :loading="saving"
        />
      </div>
    </template>
  </UModal>
</template>
