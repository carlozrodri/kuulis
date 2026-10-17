<script setup lang="ts">
// "Clear price" (docs/website-redesign/03 §5.2): how the fare is set and paid, as rows rather than cards. The
// payment methods come from GET /public/site. The quote screenshot (asset A1) joins this section when it exists.
defineProps<{ methods: string[] }>()
const { t } = useI18n()
</script>

<template>
  <section
    v-reveal
    class="section price"
  >
    <div class="container-wide grid-price">
      <div class="intro">
        <BrandHeadline :text="t('home.price.title')" />
        <p class="body">
          {{ t('home.price.body') }}
        </p>
      </div>
      <ol class="rows">
        <li>
          <h3>{{ t('home.price.rates.title') }}</h3>
          <p>{{ t('home.price.rates.body') }}</p>
        </li>
        <li>
          <h3>{{ t('home.price.pay.title') }}</h3>
          <p>{{ t('home.price.pay.body') }}</p>
          <PaymentChips
            v-if="methods.length"
            :methods="methods"
          />
        </li>
        <li>
          <h3>{{ t('home.price.haggle.title') }}</h3>
          <p>{{ t('home.price.haggle.body') }}</p>
        </li>
      </ol>
    </div>
  </section>
</template>

<style scoped>
.price {
  padding: var(--section-y) 0;
}

.grid-price {
  display: grid;
  gap: var(--space-7);
}

.intro :deep(h2) {
  max-width: 14ch;
  margin: 0 0 var(--space-5);
  font-size: var(--font-h2);
  line-height: var(--leading-heading);
  letter-spacing: var(--tracking-heading);
}

.body {
  max-width: 34rem;
  margin: 0;
  color: var(--muted);
  font-size: var(--font-lead);
  line-height: 1.5;
}

.rows {
  margin: 0;
  padding: 0;
  list-style: none;
  counter-reset: row;
}

.rows li {
  display: grid;
  grid-template-columns: 2.5rem 1fr;
  column-gap: var(--space-4);
  padding: var(--space-5) 0;
  border-top: 1px solid var(--border);
  counter-increment: row;
}

.rows li:last-child {
  border-bottom: 1px solid var(--border);
}

/* The row number, in brand green, instead of an icon or a card. */
.rows li::before {
  content: counter(row, decimal-leading-zero);
  grid-row: span 3;
  color: var(--primary);
  font-weight: 800;
  font-size: var(--font-small);
  font-variant-numeric: tabular-nums;
  line-height: 1.9;
}

.rows h3 {
  margin: 0 0 var(--space-1);
  font-size: var(--font-h3);
  letter-spacing: -0.01em;
}

.rows p {
  margin: 0;
  color: var(--muted);
}

.rows :deep(.chips) {
  margin-top: var(--space-3);
}

@media (min-width: 960px) {
  .grid-price {
    grid-template-columns: 5fr 6fr;
    align-items: start;
    column-gap: var(--space-9);
  }
}
</style>
