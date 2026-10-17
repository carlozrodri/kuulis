<script setup lang="ts">
// A headline whose final full stop is the brand dot (docs/website-redesign/02 §1): yellow on green or ink, green
// on light backgrounds (yellow on light has no contrast). Screen readers read the plain text.
const props = withDefaults(defineProps<{ text: string, as?: 'h1' | 'h2' | 'h3' }>(), { as: 'h2' })
const parts = computed(() => (props.text.endsWith('.') ? { body: props.text.slice(0, -1), dot: true } : { body: props.text, dot: false }))
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
