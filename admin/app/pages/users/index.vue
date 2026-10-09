<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { Page, Role, User } from '~/types/api'

const { t, locale } = useI18n()
const { request } = useApi()

const search = ref('')
const debouncedSearch = ref('')
let searchTimer: ReturnType<typeof setTimeout> | undefined
watch(search, (value) => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => (debouncedSearch.value = value), 300)
})
const role = ref<Role | 'all'>('all')
const page = ref(1)
const limit = 20

watch([debouncedSearch, role], () => {
  page.value = 1
})

const query = computed(() => ({
  limit,
  offset: (page.value - 1) * limit,
  ...(debouncedSearch.value ? { search: debouncedSearch.value } : {}),
  ...(role.value !== 'all' ? { role: role.value } : {}),
}))

const { data, status } = await useAsyncData(
  'users',
  () => request<Page<User>>('/users', { query: query.value }),
  { watch: [query] },
)

const roleItems = computed(() => [
  { label: t('users.allRoles'), value: 'all' },
  { label: t('roles.user'), value: 'user' },
  { label: t('roles.staff'), value: 'staff' },
  { label: t('roles.admin'), value: 'admin' },
])

const roleColor: Record<Role, 'neutral' | 'info' | 'primary'> = { user: 'neutral', staff: 'info', admin: 'primary' }

const columns = computed<TableColumn<User>[]>(() => [
  { accessorKey: 'email', header: t('users.email') },
  { accessorKey: 'full_name', header: t('users.name') },
  { accessorKey: 'role', header: t('users.role') },
  { accessorKey: 'is_active', header: t('users.status') },
  { accessorKey: 'created_at', header: t('users.createdAt') },
])
</script>

<template>
  <UDashboardPanel id="users">
    <template #header>
      <UDashboardNavbar :title="t('nav.users')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
      </UDashboardNavbar>
      <UDashboardToolbar>
        <UInput
          v-model="search"
          icon="i-lucide-search"
          :placeholder="t('users.search')"
          class="max-w-sm"
        />
        <USelect
          v-model="role"
          :items="roleItems"
          class="w-40"
        />
      </UDashboardToolbar>
    </template>

    <template #body>
      <UTable
        :data="data?.items ?? []"
        :columns="columns"
        :loading="status === 'pending'"
        :empty="t('common.empty')"
        @select="(_e: Event, row: { original: User }) => navigateTo(`/users/${row.original.id}`)"
      >
        <template #role-cell="{ row }">
          <UBadge
            :color="roleColor[row.original.role]"
            variant="subtle"
          >
            {{ t(`roles.${row.original.role}`) }}
          </UBadge>
        </template>
        <template #is_active-cell="{ row }">
          <UBadge
            :color="row.original.is_active ? 'success' : 'error'"
            variant="subtle"
          >
            {{ row.original.is_active ? t('users.active') : t('users.inactive') }}
          </UBadge>
        </template>
        <template #created_at-cell="{ row }">
          {{ formatDate(row.original.created_at, locale) }}
        </template>
      </UTable>

      <div class="flex justify-end border-t border-(--ui-border) pt-4">
        <UPagination
          v-model:page="page"
          :total="data?.total ?? 0"
          :items-per-page="limit"
        />
      </div>
    </template>
  </UDashboardPanel>
</template>
