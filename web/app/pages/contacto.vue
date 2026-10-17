<script setup lang="ts">
import type { ContactCategory, ContactChallenge } from '~/utils/types'
import { solveChallenge } from '~/utils/pow'

const { t, locale } = useI18n()
const { request } = useApi()
const { whatsapp, email: supportEmail, promise } = await useSupport()

useSeoMeta({
  title: () => t('contact.metaTitle'),
  description: () => t('contact.metaDescription'),
  ogTitle: () => t('contact.metaTitle'),
  ogDescription: () => t('contact.metaDescription'),
})

const MAX_MESSAGE = 2000
const name = ref('')
const email = ref('')
const category = ref<ContactCategory>('app_issue')
const message = ref('')
const touched = ref(false)

const errors = computed(() => ({
  name: name.value.trim().length < 2,
  email: !/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email.value.trim()),
  message: message.value.trim().length < 10,
}))
const valid = computed(() => !errors.value.name && !errors.value.email && !errors.value.message)

type State = 'idle' | 'verifying' | 'sending' | 'done'
const state = ref<State>('idle')
const failure = ref<string | null>(null)
const sentTo = ref('')

// The proof of work starts as soon as the visitor touches the form, so it is usually ready by the
// time they press Send. Each solved challenge is used once.
interface Proof { challenge: string, nonce: string, expiresAt: number }
let pending: Promise<Proof> | null = null
let controller: AbortController | null = null

function prepare(): Promise<Proof> {
  controller?.abort()
  const current = new AbortController()
  controller = current
  const job = (async () => {
    const issued = Date.now()
    const { challenge, difficulty, expires_in } = await request<ContactChallenge>('/public/contact/challenge', { signal: current.signal })
    const nonce = await solveChallenge(challenge, difficulty, { signal: current.signal })
    return { challenge, nonce, expiresAt: issued + expires_in * 1000 }
  })()
  job.catch(() => {}) // a background attempt that fails is retried on submit
  pending = job
  return job
}

function warmUp() {
  if (!pending && state.value === 'idle') prepare()
}

async function proof(): Promise<Proof> {
  if (pending) {
    try {
      const ready = await pending
      // Leave margin for the request itself.
      if (ready.expiresAt - Date.now() > 15_000) return ready
    }
    catch {
      // Failed in the background: start over below.
    }
  }
  return prepare()
}

onBeforeUnmount(() => controller?.abort())

async function submit() {
  touched.value = true
  failure.value = null
  if (!valid.value || state.value === 'verifying' || state.value === 'sending') return
  let retried = false
  for (;;) {
    try {
      state.value = 'verifying'
      const { challenge, nonce } = await proof()
      pending = null
      state.value = 'sending'
      await request('/public/contact', {
        method: 'POST',
        body: {
          name: name.value.trim(),
          email: email.value.trim(),
          category: category.value,
          message: message.value.trim(),
          locale: locale.value === 'en' ? 'en' : 'es',
          challenge,
          nonce,
        },
      })
      sentTo.value = email.value.trim()
      state.value = 'done'
      return
    }
    catch (error) {
      const status = (error as { statusCode?: number }).statusCode ?? 0
      const code = apiErrorCode(error)
      if (code === 'captcha_invalid' && !retried) {
        retried = true
        continue
      }
      state.value = 'idle'
      failure.value = code === 'captcha_invalid'
        ? t('contact.errors.captcha')
        : status === 429
          ? t('contact.errors.limited')
          : status === 400 || status === 422
            ? t('contact.errors.invalid')
            : t('common.networkError')
      return
    }
  }
}

function again() {
  message.value = ''
  touched.value = false
  failure.value = null
  state.value = 'idle'
}
</script>

<template>
  <section class="contact-page">
    <div class="container-wide">
      <PageHead
        class="head"
        :stop="t('contact.stop')"
        :title="t('contact.title')"
      />

      <div
        v-if="state === 'done'"
        class="card done"
        role="status"
      >
        <h2 class="done-title">
          {{ t('contact.doneTitle') }}
        </h2>
        <p>{{ t('contact.doneBody', { email: sentTo }) }}</p>
        <p
          v-if="promise"
          class="promise"
        >
          {{ promise }}
        </p>
        <p class="muted small">
          {{ t('contact.doneSpam') }}
        </p>
        <div class="actions">
          <NuxtLinkLocale
            to="/ayuda"
            class="btn btn-primary"
          >
            {{ t('contact.helpLink') }}
          </NuxtLinkLocale>
          <button
            type="button"
            class="btn btn-ghost"
            @click="again"
          >
            {{ t('contact.another') }}
          </button>
        </div>
      </div>

      <div
        v-else
        class="grid-contact"
      >
        <div class="aside">
          <p class="lead">
            {{ t('contact.lead') }}
            <template v-if="promise">
              {{ promise }}
            </template>
          </p>
          <p class="notice in-app">
            {{ t('contact.inApp') }}
          </p>
          <div
            v-if="whatsapp || supportEmail"
            class="other"
          >
            <h2>{{ t('contact.other') }}</h2>
            <div class="actions">
              <a
                v-if="whatsapp"
                :href="whatsapp"
                target="_blank"
                rel="noopener noreferrer"
                class="btn btn-ghost"
              >{{ t('help.whatsapp') }}</a>
              <a
                v-if="supportEmail"
                :href="`mailto:${supportEmail}`"
                class="btn btn-ghost"
              >{{ supportEmail }}</a>
            </div>
          </div>
        </div>

        <form
          class="card form"
          novalidate
          @submit.prevent="submit"
          @focusin="warmUp"
        >
          <label class="field">
            {{ t('contact.name') }}
            <input
              v-model="name"
              type="text"
              name="name"
              autocomplete="name"
              maxlength="120"
              required
              :aria-invalid="touched && errors.name"
            >
            <small
              v-if="touched && errors.name"
              class="error"
            >{{ t('contact.errors.name') }}</small>
          </label>
          <label class="field">
            {{ t('contact.email') }}
            <input
              v-model="email"
              type="email"
              name="email"
              autocomplete="email"
              inputmode="email"
              maxlength="254"
              required
              :aria-invalid="touched && errors.email"
            >
            <small :class="{ error: touched && errors.email }">{{ touched && errors.email ? t('contact.errors.email') : t('contact.emailHint') }}</small>
          </label>
          <label class="field">
            {{ t('contact.category') }}
            <select
              v-model="category"
              name="category"
            >
              <option value="app_issue">{{ t('contact.categories.app_issue') }}</option>
              <option value="other">{{ t('contact.categories.other') }}</option>
            </select>
          </label>
          <label class="field">
            {{ t('contact.message') }}
            <textarea
              v-model="message"
              name="message"
              rows="6"
              :maxlength="MAX_MESSAGE"
              required
              :aria-invalid="touched && errors.message"
            />
            <small :class="{ error: touched && errors.message }">
              {{ touched && errors.message ? t('contact.errors.message') : t('contact.messageHint') }}
            </small>
            <small class="count">{{ t('contact.count', { n: message.length, max: MAX_MESSAGE }) }}</small>
          </label>

          <p
            v-if="failure"
            class="notice notice-danger"
            role="alert"
          >
            {{ failure }}
          </p>
          <p
            v-if="state === 'verifying'"
            class="notice verifying"
            role="status"
          >
            <span
              class="spinner"
              aria-hidden="true"
            />
            {{ t('contact.verifying') }}
          </p>

          <button
            type="submit"
            class="btn btn-primary wide"
            :disabled="state !== 'idle'"
          >
            {{ state === 'verifying' ? t('common.wait') : state === 'sending' ? t('contact.sending') : t('contact.send') }}
          </button>
          <p class="muted small privacy">
            {{ t('contact.privacy') }}
            <NuxtLinkLocale to="/legal/privacy">
              {{ t('legal.kinds.privacy') }}
            </NuxtLinkLocale>.
          </p>
        </form>
      </div>
    </div>
  </section>
</template>

<style scoped>
.contact-page {
  padding-bottom: var(--section-y);
}

.head {
  padding-bottom: var(--space-5);
}

.grid-contact {
  display: grid;
  gap: var(--space-6);
  align-items: start;
}

.lead {
  max-width: 34rem;
  margin: 0 0 var(--space-5);
  color: var(--muted);
  font-size: var(--font-lead);
  line-height: 1.5;
}

.in-app {
  max-width: 34rem;
  margin: 0;
  background: var(--surface-alt);
}

.done {
  max-width: 40rem;
}

.field .error {
  color: var(--danger);
}

.count {
  justify-self: end;
}

.verifying {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  background: var(--surface-alt);
}

.spinner {
  width: 18px;
  height: 18px;
  border: 3px solid var(--border);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .spinner {
    animation-duration: 2.4s;
  }
}

.wide {
  width: 100%;
  margin-top: var(--space-2);
}

.privacy {
  margin: var(--space-4) 0 0;
}

.small {
  font-size: var(--font-small);
}

.done-title {
  margin-top: 0;
}

.promise {
  font-weight: 700;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-2);
}

.other {
  margin-top: var(--space-7);
}

.other h2 {
  margin: 0 0 var(--space-3);
  font-size: var(--font-h3);
}

@media (min-width: 960px) {
  .grid-contact {
    grid-template-columns: 5fr 7fr;
    column-gap: var(--space-9);
  }
}
</style>
