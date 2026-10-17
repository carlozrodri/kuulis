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

const items = computed(() => (docs.value ?? []).map(doc => ({
  key: doc.kind,
  to: `/legal/${doc.kind}`,
  title: doc.title,
  meta: t('legal.version', { version: doc.version, date: formatDay(doc.published_at, locale.value) }),
})))
</script>

<template>
  <div class="container narrow page">
    <PageHead
      :title="t('legal.title')"
      :lead="t('legal.lead')"
    />
    <LinkList :items="items" />
  </div>
</template>

<style scoped>
.page {
  padding-bottom: var(--section-y);
}
</style>
