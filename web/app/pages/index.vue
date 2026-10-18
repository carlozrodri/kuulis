<script setup lang="ts">
// Home page (Kuulis de noche): Caracas at night, the price as a poster, the drivers' 0 % and the download.
const { t } = useI18n()
const { data: site } = await useSite()
// The header sits over the hero photo until the hero scrolls past, and the footer's Ávila rises from the last
// night section (SiteHeader, SiteFooter).
definePageMeta({ heroHeader: 'photo', endsOnBrand: true })

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
    <HomeTicker :methods="paymentMethods" />
    <HomeStory :cities="cities" />
    <HomePrice :methods="paymentMethods" />
    <HomeDrivers
      :site="site ?? null"
      :free-months="freeMonths"
    />
    <HomeSafety />
    <HomeFaq :site="site ?? null" />
    <DownloadBand
      :title="t('home.final.title')"
      :body="t('home.final.body')"
    />
  </div>
</template>
