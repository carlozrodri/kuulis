<script setup lang="ts">
import type { AdminUser, Role } from '~/types/api'

definePageMeta({ permission: 'users.view' })

const { t, locale } = useI18n()
const route = useRoute()
const { request } = useApi()
const auth = useAuth()
const toast = useToast()
const apiError = useApiError()

const id = computed(() => route.params.id as string)
const { data: user, refresh } = await useAsyncData(`user-${id.value}`, () => request<AdminUser>(`/users/${id.value}`))

const form = reactive<{ full_name: string, role: Role, is_active: boolean, is_verified: boolean, is_test_account: boolean }>({
  full_name: '',
  role: 'user',
  is_active: true,
  is_verified: false,
  is_test_account: false,
})
watchEffect(() => {
  if (user.value) {
    Object.assign(form, {
      full_name: user.value.full_name,
      role: user.value.role,
      is_active: user.value.is_active,
      is_verified: user.value.is_verified,
      is_test_account: user.value.is_test_account ?? false,
    })
  }
})

// Grace period before an account is erased (API settings.ACCOUNT_DELETION_GRACE_DAYS).
const ERASE_AFTER_DAYS = 30
const eraseOn = computed(() => {
  const requested = user.value?.deletion_requested_at
  return requested ? new Date(new Date(requested).getTime() + ERASE_AFTER_DAYS * 86_400_000).toISOString() : null
})

const saving = ref(false)
const roleItems = computed(() => (['user', 'staff', 'admin'] as Role[]).map(r => ({ label: t(`roles.${r}`), value: r })))

const resetting = ref(false)
async function resetTotp() {
  if (!confirm(t('totp.resetConfirm'))) return
  resetting.value = true
  try {
    await request(`/users/${id.value}/totp/reset`, { method: 'POST' })
    toast.add({ title: t('totp.resetDone'), color: 'success' })
  }
  catch (error) {
    toast.add({ title: apiError(error), color: 'error' })
  }
  finally {
    resetting.value = false
  }
}

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
        <template #trailing>
          <UBadge
            v-if="isSuspensionInForce(user?.suspension)"
            color="error"
            variant="solid"
            icon="i-lucide-user-x"
          >
            {{ t('suspensions.suspended') }}
          </UBadge>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div
        v-if="user"
        class="grid max-w-3xl gap-6"
      >
        <UAlert
          v-if="user.deleted_at"
          color="neutral"
          variant="subtle"
          icon="i-lucide-user-x"
          :title="t('privacy.userErased', { date: formatDate(user.deleted_at, locale) })"
        />
        <UAlert
          v-else-if="user.deletion_requested_at"
          color="warning"
          variant="subtle"
          icon="i-lucide-clock"
          :title="t('privacy.userScheduled', { date: formatDate(eraseOn, locale) })"
          :description="t('privacy.userScheduledHelp', { date: formatDate(user.deletion_requested_at, locale) })"
        />
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
            <USwitch
              v-model="form.is_test_account"
              :label="t('users.testAccount')"
              :description="t('users.testAccountHint')"
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

        <!-- Doc 05: lost authenticator of a team member -->
        <UCard v-if="auth.isAdmin.value && user.role !== 'user'">
          <div class="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 class="font-semibold">
                {{ t('totp.resetTitle') }}
              </h2>
              <p class="text-sm text-(--ui-text-muted)">
                {{ t('totp.resetHelp') }}
              </p>
            </div>
            <UButton
              color="error"
              variant="outline"
              icon="i-lucide-key-round"
              :loading="resetting"
              :label="t('totp.reset')"
              @click="resetTotp"
            />
          </div>
        </UCard>

        <!-- Phase 1E: account suspension (moderation) and reports -->
        <AccountSuspensionCard
          :user-id="user.id"
          :name="user.full_name || user.email"
          :suspension="user.suspension"
          :can-suspend="user.role === 'user'"
          @changed="refresh"
        />
        <!-- Doc 15: cancellations and quality -->
        <QualityCard :user-id="user.id" />
        <!-- Doc 16: anti-fraud -->
        <RiskCard :user-id="user.id" />
        <ReportsList :user-id="user.id" />
        <LegalAcceptancesCard
          v-if="user.role === 'user'"
          :user-id="user.id"
        />
        <AuditHistoryCard
          entity-type="user"
          :entity-id="user.id"
        />
      </div>
    </template>
  </UDashboardPanel>
</template>
