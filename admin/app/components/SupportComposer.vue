<script setup lang="ts">
import type { CannedResponse, ReplyThen, ReportAdminDetail, ReportReplyInput } from '~/types/api'
import { REPLY_THEN } from '~/types/api'

/**
 * Answer to the user (doc 13): saved replies, up to four photos and what happens to the ticket after sending.
 * The user gets a push (an e-mail for web tickets); `{nombre}` and `{viaje}` are filled in by the API.
 */
const props = defineProps<{ reportId: string, recipient: string, web?: boolean }>()
const emit = defineEmits<{ sent: [detail: ReportAdminDetail | null] }>()

const { t } = useI18n()
const { request } = useApi()
const { upload } = useUpload()
const toast = useToast()
const apiError = useApiError()

const body = ref('')
const then = ref<ReplyThen>('wait_user')
const cannedId = ref<string | null>(null)
const cannedTags = ref<string[]>([])

// ---- Saved replies -----------------------------------------------------------------------------

const { data: canned, status: cannedStatus } = useAsyncData('support-canned-picker', () => request<CannedResponse[]>('/admin/support/canned'), { lazy: true })
const cannedItems = computed(() =>
  (canned.value ?? []).map(item => ({
    label: item.title,
    value: item.id,
    suffix: item.locale.toUpperCase(),
  })),
)
const cannedPick = ref<string | undefined>(undefined)
watch(cannedPick, (id) => {
  if (!id) return
  const item = canned.value?.find(c => c.id === id)
  cannedPick.value = undefined
  if (!item) return
  body.value = body.value.trim() ? `${body.value.trimEnd()}\n\n${item.body}` : item.body
  cannedId.value = item.id
  cannedTags.value = item.tags
  then.value = thenFromAction(item.action)
})
watch(body, (value) => {
  if (!value.trim()) {
    cannedId.value = null
    cannedTags.value = []
  }
})
const cannedTitle = computed(() => canned.value?.find(c => c.id === cannedId.value)?.title ?? null)

// ---- Photos ------------------------------------------------------------------------------------

interface Photo { id: number, name: string, preview: string, key: string | null, failed: boolean }
const photos = ref<Photo[]>([])
const fileInput = ref<HTMLInputElement | null>(null)
let nextId = 0
const uploading = computed(() => photos.value.some(p => !p.key && !p.failed))

async function onFiles(event: Event) {
  const input = event.target as HTMLInputElement
  const files = [...(input.files ?? [])]
  input.value = ''
  for (const file of files) {
    if (photos.value.length >= MAX_ATTACHMENTS) {
      toast.add({ title: t('support.composer.tooManyPhotos', { n: MAX_ATTACHMENTS }), color: 'warning' })
      break
    }
    if (!isAllowedAttachment(file)) {
      toast.add({ title: t('support.composer.onlyImages'), color: 'warning' })
      continue
    }
    const photo: Photo = { id: nextId++, name: file.name, preview: URL.createObjectURL(file), key: null, failed: false }
    photos.value.push(photo)
    try {
      const key = await upload(file)
      const current = photos.value.find(p => p.id === photo.id)
      if (current) current.key = key
    }
    catch (err) {
      const current = photos.value.find(p => p.id === photo.id)
      if (current) current.failed = true
      toast.add({ title: apiError(err), color: 'error' })
    }
  }
}
function removePhoto(id: number) {
  const photo = photos.value.find(p => p.id === id)
  if (photo) URL.revokeObjectURL(photo.preview)
  photos.value = photos.value.filter(p => p.id !== id)
}
onBeforeUnmount(() => photos.value.forEach(p => URL.revokeObjectURL(p.preview)))

// ---- Send --------------------------------------------------------------------------------------

const thenItems = computed(() => REPLY_THEN.map(value => ({ label: t(`support.composer.then.${value}`), value })))
const sending = ref(false)
const canSend = computed(() => !!body.value.trim() && body.value.length <= REPLY_MAX && !uploading.value && !sending.value)

async function send() {
  if (!canSend.value) return
  sending.value = true
  const payload: ReportReplyInput = {
    body: body.value.trim(),
    then: then.value,
    ...(photos.value.some(p => p.key) ? { attachments: photos.value.filter(p => p.key).map(p => p.key!) } : {}),
    ...(cannedId.value ? { canned_response_id: cannedId.value } : {}),
    ...(cannedTags.value.length ? { add_tags: cannedTags.value } : {}),
  }
  try {
    const detail = await request<ReportAdminDetail>(`/admin/reports/${props.reportId}/messages`, { method: 'POST', body: payload })
    toast.add({ title: t(then.value === 'resolve' ? 'support.composer.sentResolved' : 'support.composer.sent'), color: 'success' })
    photos.value.forEach(p => URL.revokeObjectURL(p.preview))
    photos.value = []
    body.value = ''
    then.value = 'wait_user'
    emit('sent', detail ?? null)
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    sending.value = false
  }
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
    event.preventDefault()
    send()
  }
}
</script>

<template>
  <form
    class="space-y-3"
    @submit.prevent="send"
  >
    <div class="flex flex-wrap items-center justify-between gap-2">
      <p class="text-sm text-(--ui-text-muted)">
        <UIcon
          :name="web ? 'i-lucide-mail' : 'i-lucide-bell'"
          class="mr-1 align-middle"
        />{{ t(web ? 'support.composer.toEmail' : 'support.composer.toPush', { name: recipient }) }}
      </p>
      <USelectMenu
        v-model="cannedPick"
        :items="cannedItems"
        value-key="value"
        :loading="cannedStatus === 'pending'"
        :placeholder="t('support.composer.canned')"
        :search-input="{ placeholder: t('support.composer.cannedSearch') }"
        icon="i-lucide-message-square-quote"
        size="sm"
        class="w-64"
      >
        <template #empty>
          <span class="text-sm">{{ t('support.composer.cannedEmpty') }}</span>
        </template>
      </USelectMenu>
    </div>
    <UTextarea
      v-model="body"
      class="w-full"
      :rows="4"
      autoresize
      :maxrows="14"
      :maxlength="REPLY_MAX"
      :placeholder="t('support.composer.placeholder')"
      :aria-label="t('support.composer.label')"
      @keydown="onKeydown"
    />
    <p
      v-if="cannedTitle"
      class="text-xs text-(--ui-text-muted)"
    >
      <UIcon
        name="i-lucide-message-square-quote"
        class="mr-1 align-middle"
      />{{ t('support.composer.usingCanned', { title: cannedTitle }) }}
    </p>

    <div
      v-if="photos.length"
      class="flex flex-wrap gap-2"
    >
      <div
        v-for="photo in photos"
        :key="photo.id"
        class="relative size-20 overflow-hidden rounded-md border border-(--ui-border)"
        :class="photo.failed ? 'ring-2 ring-error' : ''"
      >
        <img
          :src="photo.preview"
          :alt="photo.name"
          class="size-full object-cover"
          :class="photo.key ? '' : 'opacity-50'"
        >
        <UIcon
          v-if="!photo.key && !photo.failed"
          name="i-lucide-loader-circle"
          class="absolute inset-0 m-auto size-6 animate-spin"
        />
        <UButton
          icon="i-lucide-x"
          size="xs"
          color="neutral"
          variant="solid"
          class="absolute top-1 right-1"
          :aria-label="t('support.composer.removePhoto')"
          @click="removePhoto(photo.id)"
        />
      </div>
    </div>

    <div class="flex flex-wrap items-end justify-between gap-3">
      <div class="space-y-2">
        <URadioGroup
          v-model="then"
          :items="thenItems"
          :legend="t('support.composer.thenLabel')"
          orientation="horizontal"
          size="sm"
        />
      </div>
      <div class="flex items-center gap-2">
        <input
          ref="fileInput"
          type="file"
          :accept="ATTACHMENT_TYPES.join(',')"
          multiple
          class="hidden"
          @change="onFiles"
        >
        <UButton
          color="neutral"
          variant="outline"
          icon="i-lucide-image-plus"
          :label="t('support.composer.addPhoto')"
          :disabled="photos.length >= MAX_ATTACHMENTS"
          @click="fileInput?.click()"
        />
        <UButton
          type="submit"
          icon="i-lucide-send"
          :label="t(then === 'resolve' ? 'support.composer.sendResolve' : 'support.composer.send')"
          :disabled="!canSend"
          :loading="sending"
        />
      </div>
    </div>
    <p class="text-xs text-(--ui-text-muted)">
      {{ t('support.composer.hint') }}
    </p>
  </form>
</template>
