<script setup lang="ts">
// The payment methods the app offers, from GET /public/site (docs/website-redesign/03 §5.2): never written by hand.
defineProps<{ methods: string[] }>()
const { t, te } = useI18n()
</script>

<template>
  <ul class="chips">
    <li
      v-for="method in methods"
      :key="method"
    >
      {{ te(`payments.${method}`) ? t(`payments.${method}`) : method }}
    </li>
  </ul>
</template>

<style scoped>
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin: 0;
  padding: 0;
  list-style: none;
}

li {
  padding: 6px 14px;
  border-radius: var(--radius-pill);
  background: var(--surface-alt);
  font-size: var(--font-small);
  font-weight: 600;
}
</style>
