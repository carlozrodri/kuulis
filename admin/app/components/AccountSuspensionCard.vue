<script setup lang="ts">
import type { Suspension, SuspensionRecord } from '~/types/api'

/**
 * Account suspension (phase 1E) of a user: the suspension in force, suspend / lift actions and the history.
 * Not to be confused with the driver-profile suspension of phase 1A (documents and approval).
 */
const props = defineProps<{
  userId: string
  name?: string | null
  /** From UserRead when the page already has it; the history is used otherwise. */
  suspension?: Suspension | null
  /** Staff and admins cannot be suspended (the API answers cannot_suspend_staff). */
  canSuspend?: boolean
}>()
const emit = defineEmits<{ changed: [] }>()

const { t, locale } = useI18n()
const { request } = useApi()
const toast = useToast()
const apiError = useApiError()

const { data: history, status, error, refresh } = useAsyncData(
  `suspensions-${props.userId}`,
  () => request<SuspensionRecord[]>(`/admin/users/${props.userId}/suspensions`),
)

const current = computed<Suspension | null>(() => {
  if (history.value) return currentSuspension(history.value)
  return isSuspensionInForce(props.suspension) ? props.suspension ?? null : null
})

const suspendOpen = ref(false)
const liftOpen = ref(false)
const lifting = ref(false)

async function changed() {
  await refresh()
  emit('changed')
}

async function lift() {
  lifting.value = true
  try {
    await request(`/admin/users/${props.userId}/unsuspend`, { method: 'POST' })
    toast.add({ title: t('suspensions.toast.lifted'), color: 'success' })
    liftOpen.value = false
    await changed()
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    lifting.value = false
  }
}

function recordState(record: SuspensionRecord): 'active' | 'lifted' | 'expired' {
  if (record.lifted_at) return 'lifted'
  return isSuspensionInForce(record) ? 'active' : 'expired'
}
const stateColor = { active: 'error', lifted: 'neutral', expired: 'neutral' } as const
</script>

<template>
  <UCard>
    <template #header>
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div class="flex flex-wrap items-center gap-2">
          <h2 class="font-semibold">
            {{ t('suspensions.title') }}
          </h2>
          <UBadge
            v-if="current"
            color="error"
            variant="solid"
            icon="i-lucide-user-x"
          >
            {{ t('suspensions.suspended') }}
          </UBadge>
          <UBadge
            v-else-if="history"
            color="success"
            variant="subtle"
          >
            {{ t('suspensions.notSuspended') }}
          </UBadge>
        </div>
        <div class="flex gap-2">
          <UButton
            v-if="current"
            icon="i-lucide-user-check"
            color="neutral"
            variant="outline"
            size="sm"
            :label="t('suspensions.lift')"
            @click="liftOpen = true"
          />
          <UButton
            v-if="canSuspend !== false"
            icon="i-lucide-user-x"
            color="error"
            variant="soft"
            size="sm"
            :label="current ? t('suspensions.replace') : t('suspensions.suspend')"
            @click="suspendOpen = true"
          />
        </div>
      </div>
      <p class="mt-1 text-xs text-(--ui-text-muted)">
        {{ t('suspensions.help') }}
      </p>
    </template>

    <div class="space-y-4">
      <UAlert
        v-if="current"
        color="error"
        variant="subtle"
        icon="i-lucide-ban"
        :title="current.until ? t('suspensions.until', { date: formatDate(current.until, locale) }) : t('suspensions.indefinite')"
      >
        <template #description>
          <p class="whitespace-pre-wrap break-words">
            {{ current.reason }}
          </p>
          <p class="mt-1 text-xs">
            {{ t('suspensions.byOn', { name: current.by?.name || current.by?.email || t('suspensions.system'), date: formatDate(current.suspended_at, locale) }) }}
          </p>
        </template>
      </UAlert>

      <UAlert
        v-if="error"
        color="error"
        variant="subtle"
        icon="i-lucide-circle-alert"
        :title="apiError(error)"
      />
      <USkeleton
        v-else-if="status === 'pending' && !history"
        class="h-16"
      />
      <div v-else-if="history">
        <h3 class="mb-2 text-sm font-medium text-(--ui-text-muted)">
          {{ t('suspensions.history') }}
        </h3>
        <p
          v-if="!history.length"
          class="text-sm text-(--ui-text-muted)"
        >
          {{ t('suspensions.noHistory') }}
        </p>
        <ul
          v-else
          class="divide-y divide-(--ui-border) text-sm"
        >
          <li
            v-for="(record, index) in history"
            :key="`${record.suspended_at}-${index}`"
            class="space-y-1 py-2"
          >
            <div class="flex flex-wrap items-center justify-between gap-2">
              <span class="whitespace-nowrap">
                {{ formatDate(record.suspended_at, locale) }} → {{ record.until ? formatDate(record.until, locale) : t('suspensions.indefiniteShort') }}
              </span>
              <UBadge
                :color="stateColor[recordState(record)]"
                variant="subtle"
                size="sm"
              >
                {{ t(`suspensions.states.${recordState(record)}`) }}
              </UBadge>
            </div>
            <p class="whitespace-pre-wrap break-words">
              {{ record.reason }}
            </p>
            <p class="text-xs text-(--ui-text-muted)">
              {{ t('suspensions.by', { name: record.by?.name || record.by?.email || t('suspensions.system') }) }}
              <template v-if="record.lifted_at">
                · {{ t('suspensions.liftedBy', { name: record.lifted_by?.name || record.lifted_by?.email || t('suspensions.system'), date: formatDate(record.lifted_at, locale) }) }}
              </template>
              <template v-if="record.report_id">
                ·
                <NuxtLink
                  :to="`/reports/${record.report_id}`"
                  class="text-primary hover:underline"
                >{{ t('suspensions.fromReport') }}</NuxtLink>
              </template>
            </p>
          </li>
        </ul>
      </div>
    </div>

    <SuspendUserModal
      v-model:open="suspendOpen"
      :user-id="userId"
      :name="name"
      :current="current"
      @suspended="changed"
    />

    <UModal
      v-model:open="liftOpen"
      :title="t('suspensions.liftTitle', { name: name || t('suspensions.thisPerson') })"
      :description="t('suspensions.liftHelp')"
    >
      <template #footer>
        <div class="flex w-full justify-end gap-2">
          <UButton
            color="neutral"
            variant="ghost"
            :label="t('common.cancel')"
            @click="liftOpen = false"
          />
          <UButton
            icon="i-lucide-user-check"
            :label="t('suspensions.lift')"
            :loading="lifting"
            @click="lift"
          />
        </div>
      </template>
    </UModal>
  </UCard>
</template>
