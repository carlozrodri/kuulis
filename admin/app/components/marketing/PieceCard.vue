<script setup lang="ts">
import type { MarketingContentSummary } from '~/types/api'

const props = defineProps<{ item: MarketingContentSummary }>()
const emit = defineEmits<{ play: [item: MarketingContentSummary] }>()
const { t, locale } = useI18n()

const preview = computed(() => props.item.preview)
const to = computed(() => `/marketing/piezas/${props.item.id}`)

// Videos load only once the card scrolls near the screen: a month of pieces is dozens of files.
const root = ref<HTMLElement | null>(null)
const near = ref(false)
let observer: IntersectionObserver | undefined
onMounted(() => {
  if (!('IntersectionObserver' in window)) {
    near.value = true
    return
  }
  observer = new IntersectionObserver((entries) => {
    if (entries.some(e => e.isIntersecting)) {
      near.value = true
      observer?.disconnect()
    }
  }, { rootMargin: '400px' })
  if (root.value) observer.observe(root.value)
})
onBeforeUnmount(() => observer?.disconnect())

// Without a cover, the first frame stands in for it (#t asks the browser to seek there).
const videoSrc = computed(() => {
  const url = preview.value?.video_url
  if (!url || !near.value) return undefined
  return preview.value?.image_url ? url : `${url}#t=0.5`
})

// Hovering (or focusing) a card plays the clip muted, like a store's video thumbnails; nothing
// moves for people who asked the system for less motion.
const video = ref<HTMLVideoElement | null>(null)
const reducedMotion = ref(false)
onMounted(() => {
  reducedMotion.value = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
})
function startPeek() {
  if (reducedMotion.value || !video.value) return
  video.value.play().catch(() => {})
}
// Agents upload files without their length; the browser reads it once it loads the video.
const loadedDuration = ref<number | null>(null)
const duration = computed(() => preview.value?.duration_s ?? loadedDuration.value)
function onMetadata(event: Event) {
  const d = (event.target as HTMLVideoElement).duration
  if (Number.isFinite(d) && d > 0) loadedDuration.value = d
}
function stopPeek() {
  if (!video.value) return
  video.value.pause()
  video.value.currentTime = preview.value?.image_url ? 0 : 0.5
}

const dateLabel = computed(() => {
  const day = props.item.scheduled_for
  if (!day) return t('marketing.gallery.noDate')
  return new Intl.DateTimeFormat(locale.value, { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'UTC' }).format(new Date(`${day}T00:00:00Z`))
})
</script>

<template>
  <article
    ref="root"
    class="group flex flex-col overflow-hidden rounded-xl border border-(--ui-border) bg-(--ui-bg) transition hover:border-(--ui-border-accented) hover:shadow-md focus-within:ring-2 focus-within:ring-(--ui-primary)"
    @mouseenter="startPeek"
    @mouseleave="stopPeek"
  >
    <div class="relative aspect-[9/16] w-full overflow-hidden bg-(--ui-bg-inverted)/90">
      <video
        v-if="preview?.video_url"
        ref="video"
        :src="videoSrc"
        :poster="preview.image_url ?? undefined"
        muted
        loop
        playsinline
        :preload="preview.image_url ? 'none' : 'metadata'"
        aria-hidden="true"
        tabindex="-1"
        class="size-full object-cover"
        @loadedmetadata="onMetadata"
      />
      <img
        v-else-if="preview?.image_url"
        :src="preview.image_url"
        alt=""
        loading="lazy"
        class="size-full object-cover"
      >
      <div
        v-else
        class="flex size-full flex-col items-center justify-center gap-2 bg-(--ui-bg-elevated) p-4 text-center text-xs text-(--ui-text-muted)"
      >
        <UIcon
          name="i-lucide-clapperboard"
          class="size-8"
        />
        {{ t('marketing.gallery.noMedia') }}
      </div>

      <UBadge
        :color="marketingStatusColor[props.item.status]"
        variant="solid"
        class="absolute top-2 left-2 shadow-sm"
      >
        {{ t(`marketing.statuses.${props.item.status}`) }}
      </UBadge>
      <span
        v-if="duration"
        class="absolute right-2 bottom-2 rounded bg-black/75 px-1.5 py-0.5 font-mono text-xs text-white"
      >
        <span class="sr-only">{{ t('marketing.gallery.duration') }}</span>
        {{ formatClock(duration) }}
      </span>
      <!-- Watch it with sound without leaving the list. -->
      <button
        v-if="preview?.video_url"
        type="button"
        class="absolute inset-0 flex items-center justify-center bg-black/0 transition group-hover:bg-black/10 focus-visible:outline-none"
        :aria-label="t('marketing.gallery.play', { title: props.item.title })"
        @focus="startPeek"
        @blur="stopPeek"
        @click="emit('play', props.item)"
      >
        <span class="flex size-14 items-center justify-center rounded-full bg-black/60 text-white shadow-lg ring-1 ring-white/30 transition group-hover:scale-110 group-hover:bg-(--ui-primary)">
          <UIcon
            name="i-lucide-play"
            class="ms-0.5 size-7"
          />
        </span>
      </button>
    </div>

    <div class="flex flex-1 flex-col gap-1.5 p-3">
      <NuxtLink
        :to="to"
        class="line-clamp-2 text-sm leading-snug font-semibold hover:underline focus-visible:underline focus-visible:outline-none"
      >
        {{ props.item.title }}
      </NuxtLink>
      <p class="font-mono text-xs text-(--ui-text-muted)">
        {{ props.item.code }}
      </p>
      <div class="mt-auto flex flex-wrap items-center gap-x-2.5 gap-y-1 pt-1 text-xs text-(--ui-text-muted)">
        <span class="flex items-center gap-1">
          <UIcon
            name="i-lucide-calendar"
            class="size-3.5"
          />
          <span class="first-letter:uppercase">{{ dateLabel }}</span>
          <template v-if="props.item.next_post_at">· {{ formatCaracasTime(props.item.next_post_at, locale) }}</template>
        </span>
        <span
          v-if="props.item.platforms.length"
          class="flex items-center gap-1"
        >
          <UIcon
            v-for="p in props.item.platforms"
            :key="p"
            :name="platformIcon[p]"
            class="size-3.5"
            :aria-label="platformLabel[p]"
            role="img"
          />
        </span>
        <span
          v-if="props.item.asset_count"
          class="flex items-center gap-1"
        >
          <UIcon
            name="i-lucide-paperclip"
            class="size-3.5"
          />
          {{ t('marketing.gallery.files', props.item.asset_count) }}
        </span>
      </div>
    </div>
  </article>
</template>
