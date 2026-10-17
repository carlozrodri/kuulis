<script setup lang="ts">
// A link to the same page in the other language (redesign M5), query included. It shows the other language's name
// in that language ("English" / "Español"), so its visible text and its accessible name match (WCAG 2.5.3).
// Following it stores the choice in the kuulis_locale cookie, so the root page opens in that language next time.
const { t, locale } = useI18n()
const switchLocalePath = useSwitchLocalePath()
const other = computed(() => (locale.value === 'es' ? 'en' : 'es'))
</script>

<template>
  <NuxtLink
    class="lang"
    :to="switchLocalePath(other)"
    :lang="other"
    :hreflang="other"
  >
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <circle
        cx="12"
        cy="12"
        r="9"
      />
      <path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18" />
    </svg>
    {{ t('nav.otherLanguage') }}
  </NuxtLink>
</template>

<style scoped>
.lang {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  min-height: 44px;
  padding: 0 var(--space-2);
  border-radius: var(--radius-pill);
  color: inherit;
  font-weight: 600;
  font-size: var(--font-small);
  text-decoration: none;
}

svg {
  width: 18px;
  height: 18px;
  fill: none;
  stroke: currentcolor;
  stroke-width: 2;
  stroke-linecap: round;
}

@media (hover: hover) {
  .lang:hover {
    text-decoration: underline;
    text-underline-offset: 3px;
  }
}
</style>
