<script setup lang="ts">
import type { MarketingContentSummary } from '~/types/api'

const props = defineProps<{ item: MarketingContentSummary, compact?: boolean }>()
const { t, locale } = useI18n()
</script>

<template>
  <NuxtLink
    :to="`/marketing/piezas/${props.item.id}`"
    class="block rounded-lg border border-(--ui-border) p-3 transition hover:bg-(--ui-bg-elevated)"
  >
    <div class="flex items-start justify-between gap-2">
      <div class="min-w-0">
        <p class="truncate font-medium">
          {{ props.item.title }}
        </p>
        <p class="font-mono text-xs text-(--ui-text-muted)">
          {{ props.item.code }}
        </p>
      </div>
      <UBadge
        :color="marketingStatusColor[props.item.status]"
        variant="subtle"
        class="shrink-0"
      >
        {{ t(`marketing.statuses.${props.item.status}`) }}
      </UBadge>
    </div>
    <div
      v-if="!props.compact || props.item.platforms.length"
      class="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-(--ui-text-muted)"
    >
      <span
        v-if="props.item.next_post_at"
        class="flex items-center gap-1"
      >
        <UIcon
          name="i-lucide-clock"
          class="size-3.5"
        />
        {{ formatCaracasTime(props.item.next_post_at, locale) }}
      </span>
      <span
        v-for="p in props.item.platforms"
        :key="p"
        class="flex items-center gap-1"
      >
        <UIcon
          :name="platformIcon[p]"
          class="size-3.5"
        />
        {{ platformLabel[p] }}
      </span>
      <span v-if="!props.compact && props.item.pillar">{{ props.item.pillar }}</span>
      <span v-if="!props.compact && props.item.format">· {{ props.item.format }}</span>
    </div>
  </NuxtLink>
</template>
