<script setup lang="ts">
import type { MarketingAudience, MarketingContent, MarketingContentSummary, MarketingProduction, Page } from '~/types/api'
import { MARKETING_AUDIENCES, MARKETING_PRODUCTIONS } from '~/types/api'

definePageMeta({ permission: 'marketing.view' })

const { t, locale } = useI18n()
const { request } = useApi()
const auth = useAuth()
const toast = useToast()
const apiError = useApiError()
const route = useRoute()
const router = useRouter()

// View, tab, month and search in the URL, so "back" from a piece returns to the same view.
const today = caracasToday()
type View = 'galeria' | 'calendario'
const view = ref<View>(route.query.view === 'calendario' ? 'calendario' : 'galeria')
const initialTab = (typeof route.query.status === 'string' ? route.query.status : 'activas') as PieceTab
const tab = ref<PieceTab>(PIECE_TABS.includes(initialTab) ? initialTab : 'activas')
const initialMonth = typeof route.query.month === 'string' && /^\d{4}-\d{2}$/.test(route.query.month) ? route.query.month : today.slice(0, 7)
const month = ref(initialMonth)
const search = ref(typeof route.query.q === 'string' ? route.query.q : '')
const debounced = ref(search.value.trim())
let timer: ReturnType<typeof setTimeout> | undefined
watch(search, (value) => {
  clearTimeout(timer)
  timer = setTimeout(() => (debounced.value = value.trim()), 300)
})
watch([view, tab, month, debounced], () => {
  router.replace({
    query: {
      ...(view.value !== 'galeria' ? { view: view.value } : {}),
      ...(tab.value !== 'activas' ? { status: tab.value } : {}),
      ...(view.value === 'calendario' && month.value !== today.slice(0, 7) ? { month: month.value } : {}),
      ...(debounced.value ? { q: debounced.value } : {}),
    },
  })
})

const PAGE = 48
const pages = ref(1)
const query = computed(() => {
  const status = tabStatus(tab.value)
  const base = {
    ...(status ? { status } : {}),
    ...(debounced.value ? { q: debounced.value } : {}),
  }
  return view.value === 'calendario'
    ? { ...base, limit: 100, from: `${month.value}-01`, to: endOfMonth(`${month.value}-01`) }
    : { ...base, limit: Math.min(100, PAGE * pages.value) }
})
watch([view, tab, debounced], () => (pages.value = 1))

// Newest first, pieces without a date (fresh ideas and videos) before the planned ones.
const { data, status: fetchStatus, error, refresh } = await useAsyncData(
  'marketing-pieces',
  () => request<Page<MarketingContentSummary>>('/admin/marketing/contents', { query: query.value }),
  { watch: [query] },
)
const items = computed(() => (data.value?.items ?? []).filter(i => inTab(i.status, tab.value)))
const canLoadMore = computed(() => view.value === 'galeria' && !!data.value && data.value.items.length < data.value.total && data.value.limit < 100)

const days = computed(() => {
  const groups = new Map<string, MarketingContentSummary[]>()
  for (const item of items.value) {
    if (!item.scheduled_for) continue
    const list = groups.get(item.scheduled_for) ?? []
    list.push(item)
    groups.set(item.scheduled_for, list)
  }
  return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b))
})

const monthLabel = computed(() =>
  new Intl.DateTimeFormat(locale.value, { month: 'long', year: 'numeric', timeZone: 'UTC' }).format(new Date(`${month.value}-01T00:00:00Z`)),
)
const dayLabel = (day: string) =>
  new Intl.DateTimeFormat(locale.value, { weekday: 'long', day: 'numeric', month: 'short', timeZone: 'UTC' }).format(new Date(`${day}T00:00:00Z`))

const tabItems = computed(() => PIECE_TABS.map(value => ({
  label: value === 'activas' ? t('marketing.gallery.active') : t(`marketing.statuses.${value}`),
  value,
})))
const viewItems = computed(() => [
  { label: t('marketing.gallery.galleryView'), value: 'galeria', icon: 'i-lucide-layout-grid' },
  { label: t('marketing.gallery.calendarView'), value: 'calendario', icon: 'i-lucide-calendar-days' },
])

const playing = ref<MarketingContentSummary | null>(null)

// ---- New piece --------------------------------------------------------------------------------
const creating = ref(false)
const form = reactive({
  title: '',
  pillar: '',
  format: '',
  audience: 'ambos' as MarketingAudience,
  production: 'ia' as MarketingProduction,
  uses_character: false,
  scheduled_for: '',
  notes: '',
})
const audienceItems = computed(() => MARKETING_AUDIENCES.map(value => ({ label: t(`marketing.audiences.${value}`), value })))
const productionItems = computed(() => MARKETING_PRODUCTIONS.map(value => ({ label: t(`marketing.productions.${value}`), value })))
function startCreate() {
  Object.assign(form, { title: '', pillar: '', format: '', audience: 'ambos', production: 'ia', uses_character: false, scheduled_for: '', notes: '' })
  creating.value = true
}
const saving = ref(false)
async function create() {
  if (!form.title.trim()) return
  saving.value = true
  try {
    const content = await request<MarketingContent>('/admin/marketing/contents', {
      method: 'POST',
      body: {
        title: form.title.trim(),
        pillar: form.pillar.trim() || null,
        format: form.format.trim() || null,
        audience: form.audience,
        production: form.production,
        uses_character: form.uses_character,
        scheduled_for: form.scheduled_for || null,
        notes: form.notes.trim() || null,
      },
    })
    creating.value = false
    toast.add({ title: t('marketing.created', { code: content.code }), color: 'success' })
    await navigateTo(`/marketing/piezas/${content.id}`)
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    saving.value = false
  }
}

async function reload() {
  await refresh()
}
</script>

<template>
  <UDashboardPanel id="marketing-pieces">
    <template #header>
      <UDashboardNavbar :title="t('nav.marketingCalendar')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton
            icon="i-lucide-refresh-cw"
            color="neutral"
            variant="ghost"
            :loading="fetchStatus === 'pending'"
            :aria-label="t('marketing.refresh')"
            @click="reload"
          />
          <UButton
            v-if="auth.can('marketing.manage')"
            icon="i-lucide-plus"
            :label="t('marketing.new')"
            @click="startCreate"
          />
        </template>
      </UDashboardNavbar>
      <UDashboardToolbar :ui="{ root: 'flex-wrap gap-y-2 py-2 h-auto', left: 'min-w-0 max-w-full overflow-x-auto', right: 'w-full sm:w-auto' }">
        <template #left>
          <UTabs
            v-model="tab"
            :items="tabItems"
            :content="false"
            size="sm"
            variant="link"
            :aria-label="t('marketing.gallery.filterByStatus')"
          />
        </template>
        <template #right>
          <UInput
            v-model="search"
            icon="i-lucide-search"
            :placeholder="t('marketing.search')"
            :aria-label="t('marketing.search')"
            class="min-w-0 flex-1 sm:w-56 sm:flex-none"
          />
          <UTabs
            v-model="view"
            :items="viewItems"
            :content="false"
            size="sm"
            :aria-label="t('marketing.gallery.view')"
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

      <template v-if="view === 'galeria'">
        <div
          v-if="fetchStatus === 'pending' && !data"
          class="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6"
        >
          <USkeleton
            v-for="n in 8"
            :key="n"
            class="aspect-[9/16] w-full rounded-xl"
          />
        </div>
        <div
          v-else-if="!items.length"
          class="flex flex-col items-center gap-3 rounded-xl border border-dashed border-(--ui-border) p-10 text-center text-sm text-(--ui-text-muted)"
        >
          <UIcon
            name="i-lucide-clapperboard"
            class="size-8"
          />
          {{ debounced ? t('marketing.gallery.noResults') : t('marketing.gallery.empty') }}
        </div>
        <template v-else>
          <p class="text-sm text-(--ui-text-muted)">
            {{ t('marketing.gallery.count', items.length) }}<span class="hidden sm:inline"> · {{ t('marketing.gallery.hint') }}</span>
          </p>
          <div class="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6">
            <MarketingPieceCard
              v-for="item in items"
              :key="item.id"
              :item="item"
              @play="playing = $event"
            />
          </div>
          <div
            v-if="canLoadMore"
            class="flex justify-center"
          >
            <UButton
              color="neutral"
              variant="outline"
              :label="t('marketing.gallery.loadMore')"
              :loading="fetchStatus === 'pending'"
              @click="pages++"
            />
          </div>
        </template>
      </template>

      <template v-else>
        <div class="flex items-center gap-1">
          <UButton
            icon="i-lucide-chevron-left"
            color="neutral"
            variant="ghost"
            size="sm"
            :aria-label="t('marketing.previousMonth')"
            @click="month = shiftMonth(month, -1)"
          />
          <h2 class="min-w-40 text-center font-semibold capitalize">
            {{ monthLabel }}
          </h2>
          <UButton
            icon="i-lucide-chevron-right"
            color="neutral"
            variant="ghost"
            size="sm"
            :aria-label="t('marketing.nextMonth')"
            @click="month = shiftMonth(month, 1)"
          />
          <UButton
            v-if="month !== today.slice(0, 7)"
            color="neutral"
            variant="link"
            size="sm"
            :label="t('marketing.gallery.thisMonth')"
            @click="month = today.slice(0, 7)"
          />
        </div>
        <p
          v-if="fetchStatus !== 'pending' && !days.length"
          class="rounded-xl border border-dashed border-(--ui-border) p-6 text-center text-sm text-(--ui-text-muted)"
        >
          {{ t('marketing.emptyMonth') }}
        </p>
        <section
          v-for="[day, dayItems] in days"
          :key="day"
          class="space-y-3"
        >
          <h3
            class="text-sm font-semibold capitalize"
            :class="day === today ? 'text-(--ui-primary)' : ''"
          >
            {{ dayLabel(day) }}
            <span
              v-if="day === today"
              class="text-xs font-normal"
            > · {{ t('marketing.today') }}</span>
          </h3>
          <div class="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6">
            <MarketingPieceCard
              v-for="item in dayItems"
              :key="item.id"
              :item="item"
              @play="playing = $event"
            />
          </div>
        </section>
        <p class="text-xs text-(--ui-text-muted)">
          {{ t('marketing.gallery.calendarHelp') }}
        </p>
      </template>

      <MarketingPreviewModal
        v-model="playing"
        :items="view === 'galeria' ? items : days.flatMap(([, list]) => list)"
      />

      <UModal
        v-model:open="creating"
        :title="t('marketing.new')"
      >
        <template #body>
          <form
            id="content-form"
            class="space-y-4"
            @submit.prevent="create"
          >
            <UFormField
              :label="t('marketing.fields.title')"
              required
            >
              <UInput
                v-model="form.title"
                :maxlength="120"
                class="w-full"
                autofocus
              />
            </UFormField>
            <div class="grid gap-4 sm:grid-cols-2">
              <UFormField
                :label="t('marketing.fields.pillar')"
                :help="t('marketing.fields.pillarHelp')"
              >
                <UInput
                  v-model="form.pillar"
                  :maxlength="40"
                  class="w-full"
                />
              </UFormField>
              <UFormField
                :label="t('marketing.fields.format')"
                :help="t('marketing.fields.formatHelp')"
              >
                <UInput
                  v-model="form.format"
                  :maxlength="40"
                  class="w-full"
                />
              </UFormField>
              <UFormField :label="t('marketing.fields.audience')">
                <USelect
                  v-model="form.audience"
                  :items="audienceItems"
                  class="w-full"
                />
              </UFormField>
              <UFormField :label="t('marketing.fields.production')">
                <USelect
                  v-model="form.production"
                  :items="productionItems"
                  class="w-full"
                />
              </UFormField>
              <UFormField
                :label="t('marketing.fields.scheduledFor')"
                :help="t('marketing.fields.scheduledForHelp')"
              >
                <UInput
                  v-model="form.scheduled_for"
                  type="date"
                  class="w-full"
                />
              </UFormField>
            </div>
            <USwitch
              v-model="form.uses_character"
              :label="t('marketing.fields.usesCharacter')"
            />
            <UFormField :label="t('marketing.fields.notes')">
              <UTextarea
                v-model="form.notes"
                :rows="3"
                :maxlength="4000"
                class="w-full"
              />
            </UFormField>
          </form>
        </template>
        <template #footer>
          <div class="flex w-full justify-end gap-2">
            <UButton
              color="neutral"
              variant="ghost"
              :label="t('common.cancel')"
              @click="creating = false"
            />
            <UButton
              type="submit"
              form="content-form"
              icon="i-lucide-plus"
              :label="t('marketing.create')"
              :loading="saving"
              :disabled="!form.title.trim()"
            />
          </div>
        </template>
      </UModal>
    </template>
  </UDashboardPanel>
</template>
