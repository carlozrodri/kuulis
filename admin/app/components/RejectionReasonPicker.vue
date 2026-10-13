<script setup lang="ts">
import type { RejectionReason } from '~/utils/verification'

// Predefined reasons fill the text the driver receives (it can still be edited); "Otro" is free text.
defineProps<{ reasons: RejectionReason[] }>()
const text = defineModel<string>({ required: true })

const { t } = useI18n()
const selected = ref<RejectionReason | null>(null)

function pick(reason: RejectionReason) {
  selected.value = reason
  text.value = reason === 'other' ? '' : t(`verification.reasons.${reason}`)
}
</script>

<template>
  <div class="space-y-3">
    <div class="flex flex-wrap gap-2">
      <UButton
        v-for="reason in reasons"
        :key="reason"
        size="xs"
        :color="selected === reason ? 'error' : 'neutral'"
        :variant="selected === reason ? 'soft' : 'outline'"
        :label="t(`verification.reasonLabels.${reason}`)"
        @click="pick(reason)"
      />
    </div>
    <UFormField
      :label="t('drivers.reason')"
      :help="t('drivers.reasonHelp')"
      required
    >
      <UTextarea
        v-model="text"
        class="w-full"
        :rows="3"
        maxlength="500"
        :placeholder="t('verification.reasonPlaceholder')"
      />
    </UFormField>
  </div>
</template>
