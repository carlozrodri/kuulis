<script setup lang="ts">
import type { AdminWallet, Page, WalletEntry } from '~/types/api'

const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const { request } = useApi()
const auth = useAuth()
const apiError = useApiError()

const userId = computed(() => route.params.userId as string)

const { data: wallet, error: walletError, refresh: refreshWallet } = await useAsyncData(
  `wallet-page-${userId.value}`,
  () => request<AdminWallet>(`/admin/wallets/${userId.value}`),
)

const page = ref(1)
const limit = 25
const query = computed(() => ({ limit, offset: (page.value - 1) * limit }))

const { data: entries, status, error, refresh: refreshEntries } = await useAsyncData(
  `wallet-entries-${userId.value}`,
  () => request<Page<WalletEntry>>(`/admin/wallets/${userId.value}/entries`, { query: query.value }),
  { watch: [query] },
)

const title = computed(() => wallet.value?.user?.name || wallet.value?.user?.email || t('wallet.title'))
const blocked = computed(() => (wallet.value?.pending_charges ?? []).some(c => isOverdue(c)))

const adjustOpen = ref(false)
async function onAdjusted() {
  page.value = 1
  await Promise.all([refreshWallet(), refreshEntries()])
}

function back() {
  if (window.history.length > 1) router.back()
  else navigateTo('/drivers')
}
</script>

<template>
  <UDashboardPanel id="wallet-detail">
    <template #header>
      <UDashboardNavbar :title="title">
        <template #leading>
          <UButton
            icon="i-lucide-arrow-left"
            color="neutral"
            variant="ghost"
            :aria-label="t('common.back')"
            @click="back"
          />
        </template>
        <template #trailing>
          <UBadge
            v-if="blocked"
            color="error"
            variant="subtle"
            icon="i-lucide-lock"
          >
            {{ t('subscriptions.blocked') }}
          </UBadge>
        </template>
        <template #right>
          <UButton
            v-if="auth.isAdmin.value && wallet"
            icon="i-lucide-scale"
            :label="t('wallet.adjust.title')"
            @click="adjustOpen = true"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <UAlert
        v-if="walletError && !wallet"
        color="error"
        variant="subtle"
        icon="i-lucide-circle-alert"
        :title="apiError(walletError)"
      />

      <UCard v-if="wallet">
        <dl class="grid gap-4 text-sm sm:grid-cols-4">
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
              {{ t('drivers.email') }}
            </dt>
            <dd class="break-all">
              <NuxtLink
                :to="`/users/${userId}`"
                class="text-primary hover:underline"
              >
                {{ wallet.user?.email || userId }}
              </NuxtLink>
            </dd>
          </div>
          <div>
            <dt class="text-(--ui-text-muted)">
              {{ t('wallet.binancePayId') }}
            </dt>
            <dd class="font-mono">
              {{ wallet.binance_pay_id || '—' }}
            </dd>
          </div>
          <div>
            <dt class="text-(--ui-text-muted)">
              {{ t('wallet.sentThisMonth') }}
            </dt>
            <dd class="tabular-nums">
              {{ formatUsdt(wallet.sent_this_month, locale) }}
            </dd>
          </div>
        </dl>
      </UCard>

      <section class="space-y-3">
        <h2 class="font-semibold">
          {{ t('wallet.entries') }}
        </h2>
        <UAlert
          v-if="error"
          color="error"
          variant="subtle"
          icon="i-lucide-circle-alert"
          :title="apiError(error)"
        />
        <WalletEntriesTable
          :entries="entries?.items ?? []"
          :loading="status === 'pending'"
        />
        <div class="flex items-center justify-between border-t border-(--ui-border) pt-4">
          <span class="text-sm text-(--ui-text-muted)">
            {{ t('wallet.totalEntries', { n: entries?.total ?? 0 }) }}
          </span>
          <UPagination
            v-model:page="page"
            :total="entries?.total ?? 0"
            :items-per-page="limit"
          />
        </div>
      </section>

      <AdjustBalanceModal
        v-if="wallet"
        v-model:open="adjustOpen"
        :user-id="userId"
        :balance="wallet.balance"
        :name="wallet.user?.name"
        @adjusted="onAdjusted"
      />
    </template>
  </UDashboardPanel>
</template>
