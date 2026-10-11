<script setup lang="ts">
import type { NuxtError } from '#app'

const props = defineProps<{ error: NuxtError }>()
const { t } = useI18n()
const notFound = computed(() => props.error.statusCode === 404)
useSeoMeta({ title: () => (notFound.value ? t('error.notFound') : t('error.title')), robots: 'noindex' })
</script>

<template>
  <NuxtLayout>
    <section class="section">
      <div class="container narrow center">
        <h1>{{ notFound ? t('error.notFound') : t('error.title') }}</h1>
        <p class="muted">
          {{ notFound ? t('error.notFoundBody') : t('error.body') }}
        </p>
        <button
          type="button"
          class="btn btn-primary"
          @click="clearError({ redirect: '/' })"
        >
          {{ t('error.home') }}
        </button>
      </div>
    </section>
  </NuxtLayout>
</template>

<style scoped>
.center {
  text-align: center;
}
</style>
