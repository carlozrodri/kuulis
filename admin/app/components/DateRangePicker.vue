<script setup lang="ts">
import type { DayRange, RangePreset } from '~/utils/dates'

/**
 * Caracas-day range with presets. Emits a valid range only (custom ranges are checked against the API's
 * limits first); the problem is shown inline otherwise.
 */
const props = defineProps<{ presets: Exclude<RangePreset, 'custom'>[] }>()
const preset = defineModel<RangePreset>('preset', { required: true })
const range = defineModel<DayRange>('range', { required: true })

const { t } = useI18n()

const customFrom = ref(range.value.from)
const customTo = ref(range.value.to)

const items = computed(() => [...props.presets, 'custom' as const].map(value => ({ label: t(`range.presets.${value}`), value })))

const issue = computed(() => (preset.value === 'custom' ? rangeIssue({ from: customFrom.value, to: customTo.value }) : null))

watch(preset, (value) => {
  if (value === 'custom') {
    customFrom.value = range.value.from
    customTo.value = range.value.to
  }
  else {
    range.value = presetRange(value)
  }
})
watch([customFrom, customTo], () => {
  if (preset.value === 'custom' && !issue.value) {
    if (customFrom.value !== range.value.from || customTo.value !== range.value.to) {
      range.value = { from: customFrom.value, to: customTo.value }
    }
  }
})
</script>

<template>
  <div class="flex flex-wrap items-center gap-2">
    <USelect
      v-model="preset"
      :items="items"
      class="w-44"
      :aria-label="t('range.label')"
    />
    <template v-if="preset === 'custom'">
      <UInput
        v-model="customFrom"
        type="date"
        :max="customTo || undefined"
        :aria-label="t('rides.dateFrom')"
        class="w-40"
      >
        <template #leading>
          <span class="text-xs text-(--ui-text-muted)">{{ t('rides.from') }}</span>
        </template>
      </UInput>
      <UInput
        v-model="customTo"
        type="date"
        :min="customFrom || undefined"
        :aria-label="t('rides.dateTo')"
        class="w-40"
      >
        <template #leading>
          <span class="text-xs text-(--ui-text-muted)">{{ t('rides.to') }}</span>
        </template>
      </UInput>
      <span
        v-if="issue"
        class="text-xs text-error"
        role="alert"
      >{{ t(`range.errors.${issue}`, { max: MAX_RANGE_DAYS }) }}</span>
    </template>
    <span
      v-else
      class="text-xs text-(--ui-text-muted)"
    >{{ range.from === range.to ? range.from : `${range.from} → ${range.to}` }}</span>
  </div>
</template>
