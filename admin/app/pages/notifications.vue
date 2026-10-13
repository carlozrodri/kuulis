<script setup lang="ts">
import type { Role } from '~/types/api'

definePageMeta({ permission: 'notifications.send' })

const { t } = useI18n()
const { request } = useApi()
const toast = useToast()
const approvals = useApprovalCount()
const apiError = useApiError()

const audience = ref<'all' | Role | 'user_id'>('all')
const form = reactive({ title: '', body: '', user_id: '' })
const sending = ref(false)

const audienceItems = computed(() => [
  { label: t('notifications.everyone'), value: 'all' },
  { label: t('roles.user'), value: 'user' },
  { label: t('roles.staff'), value: 'staff' },
  { label: t('notifications.singleUser'), value: 'user_id' },
])

async function send() {
  sending.value = true
  try {
    const body: Record<string, unknown> = { title: form.title, body: form.body }
    if (audience.value === 'user_id') body.user_id = form.user_id
    else if (audience.value !== 'all') body.role = audience.value
    const result = await request<unknown>('/notifications/send', { method: 'POST', body })
    if (isHeld(result)) await approvals.notifyHeld(result)
    else toast.add({ title: t('notifications.queued'), color: 'success' })
    Object.assign(form, { title: '', body: '', user_id: '' })
  }
  catch (error) {
    toast.add({ title: apiError(error), color: 'error' })
  }
  finally {
    sending.value = false
  }
}
</script>

<template>
  <UDashboardPanel id="notifications">
    <template #header>
      <UDashboardNavbar :title="t('nav.notifications')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
      </UDashboardNavbar>
    </template>
    <template #body>
      <UAlert
        class="mb-4 max-w-2xl"
        color="neutral"
        variant="subtle"
        icon="i-lucide-zap"
        :title="t('notifications.quickTitle')"
        :description="t('notifications.quickHelp')"
        :actions="[{ label: t('nav.campaigns'), to: '/campaigns', color: 'neutral', variant: 'outline', icon: 'i-lucide-send' }]"
      />
      <UCard class="max-w-2xl">
        <form
          class="space-y-4"
          @submit.prevent="send"
        >
          <UFormField :label="t('notifications.audience')">
            <USelect
              v-model="audience"
              :items="audienceItems"
              class="w-60"
            />
          </UFormField>
          <UFormField
            v-if="audience === 'user_id'"
            :label="t('notifications.userId')"
          >
            <UInput
              v-model="form.user_id"
              class="w-full"
              required
            />
          </UFormField>
          <UFormField :label="t('notifications.title')">
            <UInput
              v-model="form.title"
              class="w-full"
              maxlength="200"
              required
            />
          </UFormField>
          <UFormField :label="t('notifications.body')">
            <UTextarea
              v-model="form.body"
              class="w-full"
              :rows="4"
              maxlength="2000"
            />
          </UFormField>
          <UButton
            type="submit"
            icon="i-lucide-send"
            :loading="sending"
            :label="t('notifications.send')"
          />
        </form>
      </UCard>
    </template>
  </UDashboardPanel>
</template>
