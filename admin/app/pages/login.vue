<script setup lang="ts">
import { z } from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'

definePageMeta({ layout: 'auth' })

const { t } = useI18n()
const auth = useAuth()
const route = useRoute()
const apiError = useApiError()
const loading = ref(false)
const errorMessage = ref('')

const schema = computed(() =>
  z.object({
    email: z.email(t('validation.email')),
    password: z.string().min(1, t('validation.required')),
  }),
)
type Schema = z.output<typeof schema.value>
const state = reactive({ email: '', password: '' })

async function onSubmit(event: FormSubmitEvent<Schema>) {
  loading.value = true
  errorMessage.value = ''
  try {
    await auth.login(event.data.email, event.data.password)
    await navigateTo((route.query.redirect as string) || '/')
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
          {{ t('auth.title') }}
        </h1>
      </div>
    </template>

    <UForm
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
