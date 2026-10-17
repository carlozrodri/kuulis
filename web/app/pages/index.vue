<script setup lang="ts">
// Home page (docs/website-redesign/03 §5): one job per section, from the green hero to the green download.
const { t } = useI18n()
const { data: site } = await useSite()
// The header wears the hero's green until the hero scrolls past, and the footer's Ávila rises from the last
// green section (SiteHeader, SiteFooter).
definePageMeta({ heroHeader: true, endsOnBrand: true })

useSeoMeta({
  title: () => t('home.metaTitle'),
  description: () => t('home.metaDescription'),
  ogTitle: () => t('home.metaTitle'),
  ogDescription: () => t('home.metaDescription'),
})

const freeMonths = computed(() => site.value?.free_months ?? 3)
const cities = computed(() => site.value?.cities ?? ['Caracas'])
const paymentMethods = computed(() => site.value?.payment_methods ?? [])
</script>

<template>
  <div>
    <HomeHero />
    <HomePrice :methods="paymentMethods" />
    <HomeHow :cities="cities" />
    <HomeDrivers
      :site="site ?? null"
      :free-months="freeMonths"
    />
    <HomeSafety />
    <HomeFaq :site="site ?? null" />
    <HomeDownload />
  </div>
</template>
