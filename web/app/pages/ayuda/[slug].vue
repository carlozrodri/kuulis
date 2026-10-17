<script setup lang="ts">
import type { HelpArticle } from '~/utils/types'

const { t, locale } = useI18n()
const route = useRoute()
const { request } = useApi()
const config = useRuntimeConfig()
const slug = computed(() => String(route.params.slug))
if (!/^[a-z0-9-]{1,120}$/.test(slug.value)) {
  throw createError({ statusCode: 404, statusMessage: 'Not found', fatal: true })
}

const { data: article, error } = await useAsyncData(
  () => `help-article-${slug.value}-${locale.value}`,
  () => request<HelpArticle>(`/help/articles/${slug.value}`, { query: { locale: locale.value } }),
  { watch: [locale] },
)
if (error.value && !article.value) {
  const notFound = (error.value as { statusCode?: number }).statusCode === 404
  throw createError({ statusCode: notFound ? 404 : 503, statusMessage: notFound ? 'Not found' : 'Unavailable', fatal: true })
}

// The excerpt is the article's Markdown flattened by the API: list dashes and the gap a removed link leaves
// before a full stop read badly in a search result.
const description = computed(() => (article.value?.excerpt
  ? article.value.excerpt.replace(/(^|\s)- /g, '$1').replace(/\s+([.,;:])/g, '$1')
  : t('help.metaDescription')))
const title = computed(() => (article.value ? `${article.value.title} · ${t('help.back')}` : t('help.metaTitle')))
useSeoMeta({
  title,
  description,
  ogTitle: () => article.value?.title ?? t('help.metaTitle'),
  ogDescription: description,
  ogType: 'article',
  ogUrl: () => `${config.public.siteUrl.replace(/\/$/, '')}/ayuda/${slug.value}`,
})

// "¿Te ayudó?": once per article and browser (remembered locally; the API also rate limits).
type Feedback = 'idle' | 'sending' | 'yes' | 'no' | 'failed'
const feedback = ref<Feedback>('idle')
const storageKey = computed(() => `kuulis_help_feedback_${article.value?.id ?? ''}`)
onMounted(() => {
  try {
    const saved = localStorage.getItem(storageKey.value)
    if (saved === 'yes' || saved === 'no') feedback.value = saved
  }
  catch {
    // Private mode or blocked storage: ask anyway.
  }
})
async function vote(helpful: boolean) {
  if (!article.value || feedback.value === 'sending' || feedback.value === 'yes' || feedback.value === 'no') return
  feedback.value = 'sending'
  try {
    await request(`/help/articles/${article.value.id}/feedback`, { method: 'POST', body: { helpful } })
  }
  catch (err) {
    // Already counted (rate limit) is as good as saved; anything else can be retried.
    if ((err as { statusCode?: number }).statusCode !== 429) {
      feedback.value = 'failed'
      return
    }
  }
  feedback.value = helpful ? 'yes' : 'no'
  try {
    localStorage.setItem(storageKey.value, feedback.value)
  }
  catch {
    // Not remembered: fine.
  }
}
</script>

<template>
  <section
    v-if="article"
    class="section"
  >
    <article class="container narrow">
      <nav class="crumbs">
        <NuxtLinkLocale to="/ayuda">
          ← {{ t('help.back') }}
        </NuxtLinkLocale>
        <span class="muted">· {{ t(`help.topics.${article.topic}`) }}</span>
      </nav>
      <h1>{{ article.title }}</h1>
      <p class="muted small">
        {{ t('help.updated', { date: formatDay(article.updated_at, locale) }) }}
      </p>
      <LegalMarkdown :source="article.body_md" />

      <div
        class="feedback"
        aria-live="polite"
      >
        <template v-if="feedback === 'yes' || feedback === 'no'">
          <p class="done">
            {{ feedback === 'yes' ? t('help.thanks') : t('help.sorry') }}
          </p>
        </template>
        <template v-else>
          <p class="question">
            {{ t('help.helpful') }}
          </p>
          <div class="actions">
            <button
              type="button"
              class="btn btn-ghost small-btn"
              :disabled="feedback === 'sending'"
              @click="vote(true)"
            >
              {{ t('help.yes') }}
            </button>
            <button
              type="button"
              class="btn btn-ghost small-btn"
              :disabled="feedback === 'sending'"
              @click="vote(false)"
            >
              {{ t('help.no') }}
            </button>
          </div>
          <p
            v-if="feedback === 'failed'"
            class="notice notice-danger"
            role="alert"
          >
            {{ t('help.feedbackFailed') }}
          </p>
        </template>
      </div>

      <div class="still">
        <h2>{{ t('help.stillTitle') }}</h2>
        <p class="muted">
          {{ t('help.stillBody') }}
        </p>
        <NuxtLinkLocale
          to="/contacto"
          class="btn btn-primary"
        >
          {{ t('help.stillButton') }}
        </NuxtLinkLocale>
      </div>
    </article>
  </section>
</template>

<style scoped>
.section {
  padding: clamp(40px, 7vw, 96px) 0 var(--section-y);
}

.crumbs {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
  min-height: 44px;
  margin-bottom: var(--space-4);
}

.crumbs a {
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

.small {
  margin: 0 0 var(--space-7);
  font-size: var(--font-small);
}

.feedback {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  margin-top: var(--space-8);
  padding: var(--space-5);
  border-radius: var(--radius-md);
  background: var(--surface-alt);
}

.feedback p {
  margin: 0;
}

.question,
.done {
  font-weight: 700;
}

.feedback .notice {
  flex-basis: 100%;
}

.actions {
  display: flex;
  gap: var(--space-2);
}

.small-btn {
  min-height: 44px;
  padding: 0 var(--space-5);
}

.still {
  margin-top: var(--space-8);
  padding-top: var(--space-7);
  border-top: 1px solid var(--border);
}

.still h2 {
  margin: 0 0 var(--space-2);
  font-size: var(--font-h2);
  letter-spacing: var(--tracking-heading);
}

.still p {
  margin: 0 0 var(--space-5);
}
</style>
