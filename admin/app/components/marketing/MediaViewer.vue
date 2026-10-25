<script setup lang="ts">
import type { MarketingAsset } from '~/types/api'

/** The piece page's player: the chosen file big, the rest of the videos and images below it. */
const props = defineProps<{ assets: MarketingAsset[] }>()
const selected = defineModel<string | null>({ default: null })
const { t, locale } = useI18n()

const playable = computed(() => playableAssets(props.assets))
const current = computed(() => playable.value.find(a => a.id === selected.value) ?? playable.value[0] ?? null)
const cover = computed(() => playable.value.find(a => a.kind === 'imagen' && a.role === 'portada') ?? null)
</script>

<template>
  <UCard :ui="{ body: 'space-y-3 p-3 sm:p-4' }">
    <div
      v-if="!current"
      class="flex aspect-[9/16] w-full flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-(--ui-border) p-6 text-center text-sm text-(--ui-text-muted)"
    >
      <UIcon
        name="i-lucide-clapperboard"
        class="size-8"
      />
      {{ t('marketing.viewer.empty') }}
    </div>
    <template v-else>
      <video
        v-if="current.kind === 'video'"
        :key="current.id"
        :src="current.download_url!"
        :poster="cover?.download_url ?? undefined"
        controls
        playsinline
        preload="metadata"
        :aria-label="current.filename"
        class="mx-auto aspect-[9/16] max-h-[60vh] w-full rounded-lg bg-black object-contain xl:max-h-[70vh]"
      />
      <img
        v-else
        :key="current.id"
        :src="current.download_url!"
        :alt="current.filename"
        class="mx-auto max-h-[60vh] w-full rounded-lg bg-black object-contain xl:max-h-[70vh]"
      >
      <div class="flex items-start justify-between gap-2">
        <div class="min-w-0">
          <p class="truncate text-sm font-medium">
            {{ current.filename }}
          </p>
          <p class="text-xs text-(--ui-text-muted)">
            {{ t(`marketing.assetRoles.${current.role}`) }} · {{ current.source }}<template v-if="current.model">
              · {{ current.model }}
            </template>
            · {{ formatBytes(current.size, locale) }}
            <template v-if="current.duration_s">
              · {{ formatClock(current.duration_s) }}
            </template>
            · {{ formatDate(current.created_at, locale) }}
          </p>
        </div>
        <UButton
          :to="current.download_url!"
          target="_blank"
          rel="noopener"
          size="sm"
          color="neutral"
          variant="outline"
          icon="i-lucide-download"
          :aria-label="t('marketing.assets.download')"
        />
      </div>

      <div
        v-if="playable.length > 1"
        class="space-y-1.5"
      >
        <p class="text-xs font-medium text-(--ui-text-muted)">
          {{ t('marketing.viewer.others', { n: playable.length }) }}
        </p>
        <ul class="flex gap-2 overflow-x-auto pb-1">
          <li
            v-for="asset in playable"
            :key="asset.id"
            class="shrink-0"
          >
            <button
              type="button"
              class="relative block h-24 w-14 overflow-hidden rounded-md bg-black ring-offset-2 ring-offset-(--ui-bg) focus-visible:ring-2 focus-visible:ring-(--ui-primary) focus-visible:outline-none"
              :class="asset.id === current.id ? 'ring-2 ring-(--ui-primary)' : 'opacity-80 hover:opacity-100'"
              :aria-label="`${asset.filename} · ${t(`marketing.assetRoles.${asset.role}`)}`"
              :aria-pressed="asset.id === current.id"
              @click="selected = asset.id"
            >
              <img
                v-if="asset.kind === 'imagen'"
                :src="asset.download_url!"
                alt=""
                loading="lazy"
                class="size-full object-cover"
              >
              <video
                v-else
                :src="`${asset.download_url}#t=0.5`"
                muted
                preload="metadata"
                aria-hidden="true"
                tabindex="-1"
                class="size-full object-cover"
              />
              <span class="absolute inset-x-0 bottom-0 truncate bg-black/70 px-1 text-[10px] leading-4 text-white">
                {{ t(`marketing.assetRoles.${asset.role}`) }}
              </span>
            </button>
          </li>
        </ul>
      </div>
    </template>
  </UCard>
</template>
