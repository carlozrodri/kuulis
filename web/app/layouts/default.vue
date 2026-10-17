<script setup lang="ts">
const { t } = useI18n()
// Open mobile menu: the rest of the page is inert (not focusable, hidden from screen readers).
const menuOpen = ref(false)
</script>

<template>
  <div class="page">
    <a
      href="#main"
      class="sr-only"
    >{{ t('nav.skip') }}</a>
    <SiteHeader v-model:open="menuOpen" />
    <main
      id="main"
      :inert="menuOpen || undefined"
    >
      <slot />
    </main>
    <SiteFooter :inert="menuOpen || undefined" />
  </div>
</template>

<style scoped>
.page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

main {
  flex: 1;
}
</style>
