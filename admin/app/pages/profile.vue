<script setup lang="ts">
import type { SessionInfo } from '~/types/api'

const { t, locale } = useI18n()
const { request } = useApi()
const toast = useToast()
const apiError = useApiError()
const auth = useAuth()

const form = reactive({ current_password: '', new_password: '' })
const saving = ref(false)

const { data: sessions, refresh: refreshSessions } = await useAsyncData('my-sessions', () => request<SessionInfo[]>('/auth/sessions'))
const closing = ref<string | null>(null)

async function closeSession(session: SessionInfo) {
  closing.value = session.id
  try {
    await request(`/auth/sessions/${session.id}`, { method: 'DELETE' })
    await refreshSessions()
  }
  catch (error) {
    toast.add({ title: apiError(error), color: 'error' })
  }
  finally {
    closing.value = null
  }
}

const sessionIcon = (session: SessionInfo) =>
  session.platform === 'android' || session.platform === 'ios' ? 'i-lucide-smartphone' : 'i-lucide-monitor'

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
              {{ t('sessions.title') }}
            </h2>
          </template>
          <ul class="divide-y divide-(--ui-border)">
            <li
              v-for="session in sessions ?? []"
              :key="session.id"
              class="flex items-center justify-between gap-3 py-2 text-sm"
            >
              <span class="flex items-center gap-3">
                <UIcon
                  :name="sessionIcon(session)"
                  class="size-5 text-(--ui-text-muted)"
                />
                <span>
                  {{ session.device ?? t('sessions.unknownDevice') }}
                  <UBadge
                    v-if="session.current"
                    size="sm"
                    variant="subtle"
                    class="ms-1"
                  >{{ t('sessions.current') }}</UBadge>
                  <span class="block text-xs text-(--ui-text-muted)">
                    {{ t('sessions.lastUsed', { time: formatDate(session.last_used_at, locale) }) }}<template v-if="session.ip"> · {{ session.ip }}</template>
                  </span>
                </span>
              </span>
              <UButton
                v-if="!session.current"
                size="sm"
                color="neutral"
                variant="outline"
                :loading="closing === session.id"
                :label="t('sessions.close')"
                @click="closeSession(session)"
              />
            </li>
          </ul>
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
