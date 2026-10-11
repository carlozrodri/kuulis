<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { AdminDataExport, DeletionRequest, Page } from '~/types/api'

definePageMeta({ permission: 'users.view' })

const { t, locale } = useI18n()
const { request } = useApi()
const apiError = useApiError()

type Tab = 'deletions' | 'exports'
const tab = ref<Tab>('deletions')
const state = ref<'all' | 'scheduled' | 'erased'>('all')
const page = ref(1)
const limit = 25
watch([tab, state], () => (page.value = 1))

const query = computed(() => ({
  limit,
  offset: (page.value - 1) * limit,
  ...(tab.value === 'deletions' && state.value !== 'all' ? { state: state.value } : {}),
}))

const { data: deletions, status: deletionsStatus, error: deletionsError } = await useAsyncData(
  'privacy-deletions',
  () => (tab.value === 'deletions' ? request<Page<DeletionRequest>>('/admin/privacy/deletions', { query: query.value }) : Promise.resolve(null)),
  { watch: [query, tab] },
)
const { data: exports, status: exportsStatus, error: exportsError } = await useAsyncData(
  'privacy-exports',
  () => (tab.value === 'exports' ? request<Page<AdminDataExport>>('/admin/privacy/exports', { query: query.value }) : Promise.resolve(null)),
  { watch: [query, tab] },
)
const error = computed(() => (tab.value === 'deletions' ? deletionsError.value : exportsError.value))
const total = computed(() => (tab.value === 'deletions' ? deletions.value?.total : exports.value?.total) ?? 0)

const deletionColumns = computed<TableColumn<DeletionRequest>[]>(() => [
  { id: 'user', header: t('privacy.user') },
  { accessorKey: 'requested_at', header: t('privacy.requestedAt') },
  { id: 'state', header: t('privacy.state') },
])
const exportColumns = computed<TableColumn<AdminDataExport>[]>(() => [
  { id: 'user', header: t('privacy.user') },
  { accessorKey: 'created_at', header: t('privacy.requestedAt') },
  { accessorKey: 'status', header: t('privacy.state') },
])
const EXPORT_COLORS = { pending: 'neutral', ready: 'success', failed: 'error', expired: 'neutral' } as const
</script>

<template>
  <UDashboardPanel id="privacy">
    <template #header>
      <UDashboardNavbar :title="t('nav.privacy')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
      </UDashboardNavbar>
      <UDashboardToolbar>
        <template #left>
          <UTabs
            v-model="tab"
            :items="[{ label: t('privacy.deletions'), value: 'deletions' }, { label: t('privacy.exports'), value: 'exports' }]"
            :content="false"
            size="sm"
          />
        </template>
        <template #right>
          <USelect
            v-if="tab === 'deletions'"
            v-model="state"
            :items="[
              { label: t('privacy.states.all'), value: 'all' },
              { label: t('privacy.states.scheduled'), value: 'scheduled' },
              { label: t('privacy.states.erased'), value: 'erased' },
            ]"
            class="w-44"
          />
        </template>
      </UDashboardToolbar>
    </template>

    <template #body>
      <p class="text-sm text-(--ui-text-muted)">
        {{ tab === 'deletions' ? t('privacy.deletionsHelp') : t('privacy.exportsHelp') }}
      </p>
      <UAlert
        v-if="error"
        color="error"
        variant="subtle"
        icon="i-lucide-circle-alert"
        :title="apiError(error)"
      />
      <UTable
        v-if="tab === 'deletions'"
        :data="deletions?.items ?? []"
        :columns="deletionColumns"
        :loading="deletionsStatus === 'pending'"
        :empty="t('common.empty')"
      >
        <template #user-cell="{ row }">
          <NuxtLink
            :to="`/users/${row.original.user_id}`"
            class="hover:underline"
          >
            <span class="block font-medium">{{ row.original.full_name || '—' }}</span>
            <span class="block text-xs text-(--ui-text-muted)">{{ row.original.email }}</span>
          </NuxtLink>
        </template>
        <template #requested_at-cell="{ row }">
          <span class="whitespace-nowrap">{{ formatDate(row.original.requested_at, locale) }}</span>
        </template>
        <template #state-cell="{ row }">
          <UBadge
            v-if="row.original.erased_at"
            color="neutral"
            variant="subtle"
          >
            {{ t('privacy.erasedOn', { date: formatDate(row.original.erased_at, locale) }) }}
          </UBadge>
          <UBadge
            v-else
            color="warning"
            variant="subtle"
          >
            {{ t('privacy.eraseOn', { date: formatDate(row.original.erase_at, locale) }) }}
          </UBadge>
        </template>
      </UTable>
      <UTable
        v-else
        :data="exports?.items ?? []"
        :columns="exportColumns"
        :loading="exportsStatus === 'pending'"
        :empty="t('common.empty')"
      >
        <template #user-cell="{ row }">
          <NuxtLink
            :to="`/users/${row.original.user_id}`"
            class="hover:underline"
          >{{ row.original.email }}</NuxtLink>
        </template>
        <template #created_at-cell="{ row }">
          <span class="whitespace-nowrap">{{ formatDate(row.original.created_at, locale) }}</span>
        </template>
        <template #status-cell="{ row }">
          <UBadge
            :color="EXPORT_COLORS[row.original.status]"
            variant="subtle"
          >
            {{ t(`privacy.exportStatus.${row.original.status}`) }}
          </UBadge>
          <span
            v-if="row.original.error"
            class="ml-2 text-xs text-(--ui-text-muted)"
          >{{ row.original.error }}</span>
        </template>
      </UTable>

      <div class="flex items-center justify-between border-t border-(--ui-border) pt-4">
        <span class="text-sm text-(--ui-text-muted)">
          {{ t('privacy.total', { n: total }) }}
        </span>
        <UPagination
          v-model:page="page"
          :total="total"
          :items-per-page="limit"
        />
      </div>
    </template>
  </UDashboardPanel>
</template>
