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
const steps = computed(() => [1, 2, 3, 4].map(n => ({ key: `step${n}`, body: t(`download.android.step${n}`) })))
// The header wears the hero's green until the hero scrolls past.
definePageMeta({ heroHeader: true })
</script>

<template>
  <div>
    <section
      id="hero"
      class="hero band-brand"
    >
      <div class="container-wide grid-hero">
        <div>
          <BrandHeadline
            as="h1"
            class="title"
            :text="t('download.title')"
          />
          <p class="lead">
            {{ t('download.lead') }}
          </p>
        </div>

        <div class="side">
          <!-- An iPhone sees its own answer first; the APK stays below for an Android phone nearby. -->
          <div
            v-if="isIphone"
            class="card iphone"
          >
            <p class="iphone-first">
              {{ t('download.iphoneFirst') }}
            </p>
            <h2>{{ t('download.iphone.title') }}</h2>
            <p class="muted">
              {{ t('download.iphone.body') }}
            </p>
          </div>

          <div
            v-if="release"
            class="card release"
          >
            <h2>{{ t('download.releaseTitle') }}</h2>
            <a
              class="btn btn-primary wide"
              :href="downloadUrl"
              rel="nofollow"
            >{{ t('download.button') }}</a>
            <p class="meta tabular">
              {{ t('download.meta', { version: release.version, build: release.build, size: sizeMb, date: formatDay(release.created_at, locale) }) }}
            </p>
            <p
              v-if="release.notes"
              class="muted notes"
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
        </div>
      </div>
    </section>

    <section
      v-reveal
      class="container-wide safety"
    >
      <div class="safety-block">
        <LineIcon
          name="shield-check"
          class="safety-icon"
        />
        <div>
          <h2>{{ t('download.safetyTitle') }}</h2>
          <p>{{ t('download.android.safety') }}</p>
        </div>
      </div>
    </section>

    <section
      v-reveal
      class="steps"
    >
      <div class="container-wide">
        <BrandHeadline :text="t('download.android.title')" />
        <RouteStops :items="steps" />
      </div>
    </section>
  </div>
</template>

<style scoped>
.hero {
  /* The header (64/72 px) sits on this field. */
  margin-top: -64px;
  padding: calc(64px + clamp(40px, 7vw, 96px)) 0 clamp(56px, 7vw, 112px);
}

.grid-hero {
  display: grid;
  gap: var(--space-7);
  align-items: center;
}

.title {
  max-width: 12ch;
  margin: 0 0 var(--space-5);
  font-size: var(--font-h1);
  line-height: var(--leading-tight);
  letter-spacing: var(--tracking-display);
}

.lead {
  max-width: 32rem;
  margin: 0;
  font-size: var(--font-lead);
  font-weight: 500;
  line-height: 1.45;
}

.side {
  display: grid;
  gap: var(--space-4);
}

/* The release is data, so it sits in a card on the green field, in the light theme's colors. */
.card {
  color: var(--text);
}

.card h2 {
  margin: 0 0 var(--space-4);
  font-size: var(--font-h3);
}

.wide {
  width: 100%;
}

.meta {
  margin: var(--space-4) 0 var(--space-1);
  font-weight: 600;
}

.notes {
  margin: 0 0 var(--space-3);
}

.fingerprint {
  margin-top: var(--space-3);
  padding-top: var(--space-3);
  border-top: 1px solid var(--border);
}

.fingerprint summary {
  min-height: 44px;
  display: flex;
  align-items: center;
  cursor: pointer;
  font-weight: 700;
}

.fingerprint code {
  display: block;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  background: var(--surface-alt);
  font-size: 0.85rem;
  word-break: break-all;
}

.small {
  font-size: var(--font-small);
}

.soon p,
.iphone p {
  margin: 0;
}

.iphone-first {
  margin-bottom: var(--space-2) !important;
  color: var(--primary);
  font-weight: 700;
}

.safety {
  padding-top: var(--section-y);
}

/* The anti-fraud warning stands out: a tinted block with the shield, not small print. */
.safety-block {
  display: flex;
  gap: var(--space-4);
  max-width: 48rem;
  padding: var(--space-5);
  border-radius: var(--radius-md);
  background: var(--surface-alt);
  box-shadow: inset 0 0 0 2px var(--primary);
}

.safety-icon {
  flex: none;
  color: var(--primary);
}

.safety-block h2 {
  margin: 0 0 var(--space-1);
  font-size: var(--font-h3);
}

.safety-block p {
  margin: 0;
}

.steps {
  padding: var(--space-8) 0 var(--section-y);
}

.steps :deep(h2.headline) {
  margin: 0 0 var(--space-7);
  font-size: var(--font-h2);
  letter-spacing: var(--tracking-heading);
}

@media (min-width: 960px) {
  .hero {
    margin-top: -72px;
    padding-top: calc(72px + 96px);
  }

  .grid-hero {
    grid-template-columns: 6fr 5fr;
    column-gap: var(--space-9);
  }
}
</style>
