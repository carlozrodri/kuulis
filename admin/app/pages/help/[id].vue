<script setup lang="ts">
import type { HelpArticleAdmin, HelpArticleInput, HelpAudience, HelpLocale, HelpTopic } from '~/types/api'
import { HELP_AUDIENCES, HELP_LOCALES, HELP_TOPICS } from '~/types/api'

definePageMeta({ permission: 'help.manage' })

const { t, locale } = useI18n()
const { request } = useApi()
const route = useRoute()
const toast = useToast()
const apiError = useApiError()

const id = computed(() => route.params.id as string)
const isNew = computed(() => id.value === 'new')
const queryString = (key: string) => (typeof route.query[key] === 'string' ? route.query[key] as string : '')

// The admin API has no single-article read: the article comes from the list.
const { data: article, status, error } = await useAsyncData(
  `help-article-${id.value}`,
  async () => {
    if (isNew.value) return null
    const list = await request<HelpArticleAdmin[]>('/admin/help/articles')
    return list.find(a => a.id === id.value) ?? null
  },
)

const fromQuery = (): HelpArticleInput => {
  const qLocale = queryString('locale') as HelpLocale
  const qTopic = queryString('topic') as HelpTopic
  const qAudience = queryString('audience') as HelpAudience
  return {
    slug: queryString('slug'),
    locale: HELP_LOCALES.includes(qLocale) ? qLocale : 'es',
    topic: HELP_TOPICS.includes(qTopic) ? qTopic : 'account',
    audience: HELP_AUDIENCES.includes(qAudience) ? qAudience : 'all',
    title: '',
    body_md: '',
    published: false,
    position: Number(queryString('position')) || 0,
  }
}
const toForm = (a: HelpArticleAdmin): HelpArticleInput => ({
  slug: a.slug, locale: a.locale, topic: a.topic, audience: a.audience, title: a.title, body_md: a.body_md, published: a.published, position: a.position,
})

const form = reactive<HelpArticleInput>(fromQuery())
const original = ref<HelpArticleInput | null>(null)
watch(article, (value) => {
  if (value) {
    Object.assign(form, toForm(value))
    original.value = toForm(value)
  }
}, { immediate: true })

// New article: the slug follows the title until someone edits it (translations keep the slug they came with).
const slugTouched = ref(!!form.slug)
watch(() => form.title, (title) => {
  if (isNew.value && !slugTouched.value) form.slug = slugify(title)
})

const localeItems = computed(() => HELP_LOCALES.map(value => ({ label: t(`canned.locales.${value}`), value: value as string })))
const topicItems = computed(() => HELP_TOPICS.map(value => ({ label: t(`help.topics.${value}`), value })))
const audienceItems = computed(() => HELP_AUDIENCES.map(value => ({ label: t(`help.audiences.${value}`), value })))

const slugValid = computed(() => HELP_SLUG.test(form.slug) && form.slug.length <= HELP_SLUG_MAX)
const valid = computed(() => slugValid.value && !!form.title.trim() && form.title.length <= HELP_TITLE_MAX && !!form.body_md.trim())
const dirty = computed(() => !original.value || JSON.stringify(form) !== JSON.stringify(original.value))

const saving = ref(false)
async function save() {
  if (!valid.value) return
  saving.value = true
  const body: HelpArticleInput = { ...form, title: form.title.trim(), body_md: form.body_md.trim(), position: Number(form.position) || 0 }
  try {
    if (isNew.value) {
      const created = await request<HelpArticleAdmin>('/admin/help/articles', { method: 'POST', body })
      toast.add({ title: t('help.toast.created'), color: 'success' })
      await navigateTo(`/help/${created.id}`, { replace: true })
    }
    else {
      const updated = await request<HelpArticleAdmin>(`/admin/help/articles/${id.value}`, { method: 'PATCH', body })
      article.value = updated ?? { ...article.value!, ...body }
      toast.add({ title: t('help.toast.updated'), color: 'success' })
    }
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    saving.value = false
  }
}

const otherLocale = computed(() => (form.locale === 'es' ? 'en' : 'es'))
const translateLink = computed(() => ({
  path: '/help/new',
  query: { slug: form.slug, locale: otherLocale.value, topic: form.topic, audience: form.audience, position: String(form.position) },
}))

// Narrow screens: one pane at a time.
const pane = ref<'write' | 'preview'>('write')
const paneItems = computed(() => [
  { label: t('help.write'), value: 'write' },
  { label: t('help.preview'), value: 'preview' },
])

const deleteOpen = ref(false)
const removing = ref(false)
async function remove() {
  removing.value = true
  try {
    await request(`/admin/help/articles/${id.value}`, { method: 'DELETE' })
    toast.add({ title: t('help.toast.deleted'), color: 'success' })
    await navigateTo('/help')
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    removing.value = false
  }
}
</script>

<template>
  <UDashboardPanel id="help-article">
    <template #header>
      <UDashboardNavbar :title="isNew ? t('help.new') : (article?.title ?? t('nav.help'))">
        <template #leading>
          <UButton
            icon="i-lucide-arrow-left"
            color="neutral"
            variant="ghost"
            :aria-label="t('common.back')"
            :to="{ path: '/help', query: form.locale !== 'es' ? { locale: form.locale } : {} }"
          />
        </template>
        <template #right>
          <UButton
            v-if="!isNew"
            icon="i-lucide-languages"
            color="neutral"
            variant="ghost"
            :label="t('help.translate', { locale: otherLocale.toUpperCase() })"
            :to="translateLink"
          />
          <UButton
            v-if="!isNew"
            icon="i-lucide-trash-2"
            color="error"
            variant="ghost"
            :label="t('help.delete')"
            @click="deleteOpen = true"
          />
          <UButton
            icon="i-lucide-save"
            :label="t('common.save')"
            :disabled="!valid || !dirty"
            :loading="saving"
            @click="save"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <UAlert
        v-if="error"
        color="error"
        variant="subtle"
        icon="i-lucide-circle-alert"
        :title="apiError(error)"
      />
      <USkeleton
        v-else-if="status === 'pending' && !isNew"
        class="h-96"
      />
      <UAlert
        v-else-if="!isNew && !article"
        color="warning"
        variant="subtle"
        icon="i-lucide-file-question"
        :title="t('help.notFound')"
      />

      <form
        v-else
        class="grid gap-6 lg:grid-cols-3"
        @submit.prevent="save"
      >
        <div class="grid content-start gap-6 lg:col-span-2">
          <UCard>
            <div class="space-y-4">
              <UFormField
                :label="t('help.title')"
                required
              >
                <UInput
                  v-model="form.title"
                  class="w-full"
                  size="lg"
                  :maxlength="HELP_TITLE_MAX"
                />
              </UFormField>
              <UTabs
                v-model="pane"
                :items="paneItems"
                :content="false"
                size="sm"
                class="lg:hidden"
              />
              <div class="grid gap-4 lg:grid-cols-2">
                <UFormField
                  :label="t('help.body')"
                  :help="t('help.bodyHelp')"
                  required
                  :class="pane === 'write' ? '' : 'hidden lg:block'"
                >
                  <UTextarea
                    v-model="form.body_md"
                    class="w-full font-mono"
                    :rows="18"
                    autoresize
                    :maxrows="40"
                  />
                </UFormField>
                <div :class="pane === 'preview' ? '' : 'hidden lg:block'">
                  <p class="mb-1.5 text-sm font-medium">
                    {{ t('help.preview') }}
                  </p>
                  <div class="min-h-40 rounded-md border border-(--ui-border) p-4">
                    <h1 class="mb-3 text-xl font-semibold">
                      {{ form.title || t('help.untitled') }}
                    </h1>
                    <MarkdownPreview
                      v-if="form.body_md.trim()"
                      :source="form.body_md"
                    />
                    <p
                      v-else
                      class="text-sm text-(--ui-text-muted)"
                    >
                      {{ t('help.previewEmpty') }}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </UCard>
        </div>

        <div class="grid content-start gap-6">
          <UCard>
            <div class="space-y-4">
              <USwitch
                v-model="form.published"
                :label="t('help.published')"
                :description="t('help.publishedHelp')"
              />
              <UFormField
                :label="t('help.slug')"
                :help="t('help.slugHelp')"
                :error="form.slug && !slugValid ? t('help.slugInvalid') : undefined"
                required
              >
                <UInput
                  v-model="form.slug"
                  class="w-full font-mono"
                  :maxlength="HELP_SLUG_MAX"
                  @input="slugTouched = true"
                />
              </UFormField>
              <UFormField :label="t('help.locale')">
                <USelect
                  v-model="form.locale"
                  :items="localeItems"
                  class="w-full"
                />
              </UFormField>
              <UFormField :label="t('help.topic')">
                <USelect
                  v-model="form.topic"
                  :items="topicItems"
                  class="w-full"
                />
              </UFormField>
              <UFormField
                :label="t('help.audience')"
                :help="t('help.audienceHelp')"
              >
                <USelect
                  v-model="form.audience"
                  :items="audienceItems"
                  class="w-full"
                />
              </UFormField>
              <UFormField
                :label="t('help.position')"
                :help="t('help.positionHelp')"
              >
                <UInputNumber
                  v-model="form.position"
                  :min="0"
                  :max="1000"
                />
              </UFormField>
            </div>
          </UCard>

          <UCard v-if="article">
            <template #header>
              <h2 class="font-semibold">
                {{ t('help.stats') }}
              </h2>
            </template>
            <dl class="grid grid-cols-2 gap-4 text-sm">
              <div>
                <dt class="text-(--ui-text-muted)">
                  {{ t('help.views') }}
                </dt>
                <dd class="text-lg font-semibold tabular-nums">
                  {{ formatNumber(article.views, locale) }}
                </dd>
              </div>
              <div>
                <dt class="text-(--ui-text-muted)">
                  {{ t('help.helpful') }}
                </dt>
                <dd class="text-lg font-semibold tabular-nums">
                  {{ formatPercent(helpfulRate(article.helpful_yes, article.helpful_no), locale) }}
                </dd>
                <dd class="text-xs text-(--ui-text-muted)">
                  {{ t('help.helpfulCounts', { yes: article.helpful_yes, no: article.helpful_no }) }}
                </dd>
              </div>
              <div class="col-span-2">
                <dt class="text-(--ui-text-muted)">
                  {{ t('help.updated') }}
                </dt>
                <dd>{{ formatDate(article.updated_at, locale) }}</dd>
              </div>
            </dl>
          </UCard>
        </div>
      </form>

      <UModal
        v-model:open="deleteOpen"
        :title="t('help.deleteTitle')"
        :description="t('help.deleteHelp', { title: form.title })"
      >
        <template #footer>
          <div class="flex w-full justify-end gap-2">
            <UButton
              color="neutral"
              variant="ghost"
              :label="t('common.cancel')"
              @click="deleteOpen = false"
            />
            <UButton
              color="error"
              icon="i-lucide-trash-2"
              :label="t('help.delete')"
              :loading="removing"
              @click="remove"
            />
          </div>
        </template>
      </UModal>
    </template>
  </UDashboardPanel>
</template>
