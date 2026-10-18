<script setup lang="ts">
// A poster headline (Kuulis de noche): condensed Archivo in capitals, and a final full stop drawn as the brand dot,
// yellow on night, green or photo fields and green on light ones (yellow on light has no contrast). Screen readers
// read the plain text, full stop included.
const props = withDefaults(defineProps<{ text: string, as?: 'h1' | 'h2' | 'h3' }>(), { as: 'h2' })
// The last two words stay together on longer headlines, so none ends on a lone word ("What you earn is / yours."),
// unless together they are too wide for a phone in poster type.
const keepLastPair = (text: string) => {
  const words = text.split(' ')
  return words.length > 3 && words.slice(-2).join(' ').length <= 12 ? text.replace(/ (\S+)$/, '\u00A0$1') : text
}
const parts = computed(() => {
  const dot = props.text.endsWith('.')
  const body = keepLastPair(dot ? props.text.slice(0, -1) : props.text)
  // The dot is a box, and a line may break before a box: the last word and the dot go in one unbreakable span.
  const cut = body.lastIndexOf(' ') + 1
  return { head: body.slice(0, cut), last: body.slice(cut), dot }
})
</script>

<template>
  <component
    :is="as"
    class="headline"
  >
    {{ parts.head }}<span class="last">{{ parts.last }}<span
      v-if="parts.dot"
      class="dot"
    >.</span></span>
  </component>
</template>

<style scoped>
.headline {
  font-family: var(--font-poster);
  font-weight: 900;
  font-stretch: 66%;
  text-transform: uppercase;
}

.last {
  white-space: nowrap;
}

/* The glyph stays for copy and screen readers; what shows is a round dot sitting on the baseline. */
.dot {
  display: inline-block;
  width: 0.2em;
  height: 0.2em;
  margin-left: 0.05em;
  border-radius: 50%;
  background: var(--primary);
  color: transparent;
  line-height: 0;
  vertical-align: baseline;
  overflow: hidden;
}

:is(.band-brand, .band-ink, .band-photo) .dot {
  background: var(--accent);
}
</style>
