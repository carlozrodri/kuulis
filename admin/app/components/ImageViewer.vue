<script setup lang="ts">
// Document photo with zoom, rotation and drag to pan (CSS transforms). PDFs and HEIC open in a new
// tab: the CSP does not allow framing the storage links and browsers cannot draw HEIC.
const props = withDefaults(defineProps<{
  src: string | null | undefined
  contentType: string
  alt: string
  /** Highlighted when the keyboard shortcuts act on this viewer. */
  active?: boolean
  height?: string
}>(), { active: false, height: 'h-[60vh]' })

const zoom = defineModel<number>('zoom', { default: 1 })
const rotation = defineModel<number>('rotation', { default: 0 })

const { t } = useI18n()

const previewable = computed(() => !!props.src && isPreviewableImage(props.contentType))
const failed = ref(false)
const offset = reactive({ x: 0, y: 0 })

watch(() => props.src, () => {
  failed.value = false
  offset.x = 0
  offset.y = 0
})
watch(zoom, (value) => {
  if (value <= 1) {
    offset.x = 0
    offset.y = 0
  }
})

const transform = computed(() => `translate(${offset.x}px, ${offset.y}px) scale(${zoom.value}) rotate(${rotation.value}deg)`)

let drag: { x: number, y: number, ox: number, oy: number } | null = null
function onPointerDown(event: PointerEvent) {
  if (zoom.value <= 1) return
  drag = { x: event.clientX, y: event.clientY, ox: offset.x, oy: offset.y }
  ;(event.currentTarget as HTMLElement).setPointerCapture(event.pointerId)
}
function onPointerMove(event: PointerEvent) {
  if (!drag) return
  offset.x = drag.ox + event.clientX - drag.x
  offset.y = drag.oy + event.clientY - drag.y
}
function onPointerUp() {
  drag = null
}
function onWheel(event: WheelEvent) {
  if (!previewable.value) return
  event.preventDefault()
  zoom.value = zoomBy(zoom.value, event.deltaY < 0 ? 1 : -1)
}

function reset() {
  zoom.value = 1
  rotation.value = 0
  offset.x = 0
  offset.y = 0
}
defineExpose({ reset })
</script>

<template>
  <div
    class="flex flex-col overflow-hidden rounded-md border bg-(--ui-bg-elevated)"
    :class="active ? 'border-primary ring-1 ring-primary' : 'border-(--ui-border)'"
  >
    <div
      class="relative flex items-center justify-center overflow-hidden select-none"
      :class="[height, previewable && zoom > 1 ? 'cursor-grab active:cursor-grabbing' : '']"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointercancel="onPointerUp"
      @wheel="onWheel"
    >
      <img
        v-if="previewable && !failed"
        :src="src!"
        :alt="alt"
        draggable="false"
        class="max-h-full max-w-full object-contain transition-transform duration-100"
        :style="{ transform }"
        @error="failed = true"
      >
      <div
        v-else
        class="flex flex-col items-center gap-2 p-4 text-center text-(--ui-text-muted)"
      >
        <UIcon
          :name="contentType === 'application/pdf' ? 'i-lucide-file-text' : 'i-lucide-file-image'"
          class="size-12"
        />
        <span class="text-sm">{{ src ? t('verification.viewer.noPreview') : t('drivers.documents.unavailable') }}</span>
        <UButton
          v-if="src"
          :to="src"
          target="_blank"
          rel="noopener noreferrer"
          icon="i-lucide-external-link"
          size="sm"
          color="neutral"
          variant="outline"
          :label="t('drivers.documents.openNewTab')"
        />
      </div>
    </div>
    <div
      v-if="previewable && !failed"
      class="flex items-center gap-1 border-t border-(--ui-border) bg-(--ui-bg) p-1"
    >
      <UButton
        icon="i-lucide-zoom-out"
        size="xs"
        color="neutral"
        variant="ghost"
        :aria-label="t('verification.viewer.zoomOut')"
        :title="t('verification.viewer.zoomOut')"
        @click="zoom = zoomBy(zoom, -1)"
      />
      <span class="w-12 text-center text-xs tabular-nums text-(--ui-text-muted)">{{ Math.round(zoom * 100) }}%</span>
      <UButton
        icon="i-lucide-zoom-in"
        size="xs"
        color="neutral"
        variant="ghost"
        :aria-label="t('verification.viewer.zoomIn')"
        :title="t('verification.viewer.zoomIn')"
        @click="zoom = zoomBy(zoom, 1)"
      />
      <UButton
        icon="i-lucide-rotate-cw"
        size="xs"
        color="neutral"
        variant="ghost"
        :aria-label="t('verification.viewer.rotate')"
        :title="t('verification.viewer.rotate')"
        @click="rotation = rotateBy(rotation)"
      />
      <UButton
        icon="i-lucide-maximize"
        size="xs"
        color="neutral"
        variant="ghost"
        :aria-label="t('verification.viewer.reset')"
        :title="t('verification.viewer.reset')"
        @click="reset"
      />
      <div class="flex-1" />
      <UButton
        :to="src!"
        target="_blank"
        rel="noopener noreferrer"
        icon="i-lucide-external-link"
        size="xs"
        color="neutral"
        variant="ghost"
        :aria-label="t('drivers.documents.openNewTab')"
        :title="t('drivers.documents.openNewTab')"
      />
    </div>
  </div>
</template>
