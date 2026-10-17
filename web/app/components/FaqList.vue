<script setup lang="ts">
// Questions as <details>, so they open without JavaScript (docs/website-redesign/04 §5).
defineProps<{ items: { key: string, q: string, a: string }[] }>()
</script>

<template>
  <div class="faq-list">
    <details
      v-for="item in items"
      :key="item.key"
    >
      <summary>{{ item.q }}</summary>
      <p>{{ item.a }}</p>
    </details>
  </div>
</template>

<style scoped>
details {
  border-top: 1px solid var(--border);
}

details:last-of-type {
  border-bottom: 1px solid var(--border);
}

summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  min-height: 56px;
  padding: var(--space-4) 0;
  font-size: 1.125rem;
  font-weight: 700;
  cursor: pointer;
  list-style: none;
}

summary::-webkit-details-marker {
  display: none;
}

/* A plus that turns into a minus. */
summary::after {
  content: '+';
  flex: none;
  color: var(--primary);
  font-size: 1.5rem;
  font-weight: 700;
  line-height: 1;
}

details[open] summary::after {
  content: '−';
}

details p {
  margin: 0;
  padding: 0 0 var(--space-5);
  color: var(--muted);
  max-width: 62ch;
}
</style>
