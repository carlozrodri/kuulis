<script setup lang="ts">
import type { NuxtError } from '#app'

const props = defineProps<{ error: NuxtError }>()
const { t } = useI18n()
const notFound = computed(() => props.error.statusCode === 404)
useSeoMeta({ title: () => (notFound.value ? t('error.notFound') : t('error.title')), robots: 'noindex' })
</script>

<template>
  <NuxtLayout>
    <section class="error-page">
      <div class="container-wide">
        <p
          class="code"
          aria-hidden="true"
        >
          {{ error.statusCode || 500 }}
        </p>
        <h1>{{ notFound ? t('error.notFound') : t('error.title') }}</h1>
        <p class="body">
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
.error-page {
  padding: clamp(48px, 9vw, 128px) 0 var(--section-y);
}

/* The status code as the page's figure, in the brand green, like the "0 %" on the drivers page. */
.code {
  margin: 0 0 var(--space-4);
  color: var(--primary);
  font-size: var(--font-number);
  font-weight: 800;
  line-height: 0.9;
  letter-spacing: -0.06em;
  font-variant-numeric: tabular-nums;
}

h1 {
  max-width: 18ch;
  margin: 0 0 var(--space-4);
  font-size: var(--font-h1);
  line-height: var(--leading-tight);
  letter-spacing: var(--tracking-heading);
}

.body {
  max-width: 34rem;
  margin: 0 0 var(--space-6);
  color: var(--muted);
  font-size: var(--font-lead);
  line-height: 1.5;
}
</style>
