<script setup lang="ts">
import type { AdminWallet, AppConfig } from '~/types/api'

/** Wallet summary on the driver detail page (GET /admin/wallets/{user_id}). */
const props = defineProps<{ userId: string, name?: string | null }>()

const { t, locale } = useI18n()
const { request } = useApi()
const auth = useAuth()
const apiError = useApiError()

const { data: wallet, status, error, refresh } = useAsyncData(
  `wallet-${props.userId}`,
  () => request<AdminWallet>(`/admin/wallets/${props.userId}`),
)
// Only for the transfer limit; the contract default otherwise.
const { data: config } = useAsyncData('wallet-card-config', () => request<AppConfig>('/admin/config').catch(() => null))
const transferLimit = computed(() => config.value?.transfer_monthly_limit ?? '50.00')

// 404 (no such user) or 403 not_a_driver: nothing to show rather than an error.
const notFound = computed(() => {
  const err = error.value as { status?: number, data?: { error?: { code?: string } } } | null
  return err?.status === 404 || err?.data?.error?.code === 'not_a_driver'
})
const recent = computed(() => (wallet.value?.entries ?? []).slice(0, 10))
const pendingCharges = computed(() => wallet.value?.pending_charges ?? [])
const blocked = computed(() => pendingCharges.value.some(c => isOverdue(c)))

const adjustOpen = ref(false)
</script>

<template>
  <UCard>
    <template #header>
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div class="flex items-center gap-2">
          <h2 class="font-semibold">
            {{ t('wallet.title') }}
          </h2>
          <UBadge
            v-if="blocked"
            color="error"
            variant="subtle"
            icon="i-lucide-lock"
          >
            {{ t('subscriptions.blocked') }}
          </UBadge>
        </div>
        <div
          v-if="wallet"
          class="flex gap-2"
        >
          <UButton
            v-if="auth.isAdmin.value"
            icon="i-lucide-scale"
            color="neutral"
            variant="outline"
            size="sm"
            :label="t('wallet.adjust.title')"
            @click="adjustOpen = true"
          />
          <UButton
            icon="i-lucide-list"
            color="neutral"
            variant="ghost"
            size="sm"
            :label="t('wallet.allEntries')"
            :to="walletLink(userId)"
          />
        </div>
      </div>
    </template>

    <p
      v-if="notFound"
      class="text-sm text-(--ui-text-muted)"
    >
      {{ t('wallet.none') }}
    </p>
    <UAlert
      v-else-if="error && !wallet"
      color="error"
      variant="subtle"
      icon="i-lucide-circle-alert"
      :title="apiError(error)"
    />
    <USkeleton
      v-else-if="status === 'pending' && !wallet"
      class="h-32"
    />

    <div
      v-if="wallet"
      class="space-y-6"
    >
      <dl class="grid gap-4 text-sm sm:grid-cols-3">
        <div>
          <dt class="text-(--ui-text-muted)">
            {{ t('wallet.balance') }}
          </dt>
          <dd class="text-2xl font-semibold tabular-nums">
            {{ formatUsdt(wallet.balance, locale) }}
          </dd>
        </div>
        <div>
          <dt class="text-(--ui-text-muted)">
            {{ t('wallet.binancePayId') }}
          </dt>
          <dd
            v-if="wallet.binance_pay_id"
            class="font-mono"
          >
            {{ wallet.binance_pay_id }}
          </dd>
          <dd
            v-else
            class="text-(--ui-text-muted)"
          >
            {{ t('wallet.noPayId') }}
          </dd>
        </div>
        <div>
          <dt class="text-(--ui-text-muted)">
            {{ t('wallet.sentThisMonth') }}
          </dt>
          <dd class="tabular-nums">
            {{ formatUsdt(wallet.sent_this_month, locale) }}
            <span class="text-(--ui-text-muted)">/ {{ formatUsdt(transferLimit, locale) }}</span>
          </dd>
        </div>
      </dl>

      <div
        v-if="pendingCharges.length"
        class="space-y-2"
      >
        <h3 class="text-sm font-medium">
          {{ t('wallet.pendingCharges') }}
        </h3>
        <ul class="divide-y divide-(--ui-border) rounded-md border border-(--ui-border)">
          <li
            v-for="charge in pendingCharges"
            :key="charge.id"
            class="flex flex-wrap items-center justify-between gap-2 p-3 text-sm"
          >
            <div>
              <p class="font-medium capitalize">
                {{ formatMonth(charge.month, locale) }}
              </p>
              <p class="text-xs text-(--ui-text-muted)">
                {{ t('subscriptions.dueAt') }}: {{ formatDate(charge.due_at, locale) }}
              </p>
            </div>
            <div class="flex items-center gap-2">
              <span class="font-medium tabular-nums">{{ formatUsdt(charge.fee, locale) }}</span>
              <UBadge
                :color="isOverdue(charge) ? 'error' : 'warning'"
                variant="subtle"
                size="sm"
              >
                {{ isOverdue(charge) ? t('subscriptions.blocked') : t('subscriptions.statuses.pending') }}
              </UBadge>
            </div>
          </li>
        </ul>
        <NuxtLink
          :to="`/subscriptions?status=pending&month=all${wallet.user?.email ? `&q=${encodeURIComponent(wallet.user.email)}` : ''}`"
          class="text-sm text-primary hover:underline"
        >
          {{ t('wallet.manageCharges') }}
        </NuxtLink>
      </div>

      <div class="space-y-2">
        <h3 class="text-sm font-medium">
          {{ t('wallet.recentEntries') }}
        </h3>
        <WalletEntriesTable :entries="recent" />
      </div>
    </div>

    <AdjustBalanceModal
      v-if="wallet"
      v-model:open="adjustOpen"
      :user-id="userId"
      :balance="wallet.balance"
      :name="name ?? wallet.user?.name"
      @adjusted="refresh()"
    />
  </UCard>
</template>
