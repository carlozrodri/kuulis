<script setup lang="ts">
import type { LegalSummary } from '~/utils/types'

const { t, locale } = useI18n()
const { request } = useApi()
const { data: docs } = await useAsyncData(
  () => `legal-${locale.value}`,
  () => request<LegalSummary[]>('/legal', { query: { locale: locale.value } }).catch(() => []),
  { watch: [locale] },
)

useSeoMeta({ title: () => t('legal.metaTitle'), description: () => t('legal.metaDescription') })
</script>

<template>
  <section class="section">
    <div class="container narrow">
      <h1>{{ t('legal.title') }}</h1>
      <p class="muted">
        {{ t('legal.lead') }}
      </p>
      <div class="list">
        <NuxtLink
          v-for="doc in docs ?? []"
          :key="doc.kind"
          :to="`/legal/${doc.kind}`"
          class="card item"
        >
          <span>
            <strong>{{ doc.title }}</strong>
            <span class="muted small">{{ t('legal.version', { version: doc.version, date: formatDay(doc.published_at, locale) }) }}</span>
          </span>
          <span aria-hidden="true">→</span>
        </NuxtLink>
      </div>
    </div>
  </section>
</template>

<style scoped>
.list {
  display: grid;
  gap: 12px;
  margin-top: 24px;
}

.item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: var(--text);
  text-decoration: none;
}

.item > span:first-child {
  display: grid;
}

.small {
  font-size: 0.9rem;
}
</style>
