<script setup lang="ts">
const { t } = useI18n()
const route = useRoute()
const { request } = useApi()
useSeoMeta({ title: () => t('reset.title'), robots: 'noindex, nofollow' })

const token = computed(() => (typeof route.query.token === 'string' ? route.query.token : ''))
type State = 'idle' | 'saving' | 'done' | 'invalid' | 'failed'
const state = ref<State>(token.value ? 'idle' : 'invalid')
const password = ref('')
const repeat = ref('')
const touched = ref(false)

const tooShort = computed(() => password.value.length < 8)
const mismatch = computed(() => repeat.value !== password.value)

async function save() {
  touched.value = true
  if (tooShort.value || mismatch.value) return
  state.value = 'saving'
  try {
    await request('/auth/password-reset/confirm', {
      method: 'POST',
      body: { token: token.value, new_password: password.value },
    })
    state.value = 'done'
  }
  catch (error) {
    const status = (error as { statusCode?: number }).statusCode ?? 0
    state.value = status === 422 ? 'idle' : status >= 400 && status < 500 ? 'invalid' : 'failed'
  }
}
</script>

<template>
  <UtilityCard>
    <template v-if="state === 'done'">
      <h1>{{ t('reset.doneTitle') }}</h1>
      <p class="muted">
        {{ t('reset.doneBody') }}
      </p>
    </template>
    <template v-else-if="state === 'invalid'">
      <h1>{{ t('reset.invalidTitle') }}</h1>
      <p class="muted">
        {{ t('reset.invalidBody') }}
      </p>
    </template>
    <form
      v-else
      novalidate
      @submit.prevent="save"
    >
      <h1>{{ t('reset.title') }}</h1>
      <p class="muted">
        {{ t('reset.body') }}
      </p>
      <label class="field">
        {{ t('reset.password') }}
        <input
          v-model="password"
          type="password"
          autocomplete="new-password"
          maxlength="128"
          required
        >
        <small>{{ touched && tooShort ? t('reset.tooShort') : t('reset.hint') }}</small>
      </label>
      <label class="field">
        {{ t('reset.repeat') }}
        <input
          v-model="repeat"
          type="password"
          autocomplete="new-password"
          maxlength="128"
          required
        >
        <small v-if="touched && mismatch">{{ t('reset.mismatch') }}</small>
      </label>
      <p
        v-if="state === 'failed'"
        class="notice notice-danger"
        role="alert"
      >
        {{ t('common.networkError') }}
      </p>
      <button
        type="submit"
        class="btn btn-primary wide"
        :disabled="state === 'saving'"
      >
        {{ state === 'saving' ? t('common.wait') : t('reset.button') }}
      </button>
    </form>
  </UtilityCard>
</template>

<style scoped>
.field small {
  color: var(--muted);
}
</style>
