<script setup lang="ts">
// The start PIN as a graphic (docs/website-redesign/02 §10): four digits as the app shows them. The digits are an
// example, and say so: every ride gets its own PIN.
defineProps<{ digits: string, label: string, caption: string }>()
</script>

<template>
  <figure class="pin">
    <div
      class="digits"
      role="img"
      :aria-label="`${label}: ${digits.split('').join(' ')}`"
    >
      <span
        v-for="(digit, index) in digits.split('')"
        :key="index"
        aria-hidden="true"
      >{{ digit }}</span>
    </div>
    <figcaption>{{ caption }}</figcaption>
  </figure>
</template>

<style scoped>
.pin {
  margin: 0;
}

.digits {
  display: flex;
  gap: clamp(8px, 2vw, 16px);
}

.digits span {
  display: grid;
  place-items: center;
  width: clamp(56px, 14vw, 88px);
  aspect-ratio: 3 / 4;
  border-radius: var(--radius-sm);
  background: var(--surface);
  box-shadow: inset 0 0 0 2px var(--border);
  font-size: clamp(2rem, 1.4rem + 3vw, 3.25rem);
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  color: var(--text);
}

figcaption {
  margin-top: var(--space-3);
  color: var(--muted);
  font-size: var(--font-small);
}
</style>
