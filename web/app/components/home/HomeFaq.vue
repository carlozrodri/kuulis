<script setup lang="ts">
// Frequently asked questions (docs/website-redesign/03 §5.6), as <details> so they open without JavaScript. The
// driver answer quotes the minimum age and bike year from GET /public/site, or leaves them out without it.
import type { PublicSite } from '~/utils/types'

const props = defineProps<{ site: PublicSite | null }>()
const { t } = useI18n()

const driverAnswer = computed(() => {
  const age = props.site?.driver.min_age
  const year = props.site?.driver.vehicle_min_year?.moto
  return age && year ? t('home.faq.driver.a', { age, year }) : t('home.faq.driver.aNoData')
})
const items = computed(() => [
  ...['commission', 'pay', 'store', 'iphone'].map(key => ({ key, q: t(`home.faq.${key}.q`), a: t(`home.faq.${key}.a`) })),
  { key: 'driver', q: t('home.faq.driver.q'), a: driverAnswer.value },
])
</script>

<template>
  <section class="section faq">
    <div class="container narrow">
      <BrandHeadline :text="t('home.faq.title')" />
      <details
        v-for="item in items"
        :key="item.key"
      >
        <summary>{{ item.q }}</summary>
        <p>{{ item.a }}</p>
      </details>
      <p class="more">
        {{ t('home.faq.more') }}
        <NuxtLinkLocale to="/ayuda">
          {{ t('home.faq.moreLink') }}
        </NuxtLinkLocale>
      </p>
    </div>
  </section>
</template>

<style scoped>
.faq {
  padding: var(--section-y) 0;
}

.faq :deep(h2) {
  margin: 0 0 var(--space-6);
  font-size: var(--font-h2);
  letter-spacing: var(--tracking-heading);
}

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

.more {
  margin-top: var(--space-6);
}

.more a {
  color: var(--primary);
  font-weight: 700;
}
</style>
