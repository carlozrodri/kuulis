<script setup lang="ts">
import type { Span } from '~/utils/markdown'

defineProps<{ spans: Span[] }>()
const external = (href: string) => /^https?:\/\//i.test(href)
</script>

<template>
  <template
    v-for="(span, index) in spans"
    :key="index"
  >
    <template v-if="span.href">
      <NuxtLink
        v-if="span.href.startsWith('/')"
        :to="span.href"
      >
        <strong v-if="span.bold">{{ span.text }}</strong>
        <template v-else>
          {{ span.text }}
        </template>
      </NuxtLink>
      <a
        v-else
        :href="span.href"
        :target="external(span.href) ? '_blank' : undefined"
        :rel="external(span.href) ? 'noopener noreferrer nofollow' : undefined"
      >
        <strong v-if="span.bold">{{ span.text }}</strong>
        <template v-else>
          {{ span.text }}
        </template>
      </a>
    </template>
    <strong v-else-if="span.bold">{{ span.text }}</strong>
    <template v-else>
      {{ span.text }}
    </template>
  </template>
</template>
