<script setup lang="ts">
// The top of an inner page (docs/website-redesign/02 §4): a route stop for context instead of an uppercase label, the
// headline with the brand dot, and an optional lead. Extra content (a search box) goes in the slot.
defineProps<{ title: string, stop?: string, lead?: string }>()
</script>

<template>
  <div class="page-head">
    <p
      v-if="stop"
      class="stop"
    >
      <span
        class="dot"
        aria-hidden="true"
      />{{ stop }}
    </p>
    <BrandHeadline
      as="h1"
      class="title"
      :text="title"
    />
    <p
      v-if="lead"
      class="lead"
    >
      {{ lead }}
    </p>
    <slot />
  </div>
</template>

<style scoped>
.page-head {
  padding: clamp(40px, 7vw, 96px) 0 var(--space-7);
}

.stop {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin: 0 0 var(--space-4);
  font-weight: 700;
}

.dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--bg);
  box-shadow: inset 0 0 0 3px var(--primary);
}

.title {
  max-width: 18ch;
  margin: 0 0 var(--space-5);
  font-size: var(--font-h1);
  line-height: var(--leading-tight);
  letter-spacing: var(--tracking-heading);
}

.lead {
  max-width: 40rem;
  margin: 0;
  color: var(--muted);
  font-size: var(--font-lead);
  line-height: 1.5;
}
</style>
