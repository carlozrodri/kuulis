<script setup lang="ts">
const { t } = useI18n()
const route = useRoute()
const { request } = useApi()
useSeoMeta({ title: () => t('verify.title'), robots: 'noindex, nofollow' })

const token = computed(() => (typeof route.query.token === 'string' ? route.query.token : ''))
type State = 'idle' | 'saving' | 'done' | 'invalid' | 'failed'
const state = ref<State>(token.value ? 'idle' : 'invalid')

// A button, not an automatic call: mail scanners and link previews open the link too, and the
// token works only once.
async function confirm() {
  state.value = 'saving'
  try {
    await request('/auth/verify-email', { method: 'POST', body: { token: token.value } })
    state.value = 'done'
  }
  catch (error) {
    const status = (error as { statusCode?: number }).statusCode ?? 0
    state.value = status >= 400 && status < 500 ? 'invalid' : 'failed'
  }
}
</script>

<template>
  <UtilityCard>
    <template v-if="state === 'done'">
      <h1>{{ t('verify.doneTitle') }}</h1>
      <p class="muted">
        {{ t('verify.doneBody') }}
      </p>
    </template>
    <template v-else-if="state === 'invalid'">
      <h1>{{ t('verify.invalidTitle') }}</h1>
      <p class="muted">
        {{ t('verify.invalidBody') }}
      </p>
    </template>
    <template v-else>
      <h1>{{ t('verify.title') }}</h1>
      <p class="muted">
        {{ t('verify.body') }}
      </p>
      <p
        v-if="state === 'failed'"
        class="notice notice-danger"
        role="alert"
      >
        {{ t('common.networkError') }}
      </p>
      <button
        type="button"
        class="btn btn-primary wide"
        :disabled="state === 'saving'"
        @click="confirm"
      >
        {{ state === 'saving' ? t('common.wait') : t('verify.button') }}
      </button>
    </template>
  </UtilityCard>
</template>
