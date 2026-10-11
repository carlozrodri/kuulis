<script setup lang="ts">
const { t } = useI18n()

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

      <div class="card soon">
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
