<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { AppConfig, CurrentRates, ExchangeRate, Page, RateHistoryEntry, RateSource } from '~/types/api'
import { RATE_SOURCES } from '~/types/api'

const { t, locale } = useI18n()
const { request } = useApi()
const auth = useAuth()
const toast = useToast()
const apiError = useApiError()

const readOnly = computed(() => !auth.isAdmin.value)

// ---- Current rates --------------------------------------------------------------------------

const { data: rates, status: ratesStatus, error: ratesError, refresh: refreshRates } = await useAsyncData(
  'rates-current',
  () => request<CurrentRates>('/rates'),
)

// Only needed for the stale thresholds and the manual hold window; defaults from the contract otherwise.
const { data: config } = await useAsyncData('rates-config', () => request<AppConfig>('/admin/config').catch(() => null))
const holdHours = computed(() => config.value?.rates_manual_hold_hours ?? 6)
const staleMinutes = (source: RateSource) => config.value?.rates_stale_minutes?.[source] ?? (source === 'bcv' ? 2160 : 120)

const cards = computed(() => RATE_SOURCES.map(source => ({ source, rate: rates.value?.[source] ?? null })))

// ---- History --------------------------------------------------------------------------------

type SourceFilter = RateSource | 'all'
const sourceFilter = ref<SourceFilter>('all')
const page = ref(1)
const limit = 25

watch(sourceFilter, () => {
  page.value = 1
})

const historyQuery = computed(() => ({
  limit,
  offset: (page.value - 1) * limit,
  ...(sourceFilter.value !== 'all' ? { source: sourceFilter.value } : {}),
}))

const { data: history, status: historyStatus, error: historyError, refresh: refreshHistory } = await useAsyncData(
  'rates-history',
  () => request<Page<RateHistoryEntry>>('/admin/rates/history', { query: historyQuery.value }),
  { watch: [historyQuery] },
)

const sourceItems = computed(() => [
  { label: t('rates.allSources'), value: 'all' },
  ...RATE_SOURCES.map(s => ({ label: t(`rates.sources.${s}`), value: s })),
])

const columns = computed<TableColumn<RateHistoryEntry>[]>(() => [
  { accessorKey: 'fetched_at', header: t('rates.fetchedAt') },
  { accessorKey: 'source', header: t('rates.source') },
  { accessorKey: 'rate', header: t('rates.rate') },
  { accessorKey: 'origin', header: t('rates.origin') },
  { accessorKey: 'as_of', header: t('rates.asOf') },
  { id: 'created_by', header: t('rates.createdBy') },
  { accessorKey: 'note', header: t('rates.note') },
])

// ---- Admin actions --------------------------------------------------------------------------

const refreshing = ref(false)
async function fetchNow() {
  refreshing.value = true
  try {
    rates.value = await request<CurrentRates>('/admin/rates/refresh', { method: 'POST', body: {} })
    toast.add({ title: t('rates.refreshed'), color: 'success' })
    await refreshHistory()
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    refreshing.value = false
  }
}

const manual = reactive<{ source: RateSource, rate: number | null, note: string }>({ source: 'bcv', rate: null, note: '' })
const manualValid = computed(() => manual.rate !== null && manual.rate > 0)
const saving = ref(false)

/** Pre-fills the form with the current value of the chosen source, as a starting point. */
function prefill(source: RateSource) {
  const current = Number(rates.value?.[source]?.rate)
  manual.rate = Number.isFinite(current) && current > 0 ? current : null
}
watch(() => manual.source, prefill)
watch(rates, () => {
  if (manual.rate === null) prefill(manual.source)
}, { immediate: true })

async function saveManual() {
  if (!manualValid.value || manual.rate === null) return
  saving.value = true
  try {
    const note = manual.note.trim()
    const saved = await request<ExchangeRate>('/admin/rates', {
      method: 'POST',
      body: { source: manual.source, rate: manual.rate.toFixed(2), ...(note ? { note } : {}) },
    })
    if (rates.value) rates.value = { ...rates.value, [saved.source]: saved }
    else await refreshRates()
    manual.note = ''
    toast.add({ title: t('rates.manual.saved'), color: 'success' })
    await refreshHistory()
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    saving.value = false
  }
}

const rateFormat = { minimumFractionDigits: 2, maximumFractionDigits: 2 }
</script>

<template>
  <UDashboardPanel id="rates">
    <template #header>
      <UDashboardNavbar :title="t('nav.rates')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton
            v-if="!readOnly"
            icon="i-lucide-refresh-cw"
            color="neutral"
            variant="outline"
            :label="t('rates.fetchNow')"
            :loading="refreshing"
            @click="fetchNow"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <UAlert
        v-if="readOnly"
        color="neutral"
        variant="subtle"
        icon="i-lucide-lock"
        :title="t('rates.readOnly')"
      />
      <UAlert
        v-if="ratesError && !rates"
        color="error"
        variant="subtle"
        icon="i-lucide-circle-alert"
        :title="apiError(ratesError)"
      />

      <div class="grid gap-6 xl:grid-cols-3">
        <div
          class="grid content-start gap-6 sm:grid-cols-2"
          :class="readOnly ? 'xl:col-span-3' : 'xl:col-span-2'"
        >
          <UCard
            v-for="card in cards"
            :key="card.source"
          >
            <template #header>
              <div class="flex items-center justify-between gap-2">
                <h2 class="font-semibold">
                  {{ t(`rates.sources.${card.source}`) }}
                </h2>
                <UBadge
                  v-if="card.rate"
                  :color="rateOriginColor[card.rate.origin]"
                  variant="subtle"
                  size="sm"
                >
                  {{ t(`rates.origins.${card.rate.origin}`) }}
                </UBadge>
              </div>
            </template>

            <USkeleton
              v-if="ratesStatus === 'pending' && !rates"
              class="h-24"
            />
            <p
              v-else-if="!card.rate"
              class="text-sm text-(--ui-text-muted)"
            >
              {{ t('rates.noRate') }}
            </p>
            <div
              v-else
              class="space-y-4"
            >
              <p class="text-3xl font-semibold tabular-nums">
                {{ formatRate(card.rate.rate, locale) }}
                <span class="text-base font-normal text-(--ui-text-muted)">{{ t('rates.unit') }}</span>
              </p>
              <UAlert
                v-if="card.rate.stale"
                color="warning"
                variant="subtle"
                icon="i-lucide-triangle-alert"
                :title="t('rates.stale')"
                :description="t('rates.staleHelp', { age: formatMinutes(staleMinutes(card.source)) })"
              />
              <dl class="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <dt class="text-(--ui-text-muted)">
                    {{ t('rates.asOf') }}
                  </dt>
                  <dd>{{ formatDate(card.rate.as_of, locale) }}</dd>
                </div>
                <div>
                  <dt class="text-(--ui-text-muted)">
                    {{ t('rates.fetchedAt') }}
                  </dt>
                  <dd>
                    {{ formatDate(card.rate.fetched_at, locale) }}
                    <span class="block text-xs text-(--ui-text-muted)">{{ formatAgo(card.rate.fetched_at, locale) }}</span>
                  </dd>
                </div>
              </dl>
            </div>
          </UCard>
        </div>

        <UCard v-if="!readOnly">
          <template #header>
            <h2 class="font-semibold">
              {{ t('rates.manual.title') }}
            </h2>
            <p class="text-sm text-(--ui-text-muted)">
              {{ t('rates.manual.help', { n: holdHours }) }}
            </p>
          </template>
          <form
            class="space-y-4"
            @submit.prevent="saveManual"
          >
            <UFormField
              :label="t('rates.source')"
              required
            >
              <USelect
                v-model="manual.source"
                :items="RATE_SOURCES.map(s => ({ label: t(`rates.sources.${s}`), value: s }))"
                class="w-full"
              />
            </UFormField>
            <UFormField
              :label="t('rates.manual.rate')"
              :help="t('rates.unit')"
              required
            >
              <UInputNumber
                v-model="manual.rate"
                :min="0.01"
                :step="0.01"
                :format-options="rateFormat"
                class="w-full"
              />
            </UFormField>
            <UFormField :label="t('rates.manual.note')">
              <UTextarea
                v-model="manual.note"
                :rows="2"
                maxlength="300"
                :placeholder="t('rates.manual.notePlaceholder')"
                class="w-full"
              />
            </UFormField>
            <UButton
              type="submit"
              icon="i-lucide-pencil"
              :label="t('rates.manual.save')"
              :loading="saving"
              :disabled="!manualValid"
            />
          </form>
        </UCard>
      </div>

      <section class="space-y-3">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <h2 class="font-semibold">
            {{ t('rates.history') }}
          </h2>
          <USelect
            v-model="sourceFilter"
            :items="sourceItems"
            class="w-48"
            :aria-label="t('rates.source')"
          />
        </div>
        <UAlert
          v-if="historyError"
          color="error"
          variant="subtle"
          icon="i-lucide-circle-alert"
          :title="apiError(historyError)"
        />
        <UTable
          :data="history?.items ?? []"
          :columns="columns"
          :loading="historyStatus === 'pending'"
          :empty="t('common.empty')"
        >
          <template #fetched_at-cell="{ row }">
            <span class="whitespace-nowrap">{{ formatDate(row.original.fetched_at, locale) }}</span>
          </template>
          <template #source-cell="{ row }">
            {{ t(`rates.sources.${row.original.source}`, row.original.source) }}
          </template>
          <template #rate-cell="{ row }">
            <span class="font-medium tabular-nums">{{ formatRate(row.original.rate, locale) }}</span>
          </template>
          <template #origin-cell="{ row }">
            <UBadge
              :color="rateOriginColor[row.original.origin] ?? 'neutral'"
              variant="subtle"
              size="sm"
            >
              {{ t(`rates.origins.${row.original.origin}`, row.original.origin) }}
            </UBadge>
          </template>
          <template #as_of-cell="{ row }">
            <span class="whitespace-nowrap">{{ formatDate(row.original.as_of, locale) }}</span>
          </template>
          <template #created_by-cell="{ row }">
            <NuxtLink
              v-if="row.original.created_by"
              :to="`/users/${row.original.created_by.id}`"
              class="text-primary hover:underline"
            >
              {{ row.original.created_by.name || row.original.created_by.id.slice(0, 8) }}
            </NuxtLink>
            <span
              v-else
              class="text-(--ui-text-muted)"
            >{{ t('rates.worker') }}</span>
          </template>
          <template #note-cell="{ row }">
            <span
              class="block max-w-xs truncate"
              :title="row.original.note ?? undefined"
            >{{ row.original.note || '—' }}</span>
          </template>
        </UTable>

        <div class="flex items-center justify-between border-t border-(--ui-border) pt-4">
          <span class="text-sm text-(--ui-text-muted)">
            {{ t('rates.total', { n: history?.total ?? 0 }) }}
          </span>
          <UPagination
            v-model:page="page"
            :total="history?.total ?? 0"
            :items-per-page="limit"
          />
        </div>
      </section>
    </template>
  </UDashboardPanel>
</template>
