<script setup lang="ts">
import type { HoldRead } from '~/types/api'

/**
 * Releases (pays) or voids a held payment (doc 16), with an optional note. Voiding drops a promotion
 * credit or sends a transfer back to its sender.
 */
const props = defineProps<{ hold: HoldRead | null, action: 'release' | 'void' }>()
const open = defineModel<boolean>('open', { default: false })
const emit = defineEmits<{ done: [hold: HoldRead] }>()

const { t, locale } = useI18n()
const { request } = useApi()
const toast = useToast()
const apiError = useApiError()

const note = ref('')
const busy = ref(false)
watch(open, (value) => {
  if (value) note.value = ''
})

const description = computed(() => {
  const h = props.hold
  if (!h) return ''
  const params = {
    amount: formatUsdt(h.amount, locale.value),
    name: h.user.name || h.user.email || '—',
    sender: h.sender?.name || h.sender?.email || '—',
  }
  return t(`risk.holdModal.${props.action}.${h.kind === 'transfer' ? 'transfer' : 'promo_credit'}`, params)
})

async function submit() {
  const h = props.hold
  if (!h) return
  busy.value = true
  try {
    const body = note.value.trim() ? { note: note.value.trim() } : {}
    const updated = await request<HoldRead>(`/admin/risk/holds/${h.id}/${props.action}`, { method: 'POST', body })
    toast.add({ title: t(`risk.holdModal.${props.action}.done`), color: 'success' })
    open.value = false
    emit('done', updated)
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    busy.value = false
  }
}
</script>

<template>
  <UModal
    v-model:open="open"
    :title="t(`risk.holdModal.${action}.title`)"
    :description="description"
  >
    <template #body>
      <UFormField
        :label="t('risk.note')"
        :help="t('risk.noteHelp')"
      >
        <UTextarea
          v-model="note"
          class="w-full"
          :rows="3"
          :maxlength="RISK_NOTE_MAX"
        />
      </UFormField>
    </template>
    <template #footer>
      <div class="flex w-full justify-end gap-2">
        <UButton
          color="neutral"
          variant="ghost"
          :label="t('common.cancel')"
          @click="open = false"
        />
        <UButton
          :color="action === 'release' ? 'success' : 'error'"
          :icon="action === 'release' ? 'i-lucide-check' : 'i-lucide-undo-2'"
          :label="t(`risk.holds.${action}`)"
          :loading="busy"
          @click="submit"
        />
      </div>
    </template>
  </UModal>
</template>
