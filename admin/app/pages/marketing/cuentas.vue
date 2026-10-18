<script setup lang="ts">
import type { MarketingAccount, MarketingAccountStatus, MarketingConnection, MarketingPlatform } from '~/types/api'
import { ACCOUNT_CONNECTIONS, ACCOUNT_STATUSES, MARKETING_PLATFORMS } from '~/types/api'

definePageMeta({ permission: 'marketing.view' })

const { t } = useI18n()
const { request } = useApi()
const auth = useAuth()
const toast = useToast()
const apiError = useApiError()
const canManage = computed(() => auth.can('marketing.manage'))

const { data, status, error, refresh } = await useAsyncData('marketing-accounts', () => request<MarketingAccount[]>('/admin/marketing/accounts'))

const editing = ref<MarketingAccount | null>(null)
const open = ref(false)
const form = reactive({
  platform: 'tiktok' as MarketingPlatform,
  handle: '',
  url: '',
  status: 'pendiente' as MarketingAccountStatus,
  connection: 'manual' as MarketingConnection,
  notes: '',
})
const platformItems = computed(() => MARKETING_PLATFORMS.map(p => ({ label: platformLabel[p], value: p })))
const statusItems = computed(() => ACCOUNT_STATUSES.map(value => ({ label: t(`marketing.accounts.statuses.${value}`), value })))
const connectionItems = computed(() => ACCOUNT_CONNECTIONS.map(value => ({ label: t(`marketing.accounts.connections.${value}`), value })))

function start(account: MarketingAccount | null) {
  editing.value = account
  Object.assign(form, {
    platform: account?.platform ?? 'tiktok',
    handle: account?.handle ?? '',
    url: account?.url ?? '',
    status: account?.status ?? 'pendiente',
    connection: account?.connection ?? 'manual',
    notes: account?.notes ?? '',
  })
  open.value = true
}
const saving = ref(false)
async function save() {
  if (!form.handle.trim()) return
  saving.value = true
  const body = { handle: form.handle.trim(), url: form.url.trim() || null, status: form.status, connection: form.connection, notes: form.notes.trim() || null }
  try {
    if (editing.value) await request(`/admin/marketing/accounts/${editing.value.id}`, { method: 'PATCH', body })
    else await request('/admin/marketing/accounts', { method: 'POST', body: { ...body, platform: form.platform } })
    open.value = false
    toast.add({ title: t('common.saved'), color: 'success' })
    await refresh()
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    saving.value = false
  }
}
</script>

<template>
  <UDashboardPanel id="marketing-accounts">
    <template #header>
      <UDashboardNavbar :title="t('nav.marketingAccounts')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton
            v-if="canManage"
            icon="i-lucide-plus"
            :label="t('marketing.accounts.new')"
            @click="start(null)"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <p class="text-sm text-(--ui-text-muted)">
        {{ t('marketing.accounts.help') }}
      </p>
      <UAlert
        v-if="error"
        color="error"
        variant="subtle"
        icon="i-lucide-circle-alert"
        :title="apiError(error)"
      />
      <p
        v-if="status !== 'pending' && !data?.length"
        class="rounded-lg border border-dashed border-(--ui-border) p-6 text-center text-sm text-(--ui-text-muted)"
      >
        {{ t('marketing.accounts.empty') }}
      </p>
      <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <UCard
          v-for="account in data ?? []"
          :key="account.id"
          :ui="{ body: 'space-y-2' }"
        >
          <div class="flex items-start justify-between gap-2">
            <div class="flex min-w-0 items-center gap-2">
              <UIcon
                :name="platformIcon[account.platform]"
                class="size-5 shrink-0"
              />
              <div class="min-w-0">
                <p class="truncate font-medium">
                  {{ account.handle }}
                </p>
                <p class="text-xs text-(--ui-text-muted)">
                  {{ platformLabel[account.platform] }} · {{ t(`marketing.accounts.connections.${account.connection}`) }}
                </p>
              </div>
            </div>
            <UBadge
              :color="accountStatusColor[account.status]"
              variant="subtle"
            >
              {{ t(`marketing.accounts.statuses.${account.status}`) }}
            </UBadge>
          </div>
          <p
            v-if="account.notes"
            class="text-sm text-(--ui-text-muted)"
          >
            {{ account.notes }}
          </p>
          <div class="flex justify-end gap-1">
            <UButton
              v-if="account.url"
              :to="account.url"
              target="_blank"
              rel="noopener"
              size="xs"
              color="neutral"
              variant="ghost"
              icon="i-lucide-external-link"
              :label="t('marketing.accounts.open')"
            />
            <UButton
              v-if="canManage"
              size="xs"
              color="neutral"
              variant="ghost"
              icon="i-lucide-pencil"
              :label="t('marketing.edit')"
              @click="start(account)"
            />
          </div>
        </UCard>
      </div>

      <UModal
        v-model:open="open"
        :title="editing ? t('marketing.accounts.edit') : t('marketing.accounts.new')"
      >
        <template #body>
          <form
            id="account-form"
            class="grid grid-cols-2 gap-3"
            @submit.prevent="save"
          >
            <UFormField :label="t('marketing.performance.platform')">
              <USelect
                v-model="form.platform"
                :items="platformItems"
                :disabled="!!editing"
                class="w-full"
              />
            </UFormField>
            <UFormField
              :label="t('marketing.accounts.handle')"
              required
            >
              <UInput
                v-model="form.handle"
                placeholder="@kuulis"
                :maxlength="60"
                class="w-full"
              />
            </UFormField>
            <UFormField
              :label="t('marketing.accounts.url')"
              class="col-span-2"
            >
              <UInput
                v-model="form.url"
                type="url"
                placeholder="https://"
                :maxlength="300"
                class="w-full"
              />
            </UFormField>
            <UFormField :label="t('marketing.accounts.status')">
              <USelect
                v-model="form.status"
                :items="statusItems"
                class="w-full"
              />
            </UFormField>
            <UFormField :label="t('marketing.accounts.connection')">
              <USelect
                v-model="form.connection"
                :items="connectionItems"
                class="w-full"
              />
            </UFormField>
            <UFormField
              :label="t('marketing.spend.notes')"
              class="col-span-2"
            >
              <UTextarea
                v-model="form.notes"
                :rows="2"
                :maxlength="1000"
                class="w-full"
              />
            </UFormField>
          </form>
        </template>
        <template #footer>
          <div class="flex w-full justify-end gap-2">
            <UButton
              color="neutral"
              variant="ghost"
              :label="t('common.cancel')"
              @click="open = false"
            />
            <UButton
              type="submit"
              form="account-form"
              :label="t('common.save')"
              :loading="saving"
              :disabled="!form.handle.trim()"
            />
          </div>
        </template>
      </UModal>
    </template>
  </UDashboardPanel>
</template>
