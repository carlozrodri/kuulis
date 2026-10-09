<script setup lang="ts">
const { t } = useI18n()
const { request } = useApi()
const toast = useToast()
const apiError = useApiError()
const auth = useAuth()

const form = reactive({ current_password: '', new_password: '' })
const saving = ref(false)

async function changePassword() {
  saving.value = true
  try {
    await request('/users/me/password', { method: 'POST', body: { ...form } })
    toast.add({ title: t('profile.passwordChanged'), color: 'success' })
    Object.assign(form, { current_password: '', new_password: '' })
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
  <UDashboardPanel id="profile">
    <template #header>
      <UDashboardNavbar :title="t('nav.profile')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
      </UDashboardNavbar>
    </template>
    <template #body>
      <div class="grid max-w-2xl gap-6">
        <UCard>
          <UUser
            :name="auth.user.value?.full_name || auth.user.value?.email"
            :description="auth.user.value?.email"
          />
        </UCard>
        <UCard>
          <template #header>
            <h2 class="font-semibold">
              {{ t('profile.changePassword') }}
            </h2>
          </template>
          <form
            class="space-y-4"
            @submit.prevent="changePassword"
          >
            <UFormField :label="t('profile.currentPassword')">
              <UInput
                v-model="form.current_password"
                type="password"
                class="w-full"
                required
              />
            </UFormField>
            <UFormField
              :label="t('profile.newPassword')"
              :hint="t('validation.minPassword')"
            >
              <UInput
                v-model="form.new_password"
                type="password"
                class="w-full"
                minlength="8"
                required
              />
            </UFormField>
            <UButton
              type="submit"
              :loading="saving"
              :label="t('common.save')"
            />
          </form>
        </UCard>
      </div>
    </template>
  </UDashboardPanel>
</template>
