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
      <FaqList :items="items" />
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

.more {
  margin-top: var(--space-6);
}

.more a {
  color: var(--primary);
  font-weight: 700;
}
</style>
