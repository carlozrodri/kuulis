<script setup lang="ts">
const { t } = useI18n()
const { request } = useApi()
const apiError = useApiError()
const reauth = useReauth()

const code = ref('')
const loading = ref(false)
const errorMessage = ref('')

watch(reauth.open, (open) => {
  if (open) {
    code.value = ''
    errorMessage.value = ''
  }
})

async function confirm() {
  loading.value = true
  errorMessage.value = ''
  try {
    await request('/auth/admin/reauth', { method: 'POST', body: { code: code.value } })
    reauth.finish(true)
  }
  catch (error) {
    errorMessage.value = apiError(error)
  }
  finally {
    loading.value = false
  }
}
</script>

<template>
  <UModal
    :open="reauth.open.value"
    :title="t('totp.reauthTitle')"
    :description="t('totp.reauthHelp')"
    @update:open="(open: boolean) => { if (!open) reauth.finish(false) }"
  >
    <template #body>
      <form
        class="space-y-4"
        @submit.prevent="confirm"
      >
        <UInput
          v-model="code"
          inputmode="numeric"
          autocomplete="one-time-code"
          :placeholder="t('totp.codePlaceholder')"
          class="w-full"
          autofocus
        />
        <UAlert
          v-if="errorMessage"
          color="error"
          variant="subtle"
          :title="errorMessage"
        />
        <UButton
          type="submit"
          block
          :loading="loading"
          :label="t('totp.confirm')"
        />
      </form>
    </template>
  </UModal>
</template>
