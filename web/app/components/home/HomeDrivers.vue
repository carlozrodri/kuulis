<script setup lang="ts">
// For drivers (docs/website-redesign/03 §5.4): the strongest difference as a number, on the ink field. The cap and
// the fee table come from GET /public/site; without them the text leaves the figure out (04 §8).
import type { PublicSite } from '~/utils/types'

const props = defineProps<{ site: PublicSite | null, freeMonths: number }>()
const { t } = useI18n()
const max = computed(() => maxFee(props.site?.fee_tiers))
</script>

<template>
  <section
    v-reveal
    class="drivers band-ink"
  >
    <div class="container-wide grid-drivers">
      <div class="copy">
        <p
          class="zero"
          aria-hidden="true"
        >
          {{ t('home.drivers.zero') }}
        </p>
        <BrandHeadline :text="t('home.drivers.title')" />
        <p class="body">
          {{ max === null
            ? t('home.drivers.bodyNoMax', { months: freeMonths })
            : t('home.drivers.body', { max: usd(max), months: freeMonths }) }}
        </p>
        <NuxtLinkLocale
          to="/motorizados"
          class="btn btn-primary"
        >
          {{ t('home.drivers.cta') }}
        </NuxtLinkLocale>
      </div>
      <div
        v-if="site?.fee_tiers?.length"
        class="card fees"
      >
        <h3>{{ t('home.drivers.tableTitle') }}</h3>
        <FeeTable :tiers="site.fee_tiers" />
        <p class="note">
          {{ t('home.drivers.tableNote', { months: freeMonths }) }}
        </p>
      </div>
    </div>
  </section>
</template>

<style scoped>
.drivers {
  padding: var(--section-y) 0;
}

.grid-drivers {
  display: grid;
  gap: var(--space-7);
  align-items: center;
}

.zero {
  margin: 0 0 var(--space-2);
  color: var(--accent);
  font-size: var(--font-number);
  font-weight: 800;
  line-height: 0.9;
  letter-spacing: -0.06em;
}

.copy :deep(h2) {
  max-width: 16ch;
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

.fees {
  color: var(--text);
}

.fees h3 {
  margin: 0 0 var(--space-4);
}

.note {
  margin: var(--space-4) 0 0;
  color: var(--muted);
  font-size: var(--font-small);
}

@media (min-width: 960px) {
  .grid-drivers {
    grid-template-columns: 7fr 5fr;
    column-gap: var(--space-9);
  }
}
</style>
