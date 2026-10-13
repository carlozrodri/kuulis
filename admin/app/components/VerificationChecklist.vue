<script setup lang="ts">
import type { ChecklistItem } from '~/utils/verification'

// Everything must be ticked before "Aprobar" is enabled (doc 12).
const props = defineProps<{ items: ChecklistItem[], disabled?: boolean }>()
const ticked = defineModel<Record<string, boolean>>({ required: true })

const { t } = useI18n()
const done = computed(() => props.items.filter(item => ticked.value[item]).length)

function set(item: string, value: boolean | 'indeterminate') {
  ticked.value = { ...ticked.value, [item]: value === true }
}
</script>

<template>
  <div class="space-y-2">
    <div class="flex items-center justify-between gap-2">
      <h3 class="text-sm font-medium">
        {{ t('verification.checklist.title') }}
      </h3>
      <span
        class="text-xs tabular-nums"
        :class="done === items.length ? 'text-success' : 'text-(--ui-text-muted)'"
      >
        {{ done }} / {{ items.length }}
      </span>
    </div>
    <ul class="space-y-1.5">
      <li
        v-for="(item, index) in items"
        :key="item"
        class="flex items-center gap-2"
      >
        <UKbd
          size="sm"
          class="shrink-0"
        >
          {{ index + 1 }}
        </UKbd>
        <UCheckbox
          :model-value="!!ticked[item]"
          :label="t(`verification.checklist.${item}`)"
          :disabled="disabled"
          @update:model-value="set(item, $event)"
        />
      </li>
    </ul>
  </div>
</template>
