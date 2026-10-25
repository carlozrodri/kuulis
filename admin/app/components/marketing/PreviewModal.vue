<script setup lang="ts">
import type { MarketingContentSummary } from '~/types/api'

/** Watches the list's videos one after another, with sound, without opening each piece. */
const props = defineProps<{ items: MarketingContentSummary[] }>()
const current = defineModel<MarketingContentSummary | null>({ required: true })
const { t, locale } = useI18n()

const playable = computed(() => props.items.filter(i => i.preview?.video_url))
const index = computed(() => playable.value.findIndex(i => i.id === current.value?.id))
const open = computed({
  get: () => current.value !== null,
  set: (v) => {
    if (!v) current.value = null
  },
})
function step(n: number) {
  const next = playable.value[index.value + n]
  if (next) current.value = next
}
function onKey(event: KeyboardEvent) {
  if (event.key === 'ArrowRight') step(1)
  else if (event.key === 'ArrowLeft') step(-1)
}
</script>

<template>
  <UModal
    v-model:open="open"
    :title="current?.title ?? ''"
    :description="current ? `${current.code} · ${t(`marketing.statuses.${current.status}`)}` : ''"
    :ui="{ content: 'max-w-md' }"
  >
    <template #body>
      <div
        v-if="current?.preview?.video_url"
        class="space-y-3"
        @keydown="onKey"
      >
        <video
          :key="current.id"
          :src="current.preview.video_url"
          :poster="current.preview.image_url ?? undefined"
          controls
          autoplay
          playsinline
          preload="auto"
          :aria-label="t('marketing.gallery.videoOf', { title: current.title })"
          class="mx-auto aspect-[9/16] max-h-[65vh] w-auto rounded-lg bg-black object-contain"
        />
        <p class="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 text-xs text-(--ui-text-muted)">
          <span v-if="current.preview.duration_s">{{ formatClock(current.preview.duration_s) }}</span>
          <span v-if="current.scheduled_for">{{ formatDay(current.scheduled_for, locale) }}</span>
          <span v-if="current.created_by_agent">{{ t('marketing.byAgent', { agent: current.created_by_agent }) }}</span>
        </p>
      </div>
    </template>
    <template #footer>
      <div class="flex w-full items-center justify-between gap-2">
        <div class="flex gap-1">
          <UButton
            icon="i-lucide-chevron-left"
            color="neutral"
            variant="outline"
            :disabled="index <= 0"
            :aria-label="t('marketing.gallery.previous')"
            @click="step(-1)"
          />
          <UButton
            icon="i-lucide-chevron-right"
            color="neutral"
            variant="outline"
            :disabled="index < 0 || index >= playable.length - 1"
            :aria-label="t('marketing.gallery.next')"
            @click="step(1)"
          />
          <span
            v-if="index >= 0"
            class="self-center px-1 text-xs text-(--ui-text-muted)"
          >{{ index + 1 }} / {{ playable.length }}</span>
        </div>
        <UButton
          v-if="current"
          :to="`/marketing/piezas/${current.id}`"
          icon="i-lucide-arrow-right"
          trailing
          :label="t('marketing.gallery.openPiece')"
        />
      </div>
    </template>
  </UModal>
</template>
