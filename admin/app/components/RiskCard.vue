<script setup lang="ts">
/**
 * Risk of a person (doc 16): score, whether credits and transfers are frozen, latest alerts, the phones
 * they use (and who else uses them), duplicate identifiers, held payments and banned identifiers.
 * Someone with risk.manage can ban the account from here.
 */
import type { RiskUserDetail } from '~/types/api'

const props = defineProps<{ userId: string }>()

const { t, te, locale } = useI18n()
const { request } = useApi()
const auth = useAuth()
const apiError = useApiError()

const canView = computed(() => auth.can('risk.view'))
const canManage = computed(() => auth.can('risk.manage'))
const label = (key: string, fallback: string) => (te(key) ? t(key) : fallback)

const { data, error, refresh } = await useAsyncData(
  `risk-${props.userId}`,
  () => (canView.value ? request<RiskUserDetail>(`/admin/risk/users/${props.userId}`) : Promise.resolve(null)),
  { watch: [() => props.userId] },
)

const LATEST = 5
const latest = computed(() => (data.value?.signals ?? []).slice(0, LATEST))
const banOpen = ref(false)

function banned(detail: RiskUserDetail) {
  data.value = detail
}
</script>

<template>
  <UCard v-if="canView">
    <template #header>
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div class="flex flex-wrap items-center gap-2">
          <h2 class="font-semibold">
            {{ t('risk.card.title') }}
          </h2>
          <template v-if="data">
            <UBadge
              :color="riskScoreColor(data.user.risk_score)"
              variant="solid"
              class="tabular-nums"
              :title="t('risk.score')"
            >
              {{ t('risk.points', { n: data.user.risk_score }) }}
            </UBadge>
            <UBadge
              v-if="data.frozen"
              color="warning"
              variant="subtle"
              icon="i-lucide-snowflake"
            >
              {{ t('risk.card.frozen') }}
            </UBadge>
            <UBadge
              v-if="data.suspended"
              color="error"
              variant="subtle"
            >
              {{ t('verification.duplicates.suspended') }}
            </UBadge>
          </template>
        </div>
        <UButton
          v-if="canManage && data"
          size="sm"
          color="error"
          variant="outline"
          icon="i-lucide-ban"
          :label="t('risk.ban.button')"
          @click="banOpen = true"
        />
      </div>
    </template>

    <UAlert
      v-if="error"
      color="error"
      variant="subtle"
      icon="i-lucide-circle-alert"
      :title="apiError(error)"
    />
    <USkeleton
      v-else-if="!data"
      class="h-40"
    />

    <div
      v-else
      class="space-y-6"
    >
      <p
        v-if="data.frozen"
        class="text-sm text-(--ui-text-muted)"
      >
        {{ t('risk.card.frozenHelp') }}
      </p>

      <section class="space-y-2">
        <h3 class="text-sm font-medium">
          {{ t('risk.card.alerts') }}
        </h3>
        <p
          v-if="!latest.length"
          class="text-sm text-(--ui-text-muted)"
        >
          {{ t('risk.card.noAlerts') }}
        </p>
        <ul
          v-else
          class="divide-y divide-(--ui-border) text-sm"
        >
          <li
            v-for="signal in latest"
            :key="signal.id"
            class="flex flex-wrap items-center justify-between gap-2 py-2"
          >
            <div class="min-w-0">
              <NuxtLink
                :to="{ path: '/risk', query: { signal: signal.id } }"
                class="font-medium text-primary hover:underline"
              >
                {{ label(riskKindKey(signal.kind), signal.kind) }}
              </NuxtLink>
              <p class="text-xs text-(--ui-text-muted)">
                {{ signal.reasons.map(r => label(riskReasonKey(r), r)).join(' · ') }}
                · {{ formatDate(signal.created_at, locale) }}
              </p>
            </div>
            <div class="flex items-center gap-2">
              <UBadge
                :color="signalStatusColor(signal.status)"
                variant="subtle"
                size="sm"
              >
                {{ label(`risk.statuses.${signal.status}`, signal.status) }}
              </UBadge>
              <UBadge
                :color="riskScoreColor(signal.score)"
                variant="outline"
                size="sm"
                class="tabular-nums"
              >
                {{ signal.score }}
              </UBadge>
            </div>
          </li>
        </ul>
        <p
          v-if="data.signals.length > LATEST"
          class="text-xs text-(--ui-text-muted)"
        >
          {{ t('risk.card.moreAlerts', { n: data.signals.length - LATEST }) }}
        </p>
      </section>

      <section class="space-y-2">
        <h3 class="text-sm font-medium">
          {{ t('risk.card.devices') }}
        </h3>
        <p
          v-if="!data.devices.length"
          class="text-sm text-(--ui-text-muted)"
        >
          {{ t('risk.card.noDevices') }}
        </p>
        <ul
          v-else
          class="divide-y divide-(--ui-border) text-sm"
        >
          <li
            v-for="device in data.devices"
            :key="device.id"
            class="py-2"
          >
            <p class="font-medium">
              {{ device.model || t('risk.card.unknownModel') }}
              <span class="font-normal text-(--ui-text-muted)">· {{ device.platform || '—' }} · {{ t('risk.card.appVersion', { v: device.app_version || '—' }) }}</span>
            </p>
            <p class="text-xs text-(--ui-text-muted)">
              {{ t('risk.card.seen', { first: formatDate(device.first_seen, locale), last: formatDate(device.last_seen, locale) }) }}
            </p>
            <p
              v-if="device.other_accounts.length"
              class="mt-1 flex flex-wrap items-center gap-x-2 text-xs"
            >
              <span class="text-error">{{ t('risk.card.otherAccounts', device.other_accounts.length) }}</span>
              <NuxtLink
                v-for="other in device.other_accounts"
                :key="other.id"
                :to="riskUserLink(other)"
                class="text-primary hover:underline"
              >
                {{ other.name || other.email || other.id.slice(0, 8) }}
              </NuxtLink>
            </p>
          </li>
        </ul>
      </section>

      <section
        v-if="data.duplicates.length"
        class="space-y-2 text-sm"
      >
        <h3 class="text-sm font-medium">
          {{ t('risk.card.duplicates') }}
        </h3>
        <DuplicateList :duplicates="data.duplicates" />
      </section>

      <section class="space-y-2">
        <h3 class="text-sm font-medium">
          {{ t('risk.card.holds') }}
        </h3>
        <RiskHoldList
          :holds="data.holds"
          @changed="() => refresh()"
        />
      </section>

      <section
        v-if="data.blocked.length"
        class="space-y-2"
      >
        <h3 class="text-sm font-medium">
          {{ t('risk.card.blocked') }}
        </h3>
        <ul class="divide-y divide-(--ui-border) text-sm">
          <li
            v-for="item in data.blocked"
            :key="item.id"
            class="flex flex-wrap items-center gap-2 py-2"
          >
            <UBadge
              color="error"
              variant="outline"
              size="sm"
            >
              {{ label(blockedKindKey(item.kind), item.kind) }}
            </UBadge>
            <span class="min-w-0 flex-1 break-words">{{ item.reason }}</span>
            <span class="text-xs text-(--ui-text-muted)">{{ item.created_by_name || '—' }} · {{ formatDate(item.created_at, locale) }}</span>
          </li>
        </ul>
      </section>
    </div>

    <RiskBanModal
      v-if="data"
      v-model:open="banOpen"
      :user-id="userId"
      :name="data.user.name"
      @banned="banned"
    />
  </UCard>
</template>
