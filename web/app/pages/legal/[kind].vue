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
  title: () => doc.value?.title ?? t('legal.title'),
  description: () => t('legal.metaDescription'),
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
        ← {{ t('legal.title') }}
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
.back {
  display: inline-block;
  margin-bottom: 20px;
  font-weight: 700;
  text-decoration: none;
}

h1 {
  font-size: clamp(1.9rem, 5vw, 2.8rem);
}
</style>
