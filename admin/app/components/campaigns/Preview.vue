<script setup lang="ts">
import type { CampaignChannel } from '~/types/api'

// Rough look of the campaign on a phone: the push on the lock screen and the row in the inbox.
// English falls back to Spanish, like the app does for a campaign without an English text.
const props = defineProps<{
  titleEs: string
  bodyEs: string
  titleEn?: string | null
  bodyEn?: string | null
  deepLink?: string | null
  channels: CampaignChannel[]
}>()
const { t } = useI18n()

const lang = ref<'es' | 'en'>('es')
const langItems = computed(() => [
  { label: t('control.spanish'), value: 'es' },
  { label: t('control.english'), value: 'en' },
])
const useEnglish = computed(() => lang.value === 'en' && !!props.titleEn?.trim())
const title = computed(() => (useEnglish.value ? props.titleEn! : props.titleEs).trim() || t('campaigns.preview.placeholderTitle'))
const body = computed(() => (useEnglish.value ? props.bodyEn ?? '' : props.bodyEs).trim())
const fallback = computed(() => lang.value === 'en' && !props.titleEn?.trim())
const has = (channel: CampaignChannel) => props.channels.includes(channel)
</script>

<template>
  <div class="space-y-2">
    <div class="flex items-center justify-between gap-2">
      <p class="text-sm font-medium">
        {{ t('campaigns.preview.title') }}
      </p>
      <UTabs
        v-model="lang"
        :items="langItems"
        size="xs"
        :content="false"
      />
    </div>
    <p
      v-if="fallback"
      class="text-xs text-(--ui-text-muted)"
    >
      {{ t('campaigns.preview.fallback') }}
    </p>

    <div class="mx-auto w-full max-w-[300px] rounded-[2.25rem] border-4 border-(--ui-border-accented) bg-(--ui-bg-muted) p-3 shadow-sm">
      <div class="flex items-center justify-between px-3 pb-3 text-[11px] font-medium text-(--ui-text-muted)">
        <span>9:41</span>
        <span class="flex items-center gap-1">
          <UIcon
            name="i-lucide-signal"
            class="size-3"
          />
          <UIcon
            name="i-lucide-wifi"
            class="size-3"
          />
          <UIcon
            name="i-lucide-battery-full"
            class="size-3"
          />
        </span>
      </div>

      <!-- Push on the lock screen -->
      <div
        v-if="has('push')"
        class="rounded-2xl bg-(--ui-bg)/90 p-3 shadow-sm"
      >
        <div class="mb-1 flex items-center gap-2 text-[11px] text-(--ui-text-muted)">
          <span class="flex size-4 items-center justify-center rounded bg-primary text-[9px] font-bold text-white">K</span>
          <span class="font-medium uppercase">Kuulis</span>
          <span class="ml-auto">{{ t('campaigns.preview.now') }}</span>
        </div>
        <p class="text-sm font-semibold break-words">
          {{ title }}
        </p>
        <p
          v-if="body"
          class="line-clamp-4 text-sm break-words whitespace-pre-line"
        >
          {{ body }}
        </p>
      </div>
      <p
        v-else
        class="rounded-2xl border border-dashed border-(--ui-border) p-3 text-center text-xs text-(--ui-text-muted)"
      >
        {{ t('campaigns.preview.noPush') }}
      </p>

      <!-- Inbox row -->
      <div class="mt-6 rounded-2xl bg-(--ui-bg) p-2">
        <p class="px-1 pb-2 text-xs font-semibold">
          {{ t('campaigns.preview.inbox') }}
        </p>
        <div
          v-if="has('inbox') || has('push')"
          class="flex gap-2 rounded-xl bg-primary/5 p-2"
        >
          <span class="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary">
            <UIcon
              name="i-lucide-megaphone"
              class="size-4"
            />
          </span>
          <div class="min-w-0 flex-1">
            <div class="flex items-start gap-1">
              <p class="flex-1 text-sm font-semibold break-words">
                {{ title }}
              </p>
              <span class="mt-1.5 size-2 shrink-0 rounded-full bg-primary" />
            </div>
            <p
              v-if="body"
              class="line-clamp-2 text-xs break-words text-(--ui-text-muted)"
            >
              {{ body }}
            </p>
            <p class="mt-0.5 text-[11px] text-(--ui-text-dimmed)">
              {{ t('campaigns.preview.now') }}
            </p>
          </div>
        </div>
        <p
          v-else
          class="p-2 text-center text-xs text-(--ui-text-muted)"
        >
          {{ t('campaigns.preview.noInbox') }}
        </p>
      </div>
    </div>

    <p
      v-if="props.deepLink?.trim()"
      class="text-xs text-(--ui-text-muted)"
    >
      {{ t('campaigns.preview.opens', { link: props.deepLink.trim() }) }}
    </p>
    <p
      v-if="has('email')"
      class="text-xs text-(--ui-text-muted)"
    >
      {{ t('campaigns.preview.email') }}
    </p>
  </div>
</template>
