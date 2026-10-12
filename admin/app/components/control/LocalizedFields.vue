<script setup lang="ts">
import type { Localized } from '~/types/api'

// One text in both app languages: Spanish (required by most screens) and English (the app falls
// back to Spanish when it is empty).
const props = withDefaults(defineProps<{
  label: string
  help?: string
  textarea?: boolean
  disabled?: boolean
  required?: boolean
  maxlength?: number
  rows?: number
}>(), { help: undefined, textarea: false, disabled: false, required: false, maxlength: LOCALIZED_MAX, rows: 3 })

const model = defineModel<Localized>({ required: true })
const { t } = useI18n()
</script>

<template>
  <fieldset class="space-y-2">
    <legend class="text-sm font-medium">
      {{ props.label }}
      <span
        v-if="props.required"
        class="text-error"
      >*</span>
    </legend>
    <div class="grid gap-3 sm:grid-cols-2">
      <UFormField
        :label="t('control.spanish')"
        :ui="{ label: 'text-xs text-(--ui-text-muted)' }"
      >
        <UTextarea
          v-if="props.textarea"
          v-model="model.es"
          :rows="props.rows"
          :maxlength="props.maxlength"
          :disabled="props.disabled"
          autoresize
          class="w-full"
        />
        <UInput
          v-else
          v-model="model.es"
          :maxlength="props.maxlength"
          :disabled="props.disabled"
          class="w-full"
        />
      </UFormField>
      <UFormField
        :label="t('control.english')"
        :ui="{ label: 'text-xs text-(--ui-text-muted)' }"
      >
        <UTextarea
          v-if="props.textarea"
          v-model="model.en"
          :rows="props.rows"
          :maxlength="props.maxlength"
          :disabled="props.disabled"
          :placeholder="t('control.englishFallback')"
          autoresize
          class="w-full"
        />
        <UInput
          v-else
          v-model="model.en"
          :maxlength="props.maxlength"
          :disabled="props.disabled"
          :placeholder="t('control.englishFallback')"
          class="w-full"
        />
      </UFormField>
    </div>
    <p
      v-if="props.help"
      class="text-xs text-(--ui-text-muted)"
    >
      {{ props.help }}
    </p>
  </fieldset>
</template>
