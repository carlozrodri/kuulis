<script setup lang="ts">
import { z } from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'
import type { AdminLoginStep } from '~/types/api'

definePageMeta({ layout: 'auth' })

const { t } = useI18n()
const auth = useAuth()
const route = useRoute()
const apiError = useApiError()
const loading = ref(false)
const errorMessage = ref('')

// password → code (or setup with QR) → recovery codes (only right after a setup)
const step = ref<AdminLoginStep | null>(null)
const code = ref('')
const recoveryCodes = ref<string[] | null>(null)

const schema = computed(() =>
  z.object({
    email: z.email(t('validation.email')),
    password: z.string().min(1, t('validation.required')),
  }),
)
type Schema = z.output<typeof schema.value>
const state = reactive({ email: '', password: '' })

const goOn = () => navigateTo((route.query.redirect as string) || '/')

async function run(action: () => Promise<void>) {
  loading.value = true
  errorMessage.value = ''
  try {
    await action()
  }
  catch (error) {
    errorMessage.value = apiError(error)
  }
  finally {
    loading.value = false
  }
}

function onSubmit(event: FormSubmitEvent<Schema>) {
  return run(async () => {
    step.value = await auth.login(event.data.email, event.data.password)
    code.value = ''
    if (!step.value) await goOn()
  })
}

function onCode() {
  return run(async () => {
    if (!step.value) return
    try {
      recoveryCodes.value = await auth.verifyTotp(step.value.challenge, code.value)
    }
    catch (error) {
      // The challenge expired (or too many tries): start again from the password.
      if ((error as { data?: { error?: { code?: string } } }).data?.error?.code === 'totp_challenge_expired') step.value = null
      throw error
    }
    if (!recoveryCodes.value) await goOn()
  })
}

const copied = ref(false)
async function copyCodes() {
  await navigator.clipboard.writeText(recoveryCodes.value?.join('\n') ?? '')
  copied.value = true
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
          {{ recoveryCodes ? t('totp.recoveryTitle') : step ? t('totp.title') : t('auth.title') }}
        </h1>
      </div>
    </template>

    <!-- 3. Recovery codes, once -->
    <div
      v-if="recoveryCodes"
      class="space-y-4"
    >
      <p class="text-sm text-(--ui-text-muted)">
        {{ t('totp.recoveryHelp') }}
      </p>
      <ul class="grid grid-cols-2 gap-2 rounded-md bg-(--ui-bg-elevated) p-3 font-mono text-sm">
        <li
          v-for="item in recoveryCodes"
          :key="item"
        >
          {{ item }}
        </li>
      </ul>
      <UButton
        block
        color="neutral"
        variant="outline"
        :icon="copied ? 'i-lucide-check' : 'i-lucide-copy'"
        :label="copied ? t('totp.copied') : t('totp.copy')"
        @click="copyCodes"
      />
      <UButton
        block
        :label="t('totp.continue')"
        @click="goOn"
      />
    </div>

    <!-- 2. Second factor (set it up first if needed) -->
    <form
      v-else-if="step"
      class="space-y-4"
      @submit.prevent="onCode"
    >
      <template v-if="step.setup">
        <p class="text-sm text-(--ui-text-muted)">
          {{ t('totp.setupHelp') }}
        </p>
        <img
          :src="step.setup.qr_data_uri"
          :alt="t('totp.qrAlt')"
          class="mx-auto size-48 rounded-md bg-white p-2"
        >
        <p class="text-center text-xs text-(--ui-text-muted)">
          {{ t('totp.manualKey') }}
          <span class="block font-mono break-all">{{ step.setup.secret }}</span>
        </p>
      </template>
      <p
        v-else
        class="text-sm text-(--ui-text-muted)"
      >
        {{ t('totp.codeHelp') }}
      </p>
      <UFormField :label="t('totp.code')">
        <UInput
          v-model="code"
          inputmode="numeric"
          autocomplete="one-time-code"
          :placeholder="t('totp.codePlaceholder')"
          class="w-full"
          autofocus
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
        :label="t('totp.confirm')"
      />
      <UButton
        block
        color="neutral"
        variant="ghost"
        :label="t('totp.back')"
        @click="step = null"
      />
    </form>

    <!-- 1. Email and password -->
    <UForm
      v-else
      :schema="schema"
      :state="state"
      class="space-y-4"
      @submit="onSubmit"
    >
      <UFormField
        :label="t('auth.email')"
        name="email"
      >
        <UInput
          v-model="state.email"
          type="email"
          autocomplete="username"
          class="w-full"
        />
      </UFormField>
      <UFormField
        :label="t('auth.password')"
        name="password"
      >
        <UInput
          v-model="state.password"
          type="password"
          autocomplete="current-password"
          class="w-full"
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
        :label="t('auth.login')"
      />
    </UForm>
  </UCard>
</template>
