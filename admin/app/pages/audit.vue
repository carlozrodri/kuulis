<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { AuditEntry, Page } from '~/types/api'

definePageMeta({ roles: ['admin'] })

const { t, te, locale } = useI18n()
const { request, download } = useApi()
const route = useRoute()
const router = useRouter()
const apiError = useApiError()
const toast = useToast()

const queryString = (key: string) => (typeof route.query[key] === 'string' ? route.query[key] as string : '')
const filters = reactive({
  action: queryString('action'),
  entity_type: queryString('entity_type') || 'all',
  entity_id: queryString('entity_id'),
  actor_id: queryString('actor_id'),
  from: queryString('from'),
  to: queryString('to'),
})
const page = ref(Math.max(1, Number(queryString('page')) || 1))
const limit = 50

// Text filters wait for the typing to stop.
const debounced = ref({ ...filters })
let timer: ReturnType<typeof setTimeout> | undefined
watch(filters, () => {
  clearTimeout(timer)
  timer = setTimeout(() => {
    debounced.value = { ...filters, action: filters.action.trim(), entity_id: filters.entity_id.trim() }
    page.value = 1
  }, 300)
})

const apiFilters = computed(() => {
  const f = debounced.value
  const out: Record<string, string> = {}
  if (f.action) out.action = f.action
  if (f.entity_type !== 'all') out.entity_type = f.entity_type
  if (f.entity_id) out.entity_id = f.entity_id
  if (f.actor_id) out.actor_id = f.actor_id
  if (f.from) out.from = f.from
  if (f.to) out.to = f.to
  return out
})
watch([apiFilters, page], () => {
  router.replace({ query: { ...apiFilters.value, ...(page.value > 1 ? { page: String(page.value) } : {}) } })
})

const query = computed(() => ({ ...apiFilters.value, limit, offset: (page.value - 1) * limit }))
const { data, status, error } = await useAsyncData(
  'audit',
  () => request<Page<AuditEntry>>('/admin/audit', { query: query.value }),
  { watch: [query] },
)

const entityItems = computed(() => [
  { label: t('audit.allEntities'), value: 'all' },
  ...AUDIT_ENTITY_TYPES.map(value => ({ label: t(`audit.entities.${value}`), value })),
])
const actionLabel = (action: string) => (te(`audit.actions.${action}`) ? t(`audit.actions.${action}`) : action)

const columns = computed<TableColumn<AuditEntry>[]>(() => [
  { accessorKey: 'created_at', header: t('audit.date') },
  { accessorKey: 'actor_email', header: t('audit.actor') },
  { accessorKey: 'action', header: t('audit.action') },
  { id: 'entity', header: t('audit.entity') },
  { accessorKey: 'reason', header: t('audit.reason') },
  { id: 'detail', header: '' },
])

const selected = ref<AuditEntry | null>(null)
const detailOpen = computed({
  get: () => selected.value !== null,
  set: (value: boolean) => {
    if (!value) selected.value = null
  },
})

function filterByActor(entry: AuditEntry) {
  if (entry.actor_id) filters.actor_id = entry.actor_id
}

const exporting = ref(false)
async function exportCsv() {
  exporting.value = true
  try {
    await download('/admin/audit/export.csv', 'kuulis-auditoria.csv', apiFilters.value)
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    exporting.value = false
  }
}
</script>

<template>
  <UDashboardPanel id="audit">
    <template #header>
      <UDashboardNavbar :title="t('nav.audit')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton
            icon="i-lucide-download"
            :label="t('audit.export')"
            color="neutral"
            variant="outline"
            :loading="exporting"
            @click="exportCsv"
          />
        </template>
      </UDashboardNavbar>
      <UDashboardToolbar>
        <template #left>
          <div class="flex flex-wrap items-center gap-2">
            <UInput
              v-model="filters.action"
              icon="i-lucide-search"
              :placeholder="t('audit.actionFilter')"
              class="w-48"
            />
            <USelect
              v-model="filters.entity_type"
              :items="entityItems"
              class="w-44"
            />
            <UInput
              v-model="filters.entity_id"
              :placeholder="t('audit.entityId')"
              class="w-72"
            />
            <UInput
              v-model="filters.from"
              type="date"
              :aria-label="t('audit.from')"
            />
            <UInput
              v-model="filters.to"
              type="date"
              :aria-label="t('audit.to')"
            />
            <UBadge
              v-if="filters.actor_id"
              color="neutral"
              variant="subtle"
              class="cursor-pointer"
              @click="filters.actor_id = ''"
            >
              {{ t('audit.byActor') }} ✕
            </UBadge>
          </div>
        </template>
      </UDashboardToolbar>
    </template>

    <template #body>
      <p class="text-sm text-(--ui-text-muted)">
        {{ t('audit.help') }}
      </p>
      <UAlert
        v-if="error"
        color="error"
        variant="subtle"
        icon="i-lucide-circle-alert"
        :title="apiError(error)"
      />
      <UTable
        :data="data?.items ?? []"
        :columns="columns"
        :loading="status === 'pending'"
        :empty="t('common.empty')"
      >
        <template #created_at-cell="{ row }">
          <span class="whitespace-nowrap">{{ formatDate(row.original.created_at, locale) }}</span>
        </template>
        <template #actor_email-cell="{ row }">
          <button
            v-if="row.original.actor_id"
            type="button"
            class="hover:underline"
            :title="t('audit.filterActor')"
            @click="filterByActor(row.original)"
          >
            {{ row.original.actor_email }}
          </button>
          <span v-else>{{ row.original.actor_email || t('audit.system') }}</span>
        </template>
        <template #action-cell="{ row }">
          <span :title="row.original.action">{{ actionLabel(row.original.action) }}</span>
        </template>
        <template #entity-cell="{ row }">
          <span class="whitespace-nowrap">{{ t(`audit.entities.${row.original.entity_type}`) }}</span>
          <NuxtLink
            v-if="auditEntityLink(row.original)"
            :to="auditEntityLink(row.original)!"
            class="ml-1 text-(--ui-primary) hover:underline"
          >
            {{ t('audit.open') }}
          </NuxtLink>
        </template>
        <template #reason-cell="{ row }">
          <span
            class="block max-w-xs truncate"
            :title="row.original.reason ?? undefined"
          >{{ row.original.reason || '—' }}</span>
        </template>
        <template #detail-cell="{ row }">
          <UButton
            icon="i-lucide-file-diff"
            :aria-label="t('audit.detail')"
            color="neutral"
            variant="ghost"
            size="sm"
            @click="selected = row.original"
          />
        </template>
      </UTable>

      <div class="flex items-center justify-between border-t border-(--ui-border) pt-4">
        <span class="text-sm text-(--ui-text-muted)">
          {{ t('audit.total', { n: data?.total ?? 0 }) }}
        </span>
        <UPagination
          v-model:page="page"
          :total="data?.total ?? 0"
          :items-per-page="limit"
        />
      </div>

      <UModal
        v-model:open="detailOpen"
        :title="selected ? actionLabel(selected.action) : ''"
        :description="selected ? `${selected.actor_email} · ${formatDate(selected.created_at, locale)}` : ''"
      >
        <template #body>
          <AuditDiff
            v-if="selected"
            :entry="selected"
          />
        </template>
      </UModal>
    </template>
  </UDashboardPanel>
</template>
