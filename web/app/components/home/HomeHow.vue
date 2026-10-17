<script setup lang="ts">
// How it works (docs/website-redesign/03 §5.3): three stops on the route; the last one is where you arrive.
defineProps<{ cities: string[] }>()
const { t } = useI18n()
const stops = computed(() => [1, 2, 3].map(n => ({
  key: `stop${n}`,
  title: t(`home.how.stop${n}.title`),
  body: t(`home.how.stop${n}.body`),
})))
</script>

<template>
  <section
    v-reveal
    class="section how"
  >
    <div class="container-wide">
      <BrandHeadline :text="t('home.how.title')" />
      <RouteStops :items="stops" />
      <p class="cities">
        <strong>{{ t('home.cities') }}</strong> {{ cities.join(' · ') }}
      </p>
    </div>
  </section>
</template>

<style scoped>
.how {
  padding: var(--section-y) 0;
}

.how :deep(h2) {
  margin: 0 0 var(--space-7);
  font-size: var(--font-h2);
  letter-spacing: var(--tracking-heading);
}

.cities {
  margin-top: var(--space-7);
  color: var(--text);
}
</style>
