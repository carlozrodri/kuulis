<script setup lang="ts">
import type { HoldRead } from '~/types/api'

/** Held payments (doc 16) as a compact list, with Liberar / Anular for risk.manage. */
defineProps<{ holds: HoldRead[], empty?: string }>()
const emit = defineEmits<{ changed: [hold: HoldRead] }>()

const { t, te, locale } = useI18n()
const auth = useAuth()
const canManage = computed(() => auth.can('risk.manage'))
const label = (key: string, fallback: string) => (te(key) ? t(key) : fallback)

const modalOpen = ref(false)
const action = ref<'release' | 'void'>('release')
const current = ref<HoldRead | null>(null)
function act(hold: HoldRead, value: 'release' | 'void') {
  current.value = hold
  action.value = value
  modalOpen.value = true
}
</script>

<template>
  <div>
    <p
      v-if="!holds.length"
      class="text-sm text-(--ui-text-muted)"
    >
      {{ empty ?? t('risk.holds.none') }}
    </p>
    <ul
      v-else
      class="divide-y divide-(--ui-border) text-sm"
    >
      <li
        v-for="hold in holds"
        :key="hold.id"
        class="flex flex-wrap items-start justify-between gap-2 py-2"
      >
        <div class="min-w-0">
          <p class="flex flex-wrap items-center gap-2">
            <span class="font-medium tabular-nums">{{ formatUsdt(hold.amount, locale) }}</span>
            <span>{{ label(holdKindKey(hold.kind), hold.kind) }}</span>
            <UBadge
              :color="holdStatusColor(hold.status)"
              variant="subtle"
              size="sm"
            >
              {{ label(`risk.holdStatuses.${hold.status}`, hold.status) }}
            </UBadge>
          </p>
          <p class="text-xs text-(--ui-text-muted)">
            <template v-if="hold.sender">
              <NuxtLink
                :to="riskUserLink(hold.sender)"
                class="hover:underline"
              >{{ hold.sender.name || hold.sender.email }}</NuxtLink> →
            </template>
            <NuxtLink
              :to="riskUserLink(hold.user)"
              class="hover:underline"
            >{{ hold.user.name || hold.user.email }}</NuxtLink>
            · {{ formatDate(hold.created_at, locale) }}
          </p>
          <div
            v-if="hold.reasons.length"
            class="mt-1 flex flex-wrap gap-1"
          >
            <UBadge
              v-for="reason in hold.reasons"
              :key="reason"
              color="neutral"
              variant="outline"
              size="sm"
            >
              {{ label(riskReasonKey(reason), reason) }}
            </UBadge>
          </div>
          <p
            v-if="isHoldOpen(hold) && hold.release_at"
            class="mt-1 text-xs text-(--ui-text-muted)"
          >
            {{ t('risk.holds.releasesAt', { date: formatDate(hold.release_at, locale) }) }}
          </p>
          <p
            v-if="hold.resolved_at"
            class="mt-1 text-xs text-(--ui-text-muted)"
          >
            {{ t('risk.reviewedBy', { name: hold.resolved_by_name || '—', date: formatDate(hold.resolved_at, locale) }) }}
            <template v-if="hold.note">
              · {{ hold.note }}
            </template>
          </p>
        </div>
        <div
          v-if="canManage && isHoldOpen(hold)"
          class="flex gap-2"
        >
          <UButton
            size="xs"
            color="success"
            variant="soft"
            icon="i-lucide-check"
            :label="t('risk.holds.release')"
            @click="act(hold, 'release')"
          />
          <UButton
            size="xs"
            color="error"
            variant="soft"
            icon="i-lucide-undo-2"
            :label="t('risk.holds.void')"
            @click="act(hold, 'void')"
          />
        </div>
      </li>
    </ul>
    <RiskHoldModal
      v-model:open="modalOpen"
      :hold="current"
      :action="action"
      @done="(hold) => emit('changed', hold)"
    />
  </div>
</template>
