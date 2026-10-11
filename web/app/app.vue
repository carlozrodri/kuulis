<script setup lang="ts">
const { locale } = useI18n()
const { siteUrl } = useRuntimeConfig().public
useHead({ htmlAttrs: { lang: locale } })
// Link previews (WhatsApp, Telegram) need an absolute image URL.
useSeoMeta({ ogImage: `${siteUrl.replace(/\/$/, '')}/og.png` })
</script>

<template>
  <NuxtLayout>
    <NuxtPage />
  </NuxtLayout>
</template>
