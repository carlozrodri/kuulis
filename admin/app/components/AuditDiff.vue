<script setup lang="ts">
import type { AuditEntry } from '~/types/api'

const props = defineProps<{ entry: AuditEntry }>()
const { t } = useI18n()

const changes = computed(() => auditChanges(props.entry))
const hasBefore = computed(() => props.entry.before !== null)
</script>

<template>
  <div class="space-y-3 text-sm">
    <p v-if="entry.reason">
      <span class="text-(--ui-text-muted)">{{ t('audit.reason') }}:</span> {{ entry.reason }}
    </p>
    <p
      v-if="!changes.length"
      class="text-(--ui-text-muted)"
    >
      {{ t('audit.noDetail') }}
    </p>
    <table
      v-else
      class="w-full table-fixed border-collapse"
    >
      <thead>
        <tr class="text-left text-(--ui-text-muted)">
          <th class="w-1/4 py-1 pr-2 font-normal">
            {{ t('audit.field') }}
          </th>
          <th
            v-if="hasBefore"
            class="py-1 pr-2 font-normal"
          >
            {{ t('audit.before') }}
          </th>
          <th class="py-1 font-normal">
            {{ hasBefore ? t('audit.after') : t('audit.data') }}
          </th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="change in changes"
          :key="change.key"
          class="border-t border-(--ui-border) align-top"
        >
          <td class="py-1 pr-2 font-mono text-xs break-all">
            {{ change.key }}
          </td>
          <td
            v-if="hasBefore"
            class="py-1 pr-2 break-all text-(--ui-error)"
          >
            {{ auditValue(change.before) }}
          </td>
          <td
            class="py-1 break-all"
            :class="hasBefore ? 'text-(--ui-success)' : ''"
          >
            {{ auditValue(change.after) }}
          </td>
        </tr>
      </tbody>
    </table>
    <p class="text-xs text-(--ui-text-dimmed)">
      {{ [entry.ip, entry.request_id, entry.user_agent].filter(Boolean).join(' · ') }}
    </p>
  </div>
</template>
