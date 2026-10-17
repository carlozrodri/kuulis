<script setup lang="ts">
// A list of pages to open (help articles, legal texts) as editorial rows with a divider, not a stack of cards
// (docs/website-redesign/02 §3). The whole row is the link.
defineProps<{ items: { key: string, to: string, title: string, meta?: string }[] }>()
</script>

<template>
  <ul class="link-list">
    <li
      v-for="item in items"
      :key="item.key"
    >
      <NuxtLinkLocale :to="item.to">
        <span class="text">
          <span class="title">{{ item.title }}</span>
          <span
            v-if="item.meta"
            class="meta"
          >{{ item.meta }}</span>
        </span>
        <span
          class="arrow"
          aria-hidden="true"
        >→</span>
      </NuxtLinkLocale>
    </li>
  </ul>
</template>

<style scoped>
.link-list {
  margin: 0;
  padding: 0;
  list-style: none;
}

li {
  border-top: 1px solid var(--border);
}

li:last-child {
  border-bottom: 1px solid var(--border);
}

a {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  min-height: 64px;
  padding: var(--space-4) 0;
  color: var(--text);
  text-decoration: none;
}

.text {
  display: grid;
  gap: var(--space-1);
}

.title {
  font-size: 1.125rem;
  font-weight: 700;
}

.meta {
  color: var(--muted);
  font-size: var(--font-small);
}

.arrow {
  flex: none;
  color: var(--primary);
  font-size: 1.25rem;
  font-weight: 700;
  transition: transform var(--dur-base) var(--ease-out);
}

@media (hover: hover) {
  a:hover .title {
    color: var(--primary);
  }

  a:hover .arrow {
    transform: translateX(4px);
  }
}

@media (prefers-reduced-motion: reduce) {
  .arrow {
    transition: none;
  }
}
</style>
