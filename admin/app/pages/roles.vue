<script setup lang="ts">
import type { RolesOverview, StaffRole } from '~/types/api'

definePageMeta({ roles: ['admin'] })

const { t, te } = useI18n()
const { request } = useApi()
const apiError = useApiError()
const toast = useToast()

const { data, status, error, refresh } = await useAsyncData('roles', () => request<RolesOverview>('/admin/roles'))

// Edited permissions per role, saved one role at a time.
const draft = ref<Record<string, Set<string>>>({})
watch(data, (value) => {
  draft.value = Object.fromEntries((value?.roles ?? []).map(r => [r.id, new Set(r.permissions)]))
}, { immediate: true })

const dirty = (role: StaffRole) => {
  const current = draft.value[role.id]
  return !!current && (current.size !== role.permissions.length || role.permissions.some(p => !current.has(p)))
}
function toggle(role: StaffRole, permission: string, on: boolean) {
  const next = new Set(draft.value[role.id])
  if (on) next.add(permission)
  else next.delete(permission)
  draft.value = { ...draft.value, [role.id]: next }
}

const saving = ref<string | null>(null)
async function save(role: StaffRole) {
  saving.value = role.id
  try {
    await request(`/admin/roles/${role.id}`, { method: 'PUT', body: { permissions: [...draft.value[role.id] ?? []] } })
    toast.add({ title: t('roles.saved', { role: role.label }), color: 'success' })
    await refresh()
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    saving.value = null
  }
}

const permissionLabel = (key: string) => (te(`roles.permissions.${key}`) ? t(`roles.permissions.${key}`) : key)

// ---- New role ---------------------------------------------------------------------------------
const createOpen = ref(false)
const creating = ref(false)
const form = reactive({ label: '', name: '' })
const slug = (value: string) => value.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '').replace(/^(\d)/, 'r$1')
watch(() => form.label, (label) => {
  form.name = slug(label).slice(0, 40)
})
async function create() {
  creating.value = true
  try {
    await request('/admin/roles', { method: 'POST', body: { ...form, permissions: [] } })
    createOpen.value = false
    form.label = ''
    await refresh()
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    creating.value = false
  }
}
</script>

<template>
  <UDashboardPanel id="roles">
    <template #header>
      <UDashboardNavbar :title="t('nav.roles')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton
            icon="i-lucide-plus"
            :label="t('roles.new')"
            color="neutral"
            variant="outline"
            @click="createOpen = true"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <p class="text-sm text-(--ui-text-muted)">
        {{ t('roles.help') }}
      </p>
      <UAlert
        v-if="error"
        color="error"
        variant="subtle"
        icon="i-lucide-circle-alert"
        :title="apiError(error)"
      />
      <div
        v-if="data"
        class="overflow-x-auto"
      >
        <table class="w-full min-w-[640px] border-collapse text-sm">
          <thead>
            <tr class="border-b border-(--ui-border)">
              <th class="py-2 pr-4 text-left font-medium">
                {{ t('roles.permission') }}
              </th>
              <th
                v-for="role in data.roles"
                :key="role.id"
                class="px-2 py-2 text-center font-medium"
              >
                <div>{{ role.label }}</div>
                <div class="text-xs font-normal text-(--ui-text-muted)">
                  {{ t('roles.members', role.members) }}
                </div>
              </th>
            </tr>
          </thead>
          <tbody>
            <template
              v-for="group in data.catalog"
              :key="group.group"
            >
              <tr>
                <td
                  :colspan="data.roles.length + 1"
                  class="pt-4 pb-1 text-xs font-semibold tracking-wide text-(--ui-text-muted) uppercase"
                >
                  {{ t(`roles.groups.${group.group}`) }}
                </td>
              </tr>
              <tr
                v-for="permission in group.permissions"
                :key="permission"
                class="border-b border-(--ui-border)"
              >
                <td
                  class="py-1.5 pr-4"
                  :title="permission"
                >
                  {{ permissionLabel(permission) }}
                </td>
                <td
                  v-for="role in data.roles"
                  :key="role.id"
                  class="px-2 py-1.5 text-center"
                >
                  <UCheckbox
                    :model-value="draft[role.id]?.has(permission) ?? false"
                    :aria-label="`${role.label}: ${permissionLabel(permission)}`"
                    class="inline-flex"
                    @update:model-value="(v) => toggle(role, permission, v === true)"
                  />
                </td>
              </tr>
            </template>
            <tr>
              <td />
              <td
                v-for="role in data.roles"
                :key="role.id"
                class="px-2 pt-3 text-center"
              >
                <UButton
                  :label="t('roles.save')"
                  size="sm"
                  :disabled="!dirty(role)"
                  :loading="saving === role.id"
                  @click="save(role)"
                />
              </td>
            </tr>
          </tbody>
        </table>
        <p class="mt-4 text-xs text-(--ui-text-muted)">
          {{ t('roles.adminNote') }}
        </p>
      </div>
      <p
        v-else-if="status === 'pending'"
        class="text-sm text-(--ui-text-muted)"
      >
        …
      </p>

      <UModal
        v-model:open="createOpen"
        :title="t('roles.new')"
      >
        <template #body>
          <form
            id="role-form"
            class="space-y-4"
            @submit.prevent="create"
          >
            <UFormField
              :label="t('roles.label')"
              :hint="form.name"
              required
            >
              <UInput
                v-model="form.label"
                class="w-full"
                required
                minlength="2"
              />
            </UFormField>
          </form>
        </template>
        <template #footer>
          <UButton
            type="submit"
            form="role-form"
            :label="t('roles.create')"
            :loading="creating"
            :disabled="form.name.length < 2"
          />
        </template>
      </UModal>
    </template>
  </UDashboardPanel>
</template>
