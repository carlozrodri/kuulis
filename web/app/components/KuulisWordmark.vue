<script setup lang="ts">
withDefaults(defineProps<{ size?: number }>(), { size: 28 })
</script>

<template>
  <span
    class="wordmark"
    :style="{ fontSize: `${size}px` }"
    aria-label="Kuulis"
  >kuulis<span class="dot">.</span></span>
</template>

<style scoped>
.wordmark {
  font-weight: 800;
  letter-spacing: -0.03em;
  line-height: 1;
  color: inherit;
}

.dot {
  color: var(--accent);
}
</style>
