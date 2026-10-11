<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { RolesOverview, StaffMember } from '~/types/api'

definePageMeta({ roles: ['admin'] })

const { t, locale } = useI18n()
const { request } = useApi()
const auth = useAuth()
const apiError = useApiError()
const toast = useToast()

const { data: members, status, error, refresh } = await useAsyncData('team', () => request<StaffMember[]>('/admin/staff'))
const { data: overview } = await useAsyncData('team-roles', () => request<RolesOverview>('/admin/roles'))

const roleItems = computed(() => [
  { label: t('team.admin'), value: 'admin' },
  ...(overview.value?.roles ?? []).map(r => ({ label: r.label, value: r.id })),
])
const roleValue = (m: StaffMember) => (m.role === 'admin' ? 'admin' : m.staff_role_id ?? '')

const busy = ref<string | null>(null)
async function update(member: StaffMember, body: Record<string, unknown>) {
  busy.value = member.id
  try {
    await request(`/admin/staff/${member.id}`, { method: 'PATCH', body })
    toast.add({ title: t('team.saved'), color: 'success' })
    await refresh()
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    busy.value = null
  }
}
function changeRole(member: StaffMember, value: string) {
  if (value === roleValue(member)) return
  return update(member, value === 'admin' ? { role: 'admin' } : { role: 'staff', staff_role_id: value })
}

const columns = computed<TableColumn<StaffMember>[]>(() => [
  { id: 'person', header: t('team.person') },
  { id: 'role', header: t('team.role') },
  { id: 'totp', header: t('team.totp') },
  { accessorKey: 'last_login_at', header: t('team.lastLogin') },
  { id: 'actions', header: '' },
])

// ---- Invite -----------------------------------------------------------------------------------
const inviteOpen = ref(false)
const inviting = ref(false)
const invite = reactive({ email: '', full_name: '', staff_role_id: '' })
const staffRoleItems = computed(() => (overview.value?.roles ?? []).map(r => ({ label: r.label, value: r.id })))
watch(inviteOpen, (open) => {
  if (open) Object.assign(invite, { email: '', full_name: '', staff_role_id: staffRoleItems.value[0]?.value ?? '' })
})
async function sendInvite() {
  inviting.value = true
  try {
    await request('/admin/staff/invite', { method: 'POST', body: { ...invite, locale: locale.value } })
    toast.add({ title: t('team.invited', { email: invite.email }), color: 'success' })
    inviteOpen.value = false
    await refresh()
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    inviting.value = false
  }
}
function resend(member: StaffMember) {
  Object.assign(invite, { email: member.email, full_name: member.full_name, staff_role_id: member.staff_role_id ?? '' })
  return sendInvite()
}
</script>

<template>
  <UDashboardPanel id="team">
    <template #header>
      <UDashboardNavbar :title="t('nav.team')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton
            icon="i-lucide-user-plus"
            :label="t('team.invite')"
            @click="inviteOpen = true"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <p class="text-sm text-(--ui-text-muted)">
        {{ t('team.help') }}
      </p>
      <UAlert
        v-if="error"
        color="error"
        variant="subtle"
        icon="i-lucide-circle-alert"
        :title="apiError(error)"
      />
      <UTable
        :data="members ?? []"
        :columns="columns"
        :loading="status === 'pending'"
        :empty="t('common.empty')"
      >
        <template #person-cell="{ row }">
          <div :class="row.original.is_active ? '' : 'opacity-60'">
            <p class="font-medium">
              {{ row.original.full_name || row.original.email }}
            </p>
            <p class="text-xs text-(--ui-text-muted)">
              {{ row.original.email }}
            </p>
            <div class="mt-1 flex gap-1">
              <UBadge
                v-if="!row.original.is_active"
                color="neutral"
                variant="subtle"
                size="sm"
              >
                {{ t('team.inactive') }}
              </UBadge>
              <UBadge
                v-if="row.original.invite_pending"
                color="warning"
                variant="subtle"
                size="sm"
              >
                {{ t('team.invitePending') }}
              </UBadge>
            </div>
          </div>
        </template>
        <template #role-cell="{ row }">
          <USelect
            :model-value="roleValue(row.original)"
            :items="roleItems"
            :placeholder="t('team.noRole')"
            :disabled="busy === row.original.id || row.original.id === auth.user.value?.id"
            class="w-44"
            @update:model-value="(v) => changeRole(row.original, v as string)"
          />
        </template>
        <template #totp-cell="{ row }">
          <UBadge
            :color="row.original.totp_enabled ? 'success' : 'warning'"
            variant="subtle"
            size="sm"
          >
            {{ row.original.totp_enabled ? t('team.totpOn') : t('team.totpOff') }}
          </UBadge>
        </template>
        <template #last_login_at-cell="{ row }">
          <span class="whitespace-nowrap">{{ row.original.last_login_at ? formatDate(row.original.last_login_at, locale) : t('team.never') }}</span>
        </template>
        <template #actions-cell="{ row }">
          <div
            v-if="row.original.id !== auth.user.value?.id"
            class="flex justify-end gap-1"
          >
            <UButton
              v-if="row.original.invite_pending && row.original.is_active"
              :label="t('team.resend')"
              color="neutral"
              variant="ghost"
              size="sm"
              :loading="inviting"
              @click="resend(row.original)"
            />
            <UButton
              :label="row.original.is_active ? t('team.deactivate') : t('team.activate')"
              :color="row.original.is_active ? 'error' : 'neutral'"
              variant="ghost"
              size="sm"
              :loading="busy === row.original.id"
              @click="update(row.original, { is_active: !row.original.is_active })"
            />
          </div>
        </template>
      </UTable>

      <UModal
        v-model:open="inviteOpen"
        :title="t('team.invite')"
        :description="t('team.inviteHelp')"
      >
        <template #body>
          <form
            id="invite-form"
            class="space-y-4"
            @submit.prevent="sendInvite"
          >
            <UFormField
              :label="t('team.name')"
              required
            >
              <UInput
                v-model="invite.full_name"
                class="w-full"
                required
                minlength="2"
              />
            </UFormField>
            <UFormField
              :label="t('team.email')"
              required
            >
              <UInput
                v-model="invite.email"
                type="email"
                class="w-full"
                required
              />
            </UFormField>
            <UFormField
              :label="t('team.role')"
              required
            >
              <USelect
                v-model="invite.staff_role_id"
                :items="staffRoleItems"
                class="w-full"
              />
            </UFormField>
          </form>
        </template>
        <template #footer>
          <UButton
            type="submit"
            form="invite-form"
            :label="t('team.send')"
            :loading="inviting"
            :disabled="!invite.staff_role_id"
          />
        </template>
      </UModal>
    </template>
  </UDashboardPanel>
</template>
