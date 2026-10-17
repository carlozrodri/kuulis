<script setup lang="ts">
// The last stop (docs/website-redesign/03 §5.7): the download, on the green field where the route ends in the dot.
// Every page that ends with it sets page meta `endsOnBrand`, so the footer's Ávila rises from this field.
defineProps<{ title: string, body: string }>()
const { t } = useI18n()
</script>

<template>
  <section
    v-reveal
    class="download band-brand"
  >
    <div class="container-wide grid-download">
      <div>
        <BrandHeadline :text="title" />
        <p class="body">
          {{ body }}
        </p>
        <NuxtLinkLocale
          to="/descargar"
          class="btn btn-primary"
        >
          {{ t('home.download') }}
        </NuxtLinkLocale>
      </div>
      <BrandRouteLine
        class="art"
        :animate="false"
      />
    </div>
  </section>
</template>

<style scoped>
.download {
  padding: var(--section-y) 0 calc(var(--section-y) + var(--space-6));
}

.grid-download {
  display: grid;
  gap: var(--space-6);
  align-items: center;
}

.grid-download :deep(h2) {
  max-width: 14ch;
  margin: 0 0 var(--space-5);
  font-size: var(--font-h2);
  line-height: var(--leading-heading);
  letter-spacing: var(--tracking-heading);
}

.body {
  max-width: 34rem;
  margin: 0 0 var(--space-6);
  font-size: var(--font-lead);
  line-height: 1.5;
}

.art {
  display: none;
  color: var(--on-band);
}

@media (min-width: 960px) {
  .grid-download {
    grid-template-columns: 7fr 4fr;
  }

  .art {
    display: block;
    max-width: 300px;
    justify-self: end;
  }
}
</style>
