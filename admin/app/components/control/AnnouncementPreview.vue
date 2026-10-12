<script setup lang="ts">
import type { AnnouncementForm } from '~/utils/control'

// Rough look of the banner in the app, in either language (English falls back to Spanish like the app).
const props = defineProps<{ form: AnnouncementForm }>()
const { t } = useI18n()

const lang = ref<'es' | 'en'>('es')
const langItems = computed(() => [
  { label: t('control.spanish'), value: 'es' },
  { label: t('control.english'), value: 'en' },
])
const pick = (text: { es: string, en: string }) => (lang.value === 'en' && text.en.trim() ? text.en : text.es)

const STYLE_CLASSES = {
  info: 'border-info/40 bg-info/10',
  warning: 'border-warning/40 bg-warning/10',
  promo: 'border-primary/40 bg-primary/10',
} as const
const STYLE_ICONS = {
  info: 'i-lucide-info',
  warning: 'i-lucide-triangle-alert',
  promo: 'i-lucide-sparkles',
} as const
const STYLE_TEXT = { info: 'text-info', warning: 'text-warning', promo: 'text-primary' } as const
</script>

<template>
  <div class="space-y-2">
    <div class="flex items-center justify-between gap-2">
      <p class="text-sm font-medium">
        {{ t('announcements.preview') }}
      </p>
      <UTabs
        v-model="lang"
        :items="langItems"
        size="xs"
        :content="false"
      />
    </div>
    <div class="mx-auto max-w-sm rounded-2xl border border-(--ui-border) bg-(--ui-bg-muted) p-3">
      <div
        class="flex gap-3 rounded-xl border p-3"
        :class="STYLE_CLASSES[props.form.style]"
      >
        <UIcon
          :name="STYLE_ICONS[props.form.style]"
          class="mt-0.5 size-5 shrink-0"
          :class="STYLE_TEXT[props.form.style]"
        />
        <div class="min-w-0 flex-1 space-y-1">
          <p class="font-semibold break-words">
            {{ pick(props.form.title) || t('announcements.previewTitle') }}
          </p>
          <p
            v-if="pick(props.form.body)"
            class="text-sm whitespace-pre-line break-words text-(--ui-text-muted)"
          >
            {{ pick(props.form.body) }}
          </p>
          <UButton
            v-if="props.form.hasCta"
            size="xs"
            :color="props.form.style === 'promo' ? 'primary' : props.form.style"
            variant="solid"
            class="mt-1"
            :label="pick(props.form.ctaLabel) || t('announcements.previewButton')"
          />
        </div>
        <UIcon
          v-if="props.form.dismissible"
          name="i-lucide-x"
          class="size-4 shrink-0 text-(--ui-text-muted)"
        />
      </div>
    </div>
  </div>
</template>
