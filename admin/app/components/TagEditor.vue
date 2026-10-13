<script setup lang="ts">
import type { TagCount } from '~/types/api'

/**
 * Ticket / saved reply tags (doc 13): free text normalized to "pago-movil", plus the most used tags as one-click
 * suggestions.
 */
const props = withDefaults(defineProps<{ suggestions?: TagCount[] | null, disabled?: boolean }>(), { suggestions: null, disabled: false })
const tags = defineModel<string[]>({ required: true })

const { t } = useI18n()

const value = computed({
  get: () => tags.value,
  set: (next: string[]) => {
    tags.value = normalizeTags(next).slice(0, TAGS_MAX)
  },
})
const offered = computed(() => (props.suggestions ?? []).filter(item => !tags.value.includes(item.tag)).slice(0, 8))
function add(tag: string) {
  value.value = [...tags.value, tag]
}
</script>

<template>
  <div class="space-y-2">
    <UInputTags
      v-model="value"
      class="w-full"
      :placeholder="t('support.tagPlaceholder')"
      :max-length="TAG_MAX"
      :max="TAGS_MAX"
      :disabled="disabled"
      add-on-blur
      add-on-paste
    />
    <div
      v-if="offered.length && !disabled"
      class="flex flex-wrap items-center gap-1"
    >
      <span class="text-xs text-(--ui-text-muted)">{{ t('support.tagSuggestions') }}</span>
      <UButton
        v-for="item in offered"
        :key="item.tag"
        size="xs"
        color="neutral"
        variant="soft"
        icon="i-lucide-plus"
        :label="item.tag"
        @click="add(item.tag)"
      />
    </div>
  </div>
</template>
