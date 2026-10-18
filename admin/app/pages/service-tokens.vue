<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { RolesOverview, ServiceToken, ServiceTokenCreated, StaffMember } from '~/types/api'

definePageMeta({ roles: ['admin'] })

const { t, te, locale } = useI18n()
const { request } = useApi()
const apiError = useApiError()
const toast = useToast()

const { data: tokens, status, error, refresh } = await useAsyncData('service-tokens', () => request<ServiceToken[]>('/admin/service-tokens'))
const { data: members } = await useAsyncData('service-tokens-team', () => request<StaffMember[]>('/admin/staff'))
const { data: overview } = await useAsyncData('service-tokens-roles', () => request<RolesOverview>('/admin/roles'))

const permissionLabel = (key: string) => (te(`roles.permissions.${key}`) ? t(`roles.permissions.${key}`) : key)

function state(token: ServiceToken): 'revoked' | 'expired' | 'active' {
  if (token.revoked_at) return 'revoked'
  if (token.expires_at && new Date(token.expires_at) <= new Date()) return 'expired'
  return 'active'
}
const STATE_COLOR = { active: 'success', expired: 'warning', revoked: 'neutral' } as const

const columns = computed<TableColumn<ServiceToken>[]>(() => [
  { id: 'name', header: t('serviceTokens.name') },
  { id: 'account', header: t('serviceTokens.account') },
  { id: 'permissions', header: t('serviceTokens.permissions') },
  { id: 'used', header: t('serviceTokens.lastUsed') },
  { id: 'expires', header: t('serviceTokens.expires') },
  { id: 'actions', header: '' },
])

// ---- Create -----------------------------------------------------------------------------------
// Tokens act as a staff account (never an admin) and can only carry what that account's role has.
const accounts = computed(() => (members.value ?? []).filter(m => m.role === 'staff' && m.is_active && m.staff_role_id))
const accountItems = computed(() => accounts.value.map(m => ({ label: `${m.full_name || m.email} · ${m.staff_role_label ?? ''}`, value: m.id })))

const createOpen = ref(false)
const creating = ref(false)
const form = reactive({ name: '', user_id: '', permissions: [] as string[], expires_on: '' })
const available = computed(() => {
  const member = accounts.value.find(m => m.id === form.user_id)
  const role = overview.value?.roles.find(r => r.id === member?.staff_role_id)
  return role?.permissions ?? []
})
watch(createOpen, (open) => {
  if (open) Object.assign(form, { name: '', user_id: accountItems.value[0]?.value ?? '', permissions: [], expires_on: '' })
})
watch(() => form.user_id, () => {
  form.permissions = form.permissions.filter(p => available.value.includes(p))
})
function toggle(permission: string, on: boolean | 'indeterminate') {
  form.permissions = on === true
    ? [...new Set([...form.permissions, permission])]
    : form.permissions.filter(p => p !== permission)
}

const created = ref<ServiceTokenCreated | null>(null)
async function create() {
  creating.value = true
  try {
    created.value = await request<ServiceTokenCreated>('/admin/service-tokens', {
      method: 'POST',
      body: {
        name: form.name,
        user_id: form.user_id,
        permissions: form.permissions,
        // End of the chosen day, in the browser's time zone.
        expires_at: form.expires_on ? new Date(`${form.expires_on}T23:59:59`).toISOString() : null,
      },
    })
    createOpen.value = false
    await refresh()
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    creating.value = false
  }
}
async function copy() {
  if (!created.value) return
  await navigator.clipboard.writeText(created.value.token)
  toast.add({ title: t('serviceTokens.copied'), color: 'success' })
}

// ---- Revoke -----------------------------------------------------------------------------------
const revoking = ref<ServiceToken | null>(null)
const busy = ref(false)
async function revoke() {
  if (!revoking.value) return
  busy.value = true
  try {
    await request(`/admin/service-tokens/${revoking.value.id}/revoke`, { method: 'POST' })
    toast.add({ title: t('serviceTokens.revoked'), color: 'success' })
    revoking.value = null
    await refresh()
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    busy.value = false
  }
}
</script>

<template>
  <UDashboardPanel id="service-tokens">
    <template #header>
      <UDashboardNavbar :title="t('nav.serviceTokens')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton
            icon="i-lucide-plus"
            :label="t('serviceTokens.create')"
            @click="createOpen = true"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <p class="text-sm text-(--ui-text-muted)">
        {{ t('serviceTokens.help') }}
      </p>
      <UAlert
        v-if="error"
        color="error"
        variant="subtle"
        icon="i-lucide-circle-alert"
        :title="apiError(error)"
      />
      <UTable
        :data="tokens ?? []"
        :columns="columns"
        :loading="status === 'pending'"
        :empty="t('serviceTokens.empty')"
      >
        <template #name-cell="{ row }">
          <div :class="state(row.original) === 'active' ? '' : 'opacity-60'">
            <p class="font-medium">
              {{ row.original.name }}
            </p>
            <p class="font-mono text-xs text-(--ui-text-muted)">
              {{ row.original.prefix }}…
            </p>
            <UBadge
              :color="STATE_COLOR[state(row.original)]"
              variant="subtle"
              size="sm"
              class="mt-1"
            >
              {{ t(`serviceTokens.states.${state(row.original)}`) }}
            </UBadge>
          </div>
        </template>
        <template #account-cell="{ row }">
          <p>{{ row.original.user_name || row.original.user_email }}</p>
          <p class="text-xs text-(--ui-text-muted)">
            {{ row.original.user_email }}
          </p>
        </template>
        <template #permissions-cell="{ row }">
          <div class="flex max-w-xs flex-wrap gap-1">
            <UBadge
              v-for="p in row.original.permissions"
              :key="p"
              color="neutral"
              variant="outline"
              size="sm"
            >
              {{ permissionLabel(p) }}
            </UBadge>
          </div>
        </template>
        <template #used-cell="{ row }">
          <span class="whitespace-nowrap">{{ row.original.last_used_at ? formatDate(row.original.last_used_at, locale) : t('serviceTokens.never') }}</span>
        </template>
        <template #expires-cell="{ row }">
          <span class="whitespace-nowrap">{{ row.original.expires_at ? formatDate(row.original.expires_at, locale) : t('serviceTokens.noExpiry') }}</span>
        </template>
        <template #actions-cell="{ row }">
          <div class="flex justify-end">
            <UButton
              v-if="!row.original.revoked_at"
              :label="t('serviceTokens.revoke')"
              color="error"
              variant="ghost"
              size="sm"
              @click="revoking = row.original"
            />
          </div>
        </template>
      </UTable>

      <UModal
        v-model:open="createOpen"
        :title="t('serviceTokens.create')"
        :description="t('serviceTokens.createHelp')"
      >
        <template #body>
          <UAlert
            v-if="!accountItems.length"
            color="warning"
            variant="subtle"
            icon="i-lucide-info"
            :title="t('serviceTokens.noAccounts')"
          />
          <form
            v-else
            id="token-form"
            class="space-y-4"
            @submit.prevent="create"
          >
            <UFormField
              :label="t('serviceTokens.name')"
              required
            >
              <UInput
                v-model="form.name"
                class="w-full"
                required
                minlength="2"
                maxlength="80"
                :placeholder="t('serviceTokens.namePlaceholder')"
              />
            </UFormField>
            <UFormField
              :label="t('serviceTokens.account')"
              :help="t('serviceTokens.accountHelp')"
              required
            >
              <USelect
                v-model="form.user_id"
                :items="accountItems"
                class="w-full"
              />
            </UFormField>
            <UFormField
              :label="t('serviceTokens.permissions')"
              :help="t('serviceTokens.permissionsHelp')"
              required
            >
              <div class="grid gap-2 sm:grid-cols-2">
                <UCheckbox
                  v-for="p in available"
                  :key="p"
                  :model-value="form.permissions.includes(p)"
                  :label="permissionLabel(p)"
                  @update:model-value="(v) => toggle(p, v)"
                />
              </div>
            </UFormField>
            <UFormField
              :label="t('serviceTokens.expires')"
              :help="t('serviceTokens.expiresHelp')"
            >
              <UInput
                v-model="form.expires_on"
                type="date"
                class="w-full"
              />
            </UFormField>
          </form>
        </template>
        <template #footer>
          <UButton
            type="submit"
            form="token-form"
            :label="t('serviceTokens.create')"
            :loading="creating"
            :disabled="!form.user_id || !form.permissions.length || form.name.trim().length < 2"
          />
        </template>
      </UModal>

      <UModal
        :open="!!created"
        :title="t('serviceTokens.createdTitle')"
        :dismissible="false"
        @update:open="(open) => { if (!open) created = null }"
      >
        <template #body>
          <div class="space-y-4">
            <UAlert
              color="warning"
              variant="subtle"
              icon="i-lucide-triangle-alert"
              :title="t('serviceTokens.onceTitle')"
              :description="t('serviceTokens.onceHelp')"
            />
            <div class="flex items-center gap-2">
              <code class="flex-1 break-all rounded bg-(--ui-bg-elevated) p-2 font-mono text-xs">{{ created?.token }}</code>
              <UButton
                icon="i-lucide-copy"
                color="neutral"
                variant="outline"
                :aria-label="t('serviceTokens.copy')"
                @click="copy"
              />
            </div>
          </div>
        </template>
        <template #footer>
          <div class="flex w-full justify-end">
            <UButton
              :label="t('serviceTokens.done')"
              @click="created = null"
            />
          </div>
        </template>
      </UModal>

      <UModal
        :open="!!revoking"
        :title="t('serviceTokens.revokeTitle')"
        :description="t('serviceTokens.revokeHelp', { name: revoking?.name ?? '' })"
        @update:open="(open) => { if (!open) revoking = null }"
      >
        <template #footer>
          <div class="flex w-full justify-end gap-2">
            <UButton
              color="neutral"
              variant="ghost"
              :label="t('common.cancel')"
              @click="revoking = null"
            />
            <UButton
              color="error"
              :label="t('serviceTokens.revoke')"
              :loading="busy"
              @click="revoke"
            />
          </div>
        </template>
      </UModal>
    </template>
  </UDashboardPanel>
</template>
