<script setup lang="ts">
// A headline whose final full stop is the brand dot (docs/website-redesign/02 §1): yellow on green or ink, green
// on light backgrounds (yellow on light has no contrast). Screen readers read the plain text.
const props = withDefaults(defineProps<{ text: string, as?: 'h1' | 'h2' | 'h3' }>(), { as: 'h2' })
// The last two words stay together, so no headline ends on a lone word ("What you earn is / yours.").
const keepLastPair = (text: string) => (text.split(' ').length > 2 ? text.replace(/ (\S+)$/, '\u00A0$1') : text)
const parts = computed(() => {
  const dot = props.text.endsWith('.')
  return { body: keepLastPair(dot ? props.text.slice(0, -1) : props.text), dot }
})
</script>

<template>
  <component
    :is="as"
    class="headline"
  >
    {{ parts.body }}<span
      v-if="parts.dot"
      class="dot"
    >.</span>
  </component>
</template>

<style scoped>
.dot {
  color: var(--primary);
}

:is(.band-brand, .band-ink) .dot {
  color: var(--accent);
}
</style>
