<script setup lang="ts">
import type { HelpArticleSummary, HelpAudience, HelpTopic } from '~/utils/types'
import { HELP_TOPICS } from '~/utils/types'

const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const { request } = useApi()
const { whatsapp } = await useSupport()

// The search and the audience live in the URL (?q=…&para=driver): shareable and server rendered.
const q = computed(() => (typeof route.query.q === 'string' ? route.query.q.trim().slice(0, 100) : ''))
const audience = computed<Exclude<HelpAudience, 'all'> | null>(() =>
  route.query.para === 'passenger' || route.query.para === 'driver' ? route.query.para : null,
)

const { data: articles, error, status } = await useAsyncData(
  () => `help-${locale.value}-${audience.value ?? 'all'}-${q.value}`,
  () => request<HelpArticleSummary[]>('/help/articles', {
    query: { locale: locale.value, q: q.value || undefined, audience: audience.value ?? undefined },
  }),
  { watch: [locale, q, audience] },
)

const groups = computed(() => {
  const byTopic = new Map<HelpTopic, HelpArticleSummary[]>()
  for (const article of articles.value ?? []) {
    byTopic.set(article.topic, [...(byTopic.get(article.topic) ?? []), article])
  }
  return HELP_TOPICS.filter(topic => byTopic.has(topic)).map(topic => ({ topic, items: byTopic.get(topic)! }))
})

const term = ref(q.value)
watch(q, value => (term.value = value))
let timer: ReturnType<typeof setTimeout> | undefined
function search(value = term.value) {
  clearTimeout(timer)
  const next = value.trim()
  if (next === q.value) return
  router.replace({ query: { ...route.query, q: next || undefined } })
}
watch(term, (value) => {
  clearTimeout(timer)
  timer = setTimeout(() => search(value), 400)
})
onBeforeUnmount(() => clearTimeout(timer))

function setAudience(value: Exclude<HelpAudience, 'all'> | null) {
  router.replace({ query: { ...route.query, para: value ?? undefined } })
}
const audiences = [null, 'passenger', 'driver'] as const

useSeoMeta({
  title: () => t('help.metaTitle'),
  description: () => t('help.metaDescription'),
  ogTitle: () => t('help.metaTitle'),
  ogDescription: () => t('help.metaDescription'),
})
</script>

<template>
  <div>
    <section class="section intro">
      <div class="container narrow">
        <span class="eyebrow">{{ t('help.eyebrow') }}</span>
        <h1>{{ t('help.title') }}</h1>
        <p class="lead">
          {{ t('help.lead') }}
        </p>
        <form
          role="search"
          class="search"
          @submit.prevent="search()"
        >
          <label
            for="help-search"
            class="sr-only"
          >{{ t('help.search') }}</label>
          <input
            id="help-search"
            v-model="term"
            type="search"
            name="q"
            maxlength="100"
            autocomplete="off"
            :placeholder="t('help.searchPlaceholder')"
          >
          <button
            type="submit"
            class="btn btn-primary"
          >
            {{ t('help.searchButton') }}
          </button>
        </form>
        <div
          class="chips"
          role="group"
          :aria-label="t('help.audience.label')"
        >
          <button
            v-for="value in audiences"
            :key="value ?? 'all'"
            type="button"
            class="chip"
            :aria-pressed="audience === value"
            @click="setAudience(value)"
          >
            {{ t(`help.audience.${value ?? 'all'}`) }}
          </button>
        </div>
      </div>
    </section>

    <section class="container narrow">
      <p
        v-if="error && !articles"
        class="notice notice-danger"
        role="alert"
      >
        {{ t('help.loadFailed') }}
      </p>
      <template v-else>
        <div
          v-if="q"
          class="results-head"
        >
          <h2>{{ t('help.results', { q }) }}</h2>
          <button
            type="button"
            class="link"
            @click="term = ''; search('')"
          >
            {{ t('help.clear') }}
          </button>
        </div>
        <nav
          v-else-if="groups.length > 1"
          class="topics"
          :aria-label="t('help.topicsLabel')"
        >
          <a
            v-for="group in groups"
            :key="group.topic"
            :href="`#${group.topic}`"
            class="chip"
          >{{ t(`help.topics.${group.topic}`) }}</a>
        </nav>

        <p
          v-if="!groups.length && status !== 'pending'"
          class="muted empty"
        >
          {{ q ? t('help.noResults', { q }) : t('help.empty') }}
        </p>

        <div
          v-for="group in groups"
          :id="group.topic"
          :key="group.topic"
          class="topic"
        >
          <h2>{{ t(`help.topics.${group.topic}`) }}</h2>
          <div class="list">
            <NuxtLinkLocale
              v-for="article in group.items"
              :key="article.id"
              :to="`/ayuda/${article.slug}`"
              class="card item"
            >
              <span>
                <strong>{{ article.title }}</strong>
                <span
                  v-if="article.excerpt"
                  class="muted small"
                >{{ article.excerpt }}</span>
              </span>
              <span aria-hidden="true">→</span>
            </NuxtLinkLocale>
          </div>
        </div>
      </template>

      <div class="card contact">
        <div>
          <h2>{{ t('help.contactTitle') }}</h2>
          <p class="muted">
            {{ t('help.contactBody') }}
          </p>
        </div>
        <div class="actions">
          <NuxtLinkLocale
            to="/contacto"
            class="btn btn-primary"
          >
            {{ t('help.contactButton') }}
          </NuxtLinkLocale>
          <a
            v-if="whatsapp"
            :href="whatsapp"
            target="_blank"
            rel="noopener noreferrer"
            class="btn btn-ghost"
          >{{ t('help.whatsapp') }}</a>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.intro {
  padding-bottom: 32px;
}

.lead {
  font-size: 1.2rem;
  color: var(--muted);
}

.search {
  display: flex;
  gap: 10px;
  margin-top: 8px;
}

.search input {
  flex: 1;
  min-width: 0;
  min-height: 52px;
  padding: 0 18px;
  border: 2px solid var(--border);
  border-radius: 999px;
  background: var(--surface);
  color: var(--text);
  font: inherit;
}

.search input:focus {
  outline: none;
  border-color: var(--primary);
}

@media (max-width: 480px) {
  .search .btn {
    padding: 0 18px;
  }
}

.chips,
.topics {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
}

.topics {
  margin: 0 0 8px;
}

.chip {
  border: 0;
  background: var(--surface-alt);
  color: var(--text);
  font: inherit;
  font-weight: 700;
  font-size: 0.9rem;
  border-radius: 999px;
  padding: 8px 14px;
  cursor: pointer;
  text-decoration: none;
}

.chip[aria-pressed='true'] {
  background: var(--primary);
  color: var(--on-primary);
}

.results-head {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
}

.link {
  border: 0;
  background: none;
  padding: 0;
  color: var(--primary);
  font: inherit;
  font-weight: 700;
  cursor: pointer;
}

.empty {
  margin: 24px 0;
}

.topic {
  margin-top: 32px;
  scroll-margin-top: 84px;
}

.list {
  display: grid;
  gap: 12px;
}

.item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  color: var(--text);
  text-decoration: none;
}

.item > span:first-child {
  display: grid;
  gap: 4px;
}

.small {
  font-size: 0.9rem;
}

.contact {
  margin-top: 48px;
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.contact h2 {
  margin-top: 0;
}

.contact p {
  margin: 0;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
</style>
