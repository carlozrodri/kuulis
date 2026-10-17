<script setup lang="ts">
import type { LegalDocument } from '~/utils/types'
import { isLegalKind } from '~/utils/types'

const { t, locale } = useI18n()
const route = useRoute()
const { request } = useApi()
const kind = computed(() => String(route.params.kind))
if (!isLegalKind(kind.value)) {
  throw createError({ statusCode: 404, statusMessage: 'Not found', fatal: true })
}

const { data: doc, error } = await useAsyncData(
  () => `legal-${kind.value}-${locale.value}`,
  () => request<LegalDocument>(`/legal/${kind.value}`, { query: { locale: locale.value } }),
  { watch: [locale] },
)
if (error.value && !doc.value) {
  throw createError({ statusCode: 404, statusMessage: 'Not found', fatal: true })
}

useSeoMeta({
  title: () => doc.value?.title ?? t('legal.metaTitle'),
  description: () => (doc.value ? t('legal.kindDescription', { title: doc.value.title }) : t('legal.metaDescription')),
})
</script>

<template>
  <section
    v-if="doc"
    class="section"
  >
    <article class="container narrow">
      <NuxtLinkLocale
        to="/legal"
        class="back"
      >
        ← {{ t('legal.back') }}
      </NuxtLinkLocale>
      <h1>{{ doc.title }}</h1>
      <p class="muted">
        {{ t('legal.version', { version: doc.version, date: formatDay(doc.published_at, locale) }) }}
      </p>
      <LegalMarkdown :source="doc.body_md" />
    </article>
  </section>
</template>

<style scoped>
.section {
  padding: clamp(40px, 7vw, 96px) 0 var(--section-y);
}

.back {
  display: inline-flex;
  align-items: center;
  min-height: 44px;
  margin-bottom: var(--space-4);
  color: var(--primary);
  font-weight: 700;
  text-decoration: none;
}

h1 {
  margin: 0 0 var(--space-3);
  font-size: var(--font-h1);
  line-height: var(--leading-tight);
  letter-spacing: var(--tracking-heading);
}

.muted {
  margin: 0 0 var(--space-7);
}
</style>
