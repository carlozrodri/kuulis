<script setup lang="ts">
// Switches to the other language and remembers it in the kuulis_locale cookie. Shows the other language's
// name in that language ("English" / "Español"), so its visible text and its accessible name match (WCAG 2.5.3).
// With language URLs (redesign M5) this becomes a link to the same page in the other language.
const { t, locale, setLocale } = useI18n()
const other = computed(() => (locale.value === 'es' ? 'en' : 'es'))
</script>

<template>
  <button
    type="button"
    class="lang"
    :lang="other"
    @click="setLocale(other)"
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
  </button>
</template>

<style scoped>
.lang {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  min-height: 44px;
  padding: 0 var(--space-2);
  border: 0;
  border-radius: var(--radius-pill);
  background: transparent;
  color: inherit;
  font: inherit;
  font-weight: 600;
  font-size: var(--font-small);
  cursor: pointer;
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
