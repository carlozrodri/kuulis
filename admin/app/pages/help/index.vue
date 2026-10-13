<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { HelpArticleAdmin, HelpLocale, HelpTopic } from '~/types/api'
import { HELP_LOCALES, HELP_TOPICS } from '~/types/api'

definePageMeta({ permission: 'help.manage' })

const { t, locale } = useI18n()
const { request } = useApi()
const route = useRoute()
const router = useRouter()
const toast = useToast()
const apiError = useApiError()

const queryString = (key: string) => (typeof route.query[key] === 'string' ? route.query[key] as string : '')
const initialLocale = queryString('locale') as HelpLocale
const articleLocale = ref<HelpLocale>(HELP_LOCALES.includes(initialLocale) ? initialLocale : 'es')
const initialTopic = queryString('topic') as HelpTopic
const topic = ref<HelpTopic | 'all'>(HELP_TOPICS.includes(initialTopic) ? initialTopic : 'all')
const search = ref(queryString('q'))
const debouncedSearch = ref(search.value.trim())
let searchTimer: ReturnType<typeof setTimeout> | undefined
watch(search, (value) => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => (debouncedSearch.value = value.trim()), 300)
})
watch([articleLocale, topic, debouncedSearch], () => {
  router.replace({
    query: {
      ...(articleLocale.value !== 'es' ? { locale: articleLocale.value } : {}),
      ...(topic.value !== 'all' ? { topic: topic.value } : {}),
      ...(debouncedSearch.value ? { q: debouncedSearch.value } : {}),
    },
  })
})

const query = computed(() => ({
  locale: articleLocale.value,
  ...(topic.value !== 'all' ? { topic: topic.value } : {}),
  ...(debouncedSearch.value ? { q: debouncedSearch.value } : {}),
}))
const { data, status, error, refresh } = await useAsyncData(
  'help-articles',
  () => request<HelpArticleAdmin[]>('/admin/help/articles', { query: query.value }),
  { watch: [query] },
)

// By topic (in the catalogue order), then position, like the apps show them.
const items = computed(() =>
  [...(data.value ?? [])].sort((a, b) =>
    HELP_TOPICS.indexOf(a.topic) - HELP_TOPICS.indexOf(b.topic) || a.position - b.position || a.title.localeCompare(b.title)),
)

const localeTabs = computed(() => HELP_LOCALES.map(value => ({ label: t(`canned.locales.${value}`), value })))
const topicItems = computed(() => [
  { label: t('help.allTopics'), value: 'all' },
  ...HELP_TOPICS.map(value => ({ label: t(`help.topics.${value}`), value })),
])

const columns = computed<TableColumn<HelpArticleAdmin>[]>(() => [
  { accessorKey: 'topic', header: t('help.topic') },
  { accessorKey: 'title', header: t('help.title') },
  { accessorKey: 'published', header: t('help.published') },
  { accessorKey: 'views', header: t('help.views') },
  { id: 'helpful', header: t('help.helpful') },
  { accessorKey: 'updated_at', header: t('help.updated') },
  { id: 'actions', header: '' },
])

// ---- Publish / hide -----------------------------------------------------------------------------

const toggling = ref<string | null>(null)
async function setPublished(article: HelpArticleAdmin, published: boolean) {
  toggling.value = article.id
  try {
    await request(`/admin/help/articles/${article.id}`, { method: 'PATCH', body: { published } })
    toast.add({ title: t(published ? 'help.toast.published' : 'help.toast.hidden'), color: 'success' })
    await refresh()
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    toggling.value = null
  }
}

// ---- Delete -------------------------------------------------------------------------------------

const deleting = ref<HelpArticleAdmin | null>(null)
const deleteOpen = computed({
  get: () => deleting.value !== null,
  set: (open: boolean) => {
    if (!open) deleting.value = null
  },
})
const removing = ref(false)
async function confirmDelete() {
  if (!deleting.value) return
  removing.value = true
  try {
    await request(`/admin/help/articles/${deleting.value.id}`, { method: 'DELETE' })
    toast.add({ title: t('help.toast.deleted'), color: 'success' })
    deleting.value = null
    await refresh()
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
  <UDashboardPanel id="help-articles">
    <template #header>
      <UDashboardNavbar :title="t('nav.help')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton
            icon="i-lucide-plus"
            :label="t('help.new')"
            :to="{ path: '/help/new', query: { locale: articleLocale, ...(topic !== 'all' ? { topic } : {}) } }"
          />
        </template>
      </UDashboardNavbar>
      <UDashboardToolbar>
        <template #left>
          <div class="flex flex-wrap items-center gap-3">
            <UTabs
              v-model="articleLocale"
              :items="localeTabs"
              :content="false"
              size="sm"
              variant="link"
            />
            <USelect
              v-model="topic"
              :items="topicItems"
              class="w-52"
              :aria-label="t('help.topic')"
            />
          </div>
        </template>
        <template #right>
          <UInput
            v-model="search"
            icon="i-lucide-search"
            :placeholder="t('help.search')"
            maxlength="100"
            class="w-72 max-w-full"
          />
        </template>
      </UDashboardToolbar>
    </template>

    <template #body>
      <UAlert
        v-if="error"
        color="error"
        variant="subtle"
        icon="i-lucide-circle-alert"
        :title="apiError(error)"
      />

      <UTable
        :data="items"
        :columns="columns"
        :loading="status === 'pending'"
        :empty="t('help.empty')"
        :ui="{ tr: 'cursor-pointer' }"
        @select="(_e: Event, row: { original: HelpArticleAdmin }) => navigateTo(`/help/${row.original.id}`)"
      >
        <template #topic-cell="{ row }">
          <span class="whitespace-nowrap">{{ t(`help.topics.${row.original.topic}`, row.original.topic) }}</span>
          <p class="text-xs text-(--ui-text-muted)">
            {{ t('help.positionShort', { n: row.original.position }) }}
          </p>
        </template>
        <template #title-cell="{ row }">
          <p class="font-medium">
            {{ row.original.title }}
          </p>
          <p class="flex flex-wrap items-center gap-1 text-xs text-(--ui-text-muted)">
            <span class="font-mono">{{ row.original.slug }}</span>
            <UBadge
              v-if="row.original.audience !== 'all'"
              color="neutral"
              variant="outline"
              size="sm"
            >
              {{ t(`help.audiences.${row.original.audience}`) }}
            </UBadge>
          </p>
        </template>
        <template #published-cell="{ row }">
          <div @click.stop>
            <USwitch
              :model-value="row.original.published"
              :loading="toggling === row.original.id"
              :aria-label="t('help.published')"
              @update:model-value="(v: boolean) => setPublished(row.original, v)"
            />
          </div>
        </template>
        <template #views-cell="{ row }">
          <span class="tabular-nums">{{ formatNumber(row.original.views, locale) }}</span>
        </template>
        <template #helpful-cell="{ row }">
          <template v-if="helpfulRate(row.original.helpful_yes, row.original.helpful_no) !== null">
            <span
              class="font-medium tabular-nums"
              :class="(helpfulRate(row.original.helpful_yes, row.original.helpful_no) ?? 1) < 0.5 ? 'text-error' : ''"
            >
              {{ formatPercent(helpfulRate(row.original.helpful_yes, row.original.helpful_no), locale) }}
            </span>
            <p class="text-xs whitespace-nowrap text-(--ui-text-muted)">
              {{ t('help.helpfulCounts', { yes: row.original.helpful_yes, no: row.original.helpful_no }) }}
            </p>
          </template>
          <span
            v-else
            class="text-(--ui-text-muted)"
          >—</span>
        </template>
        <template #updated_at-cell="{ row }">
          <span class="text-sm whitespace-nowrap text-(--ui-text-muted)">{{ formatDate(row.original.updated_at, locale) }}</span>
        </template>
        <template #actions-cell="{ row }">
          <div class="flex justify-end gap-1">
            <UButton
              icon="i-lucide-pencil"
              size="xs"
              color="neutral"
              variant="ghost"
              :aria-label="t('help.edit')"
              :to="`/help/${row.original.id}`"
              @click.stop
            />
            <UButton
              icon="i-lucide-trash-2"
              size="xs"
              color="error"
              variant="ghost"
              :aria-label="t('help.delete')"
              @click.stop="deleting = row.original"
            />
          </div>
        </template>
      </UTable>

      <UModal
        v-model:open="deleteOpen"
        :title="t('help.deleteTitle')"
        :description="deleting ? t('help.deleteHelp', { title: deleting.title }) : ''"
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
              @click="confirmDelete"
            />
          </div>
        </template>
      </UModal>
    </template>
  </UDashboardPanel>
</template>
