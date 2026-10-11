<script setup lang="ts">
definePageMeta({ layout: 'auth' })

const { t } = useI18n()
const config = useRuntimeConfig()
const route = useRoute()
const apiError = useApiError()

const token = computed(() => (typeof route.query.token === 'string' ? route.query.token : ''))
const password = ref('')
const confirm = ref('')
const loading = ref(false)
const done = ref(false)
const errorMessage = ref('')

const mismatch = computed(() => confirm.value.length > 0 && confirm.value !== password.value)

async function submit() {
  if (mismatch.value || !token.value) return
  loading.value = true
  errorMessage.value = ''
  try {
    await $fetch(`${config.public.apiBase}/auth/invite/accept`, {
      method: 'POST',
      body: { token: token.value, password: password.value },
    })
    done.value = true
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
  <UCard class="w-full max-w-sm">
    <template #header>
      <div class="flex items-center gap-2">
        <UIcon
          name="i-lucide-shield-check"
          class="size-6 text-primary"
        />
        <h1 class="text-lg font-semibold">
          {{ t('invite.title') }}
        </h1>
      </div>
    </template>

    <div
      v-if="done"
      class="space-y-4"
    >
      <p class="text-sm">
        {{ t('invite.done') }}
      </p>
      <UButton
        block
        to="/login"
        :label="t('invite.goLogin')"
      />
    </div>
    <UAlert
      v-else-if="!token"
      color="error"
      variant="subtle"
      :title="t('invite.noToken')"
    />
    <form
      v-else
      class="space-y-4"
      @submit.prevent="submit"
    >
      <p class="text-sm text-(--ui-text-muted)">
        {{ t('invite.help') }}
      </p>
      <UFormField
        :label="t('invite.password')"
        :hint="t('invite.passwordHint')"
        required
      >
        <UInput
          v-model="password"
          type="password"
          autocomplete="new-password"
          class="w-full"
          required
          minlength="8"
        />
      </UFormField>
      <UFormField
        :label="t('invite.confirm')"
        :error="mismatch ? t('invite.mismatch') : undefined"
        required
      >
        <UInput
          v-model="confirm"
          type="password"
          autocomplete="new-password"
          class="w-full"
          required
        />
      </UFormField>
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
        :disabled="mismatch || password.length < 8"
        :label="t('invite.submit')"
      />
    </form>
  </UCard>
</template>
