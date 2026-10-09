<script setup lang="ts">
import type { Role, User } from '~/types/api'

const { t, locale } = useI18n()
const route = useRoute()
const { request } = useApi()
const auth = useAuth()
const toast = useToast()
const apiError = useApiError()

const id = computed(() => route.params.id as string)
const { data: user, refresh } = await useAsyncData(`user-${id.value}`, () => request<User>(`/users/${id.value}`))

const form = reactive<{ full_name: string, role: Role, is_active: boolean, is_verified: boolean }>({
  full_name: '',
  role: 'user',
  is_active: true,
  is_verified: false,
})
watchEffect(() => {
  if (user.value) {
    Object.assign(form, {
      full_name: user.value.full_name,
      role: user.value.role,
      is_active: user.value.is_active,
      is_verified: user.value.is_verified,
    })
  }
})

const saving = ref(false)
const roleItems = computed(() => (['user', 'staff', 'admin'] as Role[]).map(r => ({ label: t(`roles.${r}`), value: r })))

async function save() {
  saving.value = true
  try {
    await request(`/users/${id.value}`, { method: 'PATCH', body: { ...form } })
    toast.add({ title: t('common.saved'), color: 'success' })
    await refresh()
  }
  catch (error) {
    toast.add({ title: apiError(error), color: 'error' })
  }
  finally {
    saving.value = false
  }
}
</script>

<template>
  <UDashboardPanel id="user-detail">
    <template #header>
      <UDashboardNavbar :title="user?.email ?? ''">
        <template #leading>
          <UButton
            icon="i-lucide-arrow-left"
            color="neutral"
            variant="ghost"
            to="/users"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div
        v-if="user"
        class="grid max-w-3xl gap-6"
      >
        <UCard>
          <dl class="grid grid-cols-2 gap-4 text-sm">
            <div>
              <dt class="text-(--ui-text-muted)">
                {{ t('users.createdAt') }}
              </dt>
              <dd>{{ formatDate(user.created_at, locale) }}</dd>
            </div>
            <div>
              <dt class="text-(--ui-text-muted)">
                {{ t('users.lastLogin') }}
              </dt>
              <dd>{{ formatDate(user.last_login_at, locale) }}</dd>
            </div>
            <div>
              <dt class="text-(--ui-text-muted)">
                {{ t('users.locale') }}
              </dt>
              <dd>{{ user.locale }}</dd>
            </div>
          </dl>
        </UCard>

        <UCard>
          <form
            class="space-y-4"
            @submit.prevent="save"
          >
            <UFormField :label="t('users.name')">
              <UInput
                v-model="form.full_name"
                class="w-full"
                :disabled="!auth.isAdmin.value"
              />
            </UFormField>
            <UFormField :label="t('users.role')">
              <USelect
                v-model="form.role"
                :items="roleItems"
                class="w-48"
                :disabled="!auth.isAdmin.value"
              />
            </UFormField>
            <USwitch
              v-model="form.is_active"
              :label="t('users.active')"
              :disabled="!auth.isAdmin.value"
            />
            <USwitch
              v-model="form.is_verified"
              :label="t('users.verified')"
              :disabled="!auth.isAdmin.value"
            />
            <UButton
              v-if="auth.isAdmin.value"
              type="submit"
              :loading="saving"
              :label="t('common.save')"
            />
            <p
              v-else
              class="text-sm text-(--ui-text-muted)"
            >
              {{ t('users.readOnly') }}
            </p>
          </form>
        </UCard>
      </div>
    </template>
  </UDashboardPanel>
</template>
