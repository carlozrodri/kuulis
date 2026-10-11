<script setup lang="ts">
import type { AuditEntry, Page } from '~/types/api'

/** "Historial" of a record: the latest audited admin actions on it (admins only). */
const props = defineProps<{ entityType: string, entityId: string }>()

const { t, te, locale } = useI18n()
const { request } = useApi()
const auth = useAuth()

const limit = 10
const { data, status } = await useAsyncData(
  `audit-${props.entityType}-${props.entityId}`,
  () => auth.isAdmin.value
    ? request<Page<AuditEntry>>('/admin/audit', {
        query: { entity_type: props.entityType, entity_id: props.entityId, limit },
      })
    : Promise.resolve(null),
  { watch: [() => props.entityId] },
)
const open = ref<string | null>(null)
const actionLabel = (action: string) => (te(`audit.actions.${action}`) ? t(`audit.actions.${action}`) : action)
</script>

<template>
  <UCard v-if="auth.isAdmin.value">
    <template #header>
      <div class="flex items-center justify-between gap-2">
        <h3 class="font-semibold">
          {{ t('audit.history') }}
        </h3>
        <UButton
          v-if="(data?.total ?? 0) > limit"
          :to="{ path: '/audit', query: { entity_type: entityType, entity_id: entityId } }"
          :label="t('audit.seeAll', { n: data?.total })"
          variant="link"
          size="sm"
        />
      </div>
    </template>
    <p
      v-if="status !== 'pending' && !data?.items.length"
      class="text-sm text-(--ui-text-muted)"
    >
      {{ t('audit.empty') }}
    </p>
    <ul class="divide-y divide-(--ui-border)">
      <li
        v-for="entry in data?.items ?? []"
        :key="entry.id"
        class="py-2"
      >
        <button
          type="button"
          class="flex w-full items-start justify-between gap-3 text-left text-sm"
          @click="open = open === entry.id ? null : entry.id"
        >
          <span>
            <span class="font-medium">{{ actionLabel(entry.action) }}</span>
            <span class="text-(--ui-text-muted)"> · {{ entry.actor_email || t('audit.system') }}</span>
          </span>
          <span class="whitespace-nowrap text-(--ui-text-muted)">{{ formatDate(entry.created_at, locale) }}</span>
        </button>
        <AuditDiff
          v-if="open === entry.id"
          :entry="entry"
          class="mt-2"
        />
      </li>
    </ul>
  </UCard>
</template>
