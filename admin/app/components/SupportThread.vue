<script setup lang="ts">
import type { MessageAttachment, ReportMessageAdminRead } from '~/types/api'

/**
 * Ticket conversation (doc 13): the user on the left, the team on the right, automatic lines centered.
 * Photos show as thumbnails and open in the zoomable viewer.
 */
const props = defineProps<{ messages: ReportMessageAdminRead[], userName: string }>()

const { t, locale } = useI18n()

const ordered = computed(() => [...props.messages].sort((a, b) => a.created_at.localeCompare(b.created_at)))

const authorLabel = (message: ReportMessageAdminRead) =>
  message.author_kind === 'staff'
    ? message.author?.name || message.author_name || message.author?.email || t('reports.notes.staff')
    : props.userName

// ---- Photo viewer ------------------------------------------------------------------------------

const viewing = ref<MessageAttachment | null>(null)
const zoom = ref(1)
const rotation = ref(0)
const viewerOpen = computed({
  get: () => viewing.value !== null,
  set: (open: boolean) => {
    if (!open) viewing.value = null
  },
})
function openPhoto(attachment: MessageAttachment) {
  zoom.value = 1
  rotation.value = 0
  viewing.value = attachment
}
</script>

<template>
  <div>
    <p
      v-if="!ordered.length"
      class="text-sm text-(--ui-text-muted)"
    >
      {{ t('support.thread.empty') }}
    </p>
    <ol
      v-else
      class="space-y-4"
    >
      <li
        v-for="message in ordered"
        :key="message.id"
        class="flex"
        :class="{
          'justify-start': messageSide(message.author_kind) === 'left',
          'justify-end': messageSide(message.author_kind) === 'right',
          'justify-center': messageSide(message.author_kind) === 'center',
        }"
      >
        <p
          v-if="message.author_kind === 'system'"
          class="max-w-md text-center text-xs text-(--ui-text-muted) italic"
        >
          <UIcon
            name="i-lucide-info"
            class="mr-1 align-middle"
          />{{ message.body }} · {{ formatDate(message.created_at, locale) }}
        </p>
        <div
          v-else
          class="max-w-[85%] min-w-0 space-y-1 sm:max-w-[75%]"
        >
          <p
            class="text-xs text-(--ui-text-muted)"
            :class="message.author_kind === 'staff' ? 'text-right' : ''"
          >
            <span class="font-medium">{{ authorLabel(message) }}</span> · {{ formatDate(message.created_at, locale) }}
          </p>
          <div
            class="rounded-2xl px-4 py-2 text-sm"
            :class="message.author_kind === 'staff'
              ? 'rounded-tr-sm bg-primary/10 ring-1 ring-primary/25'
              : 'rounded-tl-sm bg-(--ui-bg-elevated)'"
          >
            <p class="whitespace-pre-wrap break-words">
              {{ message.body }}
            </p>
          </div>
          <div
            v-if="message.attachments?.length"
            class="flex flex-wrap gap-2"
            :class="message.author_kind === 'staff' ? 'justify-end' : ''"
          >
            <button
              v-for="(attachment, index) in message.attachments"
              :key="attachment.key"
              type="button"
              class="flex size-20 items-center justify-center overflow-hidden rounded-md border border-(--ui-border) bg-(--ui-bg-elevated) hover:ring-2 hover:ring-primary"
              :aria-label="t('support.thread.openPhoto', { n: index + 1 })"
              @click="openPhoto(attachment)"
            >
              <img
                v-if="isPreviewableImage(contentTypeFromKey(attachment.key))"
                :src="attachment.url"
                :alt="t('support.thread.photo', { n: index + 1 })"
                class="size-full object-cover"
                loading="lazy"
              >
              <UIcon
                v-else
                name="i-lucide-image"
                class="size-6 text-(--ui-text-muted)"
              />
            </button>
          </div>
        </div>
      </li>
    </ol>

    <UModal
      v-model:open="viewerOpen"
      :title="t('support.thread.photoTitle')"
      :ui="{ content: 'sm:max-w-4xl' }"
    >
      <template #body>
        <ImageViewer
          v-if="viewing"
          v-model:zoom="zoom"
          v-model:rotation="rotation"
          :src="viewing.url"
          :content-type="contentTypeFromKey(viewing.key)"
          :alt="t('support.thread.photoTitle')"
          active
        />
      </template>
    </UModal>
  </div>
</template>
