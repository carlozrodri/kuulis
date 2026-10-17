<script setup lang="ts">
// The Latin subset of the font, fetched with the HTML instead of after the CSS: text renders in it sooner.
import fontLatin from '@fontsource-variable/plus-jakarta-sans/files/plus-jakarta-sans-latin-wght-normal.woff2?url'

const { locale } = useI18n()
useHead({
  htmlAttrs: { lang: locale },
  link: [{ rel: 'preload', as: 'font', type: 'font/woff2', href: fontLatin, crossorigin: '' }],
})
useLocaleSeo()
</script>

<template>
  <NuxtLayout>
    <NuxtPage />
  </NuxtLayout>
</template>
