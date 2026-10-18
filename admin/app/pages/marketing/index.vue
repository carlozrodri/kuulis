<script setup lang="ts">
import type { MarketingAudience, MarketingContent, MarketingContentSummary, MarketingProduction, MarketingStatus, Page } from '~/types/api'
import { MARKETING_AUDIENCES, MARKETING_PRODUCTIONS, MARKETING_STATUSES } from '~/types/api'

definePageMeta({ permission: 'marketing.view' })

const { t, locale } = useI18n()
const { request } = useApi()
const auth = useAuth()
const toast = useToast()
const apiError = useApiError()
const route = useRoute()
const router = useRouter()

// Month and filters in the URL, so "back" from a piece returns to the same view.
const today = caracasToday()
const initialMonth = typeof route.query.month === 'string' && /^\d{4}-\d{2}$/.test(route.query.month) ? route.query.month : today.slice(0, 7)
const month = ref(initialMonth)
type StatusFilter = MarketingStatus | 'all'
const initialStatus = (typeof route.query.status === 'string' ? route.query.status : 'all') as StatusFilter
const status = ref<StatusFilter>(['all', ...MARKETING_STATUSES].includes(initialStatus) ? initialStatus : 'all')
const search = ref(typeof route.query.q === 'string' ? route.query.q : '')
const debounced = ref(search.value.trim())
let timer: ReturnType<typeof setTimeout> | undefined
watch(search, (value) => {
  clearTimeout(timer)
  timer = setTimeout(() => (debounced.value = value.trim()), 300)
})
watch([month, status, debounced], () => {
  router.replace({
    query: {
      ...(month.value !== today.slice(0, 7) ? { month: month.value } : {}),
      ...(status.value !== 'all' ? { status: status.value } : {}),
      ...(debounced.value ? { q: debounced.value } : {}),
    },
  })
})

const filters = computed(() => ({
  ...(status.value !== 'all' ? { status: status.value } : {}),
  ...(debounced.value ? { q: debounced.value } : {}),
}))
const monthQuery = computed(() => ({
  limit: 100,
  from: `${month.value}-01`,
  to: endOfMonth(`${month.value}-01`),
  ...filters.value,
}))

const { data, status: fetchStatus, error, refresh } = await useAsyncData(
  'marketing-calendar',
  () => request<Page<MarketingContentSummary>>('/admin/marketing/contents', { query: monthQuery.value }),
  { watch: [monthQuery] },
)
// Pieces without a date (ideas, scripts) sort first in the API; the newest 100 cover the backlog.
const { data: backlog, refresh: refreshBacklog } = await useAsyncData(
  'marketing-backlog',
  () => request<Page<MarketingContentSummary>>('/admin/marketing/contents', { query: { limit: 100, ...filters.value } }),
  { watch: [filters] },
)
const unscheduled = computed(() => (backlog.value?.items ?? []).filter(c => !c.scheduled_for))

const days = computed(() => {
  const groups = new Map<string, MarketingContentSummary[]>()
  for (const item of data.value?.items ?? []) {
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

const statusItems = computed(() => [
  { label: t('marketing.allStatuses'), value: 'all' },
  ...MARKETING_STATUSES.map(value => ({ label: t(`marketing.statuses.${value}`), value })),
])

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
  await Promise.all([refresh(), refreshBacklog()])
}
</script>

<template>
  <UDashboardPanel id="marketing-calendar">
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
      <UDashboardToolbar>
        <template #left>
          <div class="flex items-center gap-1">
            <UButton
              icon="i-lucide-chevron-left"
              color="neutral"
              variant="ghost"
              size="sm"
              :aria-label="t('marketing.previousMonth')"
              @click="month = shiftMonth(month, -1)"
            />
            <span class="min-w-36 text-center text-sm font-medium capitalize">{{ monthLabel }}</span>
            <UButton
              icon="i-lucide-chevron-right"
              color="neutral"
              variant="ghost"
              size="sm"
              :aria-label="t('marketing.nextMonth')"
              @click="month = shiftMonth(month, 1)"
            />
          </div>
        </template>
        <template #right>
          <USelect
            v-model="status"
            :items="statusItems"
            class="w-40"
          />
          <UInput
            v-model="search"
            icon="i-lucide-search"
            :placeholder="t('marketing.search')"
            class="w-56 max-w-full"
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

      <div class="grid gap-6 lg:grid-cols-[1fr_20rem]">
        <section class="space-y-4">
          <p
            v-if="fetchStatus !== 'pending' && !days.length"
            class="rounded-lg border border-dashed border-(--ui-border) p-6 text-center text-sm text-(--ui-text-muted)"
          >
            {{ t('marketing.emptyMonth') }}
          </p>
          <div
            v-for="[day, items] in days"
            :key="day"
            class="space-y-2"
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
            <MarketingContentRow
              v-for="item in items"
              :key="item.id"
              :item="item"
            />
          </div>
        </section>

        <aside class="space-y-2">
          <h3 class="text-sm font-semibold">
            {{ t('marketing.unscheduled') }}
            <span class="font-normal text-(--ui-text-muted)">({{ unscheduled.length }})</span>
          </h3>
          <p
            v-if="!unscheduled.length"
            class="text-sm text-(--ui-text-muted)"
          >
            {{ t('common.empty') }}
          </p>
          <MarketingContentRow
            v-for="item in unscheduled"
            :key="item.id"
            :item="item"
            compact
          />
        </aside>
      </div>

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
