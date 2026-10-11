<script setup lang="ts">
import type { Span } from '~/utils/markdown'

defineProps<{ spans: Span[] }>()
</script>

<template>
  <template
    v-for="(span, index) in spans"
    :key="index"
  >
    <strong v-if="span.bold">{{ span.text }}</strong>
    <template v-else>
      {{ span.text }}
    </template>
  </template>
</template>
