<script setup lang="ts">
import type { VersionCheck } from '~/utils/types'

const { t, locale } = useI18n()
const { request } = useApi()
const { public: { apiBase } } = useRuntimeConfig()

// The newest APK published for this environment (doc 09); "coming soon" until there is one.
const { data: check } = await useAsyncData('app-version', () =>
  request<VersionCheck>('/app/version').catch(() => null),
)
const release = computed(() => check.value?.latest ?? null)
const sizeMb = computed(() => (release.value ? (release.value.size / 1_000_000).toFixed(1) : ''))
// Redirects to a short-lived link to the file in storage.
const downloadUrl = `${apiBase}/app/download`

useSeoMeta({
  title: () => t('download.metaTitle'),
  description: () => t('download.metaDescription'),
  ogTitle: () => t('download.metaTitle'),
  ogDescription: () => t('download.metaDescription'),
})

// Which phone is looking: Android gets the APK steps first, an iPhone the web app note (doc 09).
const headers = useRequestHeaders(['user-agent'])
const agent = import.meta.server ? headers['user-agent'] ?? '' : navigator.userAgent
const isIphone = /iPhone|iPad|iPod/i.test(agent)
</script>

<template>
  <section class="section">
    <div class="container narrow">
      <span class="eyebrow">{{ t('download.eyebrow') }}</span>
      <h1>{{ t('download.title') }}</h1>
      <p class="lead">
        {{ t('download.lead') }}
      </p>

      <div
        v-if="release"
        class="card release"
      >
        <a
          class="btn btn-accent"
          :href="downloadUrl"
          rel="nofollow"
        >{{ t('download.button') }}</a>
        <p class="meta">
          {{ t('download.meta', { version: release.version, build: release.build, size: sizeMb, date: formatDay(release.created_at, locale) }) }}
        </p>
        <p
          v-if="release.notes"
          class="muted"
        >
          {{ release.notes }}
        </p>
        <details class="fingerprint">
          <summary>{{ t('download.fingerprint') }}</summary>
          <p class="muted small">
            {{ t('download.fingerprintHelp') }}
          </p>
          <code>{{ release.sha256 }}</code>
        </details>
      </div>

      <div
        v-else
        class="card soon"
      >
        <h2>{{ t('download.soon.title') }}</h2>
        <p class="muted">
          {{ t('download.soon.body') }}
        </p>
      </div>

      <div
        v-if="isIphone"
        class="card"
      >
        <h3>{{ t('download.iphone.title') }}</h3>
        <p class="muted">
          {{ t('download.iphone.body') }}
        </p>
      </div>

      <h2 class="steps-title">
        {{ t('download.android.title') }}
      </h2>
      <ol class="steps">
        <li
          v-for="n in 4"
          :key="n"
        >
          {{ t(`download.android.step${n}`) }}
        </li>
      </ol>
      <p class="muted small">
        {{ t('download.android.safety') }}
      </p>
    </div>
  </section>
</template>

<style scoped>
.lead {
  font-size: 1.2rem;
  color: var(--muted);
}

.release {
  margin-bottom: 16px;
}

.meta {
  margin: 12px 0 4px;
  font-weight: 600;
}

.fingerprint summary {
  cursor: pointer;
  font-weight: 600;
}

.fingerprint code {
  display: block;
  word-break: break-all;
  font-size: 0.85rem;
  padding: 8px;
  background: var(--surface-alt);
  border-radius: 8px;
}

.soon {
  border: 2px dashed var(--primary);
  box-shadow: none;
  margin-bottom: 16px;
}

.steps-title {
  margin-top: 40px;
}

.steps {
  padding-left: 1.3em;
}

.steps li {
  margin-bottom: 10px;
}

.small {
  font-size: 0.9rem;
}
</style>
