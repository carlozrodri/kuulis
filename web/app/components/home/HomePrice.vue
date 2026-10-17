<script setup lang="ts">
// "Clear price" (Kuulis de noche): one real quote from the app, set as a poster. The figures are an example dated
// in the note below them; the payment methods come from GET /public/site.
defineProps<{ methods: string[] }>()
const { t } = useI18n()
</script>

<template>
  <section class="price">
    <svg
      class="route"
      viewBox="0 0 560 420"
      aria-hidden="true"
    >
      <path d="M20 400 C 120 260, 300 360, 340 220 S 520 120, 540 20" />
    </svg>
    <div
      v-reveal
      class="container-wide inner"
    >
      <p class="eyebrow">
        {{ t('home.eyebrow.price') }}
      </p>
      <BrandHeadline :text="t('home.price.title')" />
      <p class="body">
        {{ t('home.price.body') }}
      </p>
      <p class="amount">
        <span class="sr-only">{{ t('home.price.amountLabel') }}</span><span
          class="currency"
          aria-hidden="true"
        >$</span><span aria-hidden="true">1.80</span>
      </p>
      <dl class="rates">
        <div>
          <dt>{{ t('home.price.trip') }}</dt>
          <dd>{{ t('home.price.tripValue') }}</dd>
        </div>
        <div>
          <dt>{{ t('home.price.bcv') }}</dt>
          <dd>Bs 1.584,21</dd>
        </div>
        <div>
          <dt>{{ t('home.price.binance') }}</dt>
          <dd>Bs 1.812,60</dd>
        </div>
      </dl>
      <PaymentChips
        v-if="methods.length"
        class="pays"
        :methods="methods"
      />
      <p class="note">
        {{ t('home.price.exampleNote') }}
      </p>
    </div>
  </section>
</template>

<style scoped>
.price {
  position: relative;
  overflow: clip;
  padding: var(--section-y) 0;
}

.inner {
  display: grid;
  gap: var(--space-5);
}

.eyebrow {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0;
  color: var(--primary);
  font-size: var(--font-label);
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.eyebrow::before {
  content: '';
  width: 28px;
  height: 2px;
  background: currentcolor;
}

.inner :deep(h2) {
  max-width: 13ch;
  margin: 0;
  font-size: var(--font-h2);
  line-height: var(--leading-heading);
}

.body {
  max-width: 40rem;
  margin: 0;
  color: var(--muted);
  font-size: var(--font-lead);
  line-height: 1.5;
}

.amount {
  display: flex;
  align-items: flex-start;
  margin: var(--space-4) 0 0;
  color: var(--primary);
  font-family: var(--font-poster);
  font-size: clamp(7rem, 2rem + 24vw, 22rem);
  font-weight: 900;
  font-stretch: 62%;
  line-height: 0.8;
  letter-spacing: -0.02em;
  font-variant-numeric: tabular-nums;
}

.currency {
  margin: 0.12em 0.04em 0 0;
  font-size: 0.38em;
}

.rates {
  display: grid;
  margin: 0;
  border-top: 2px solid var(--text);
}

.rates div {
  padding: var(--space-4) 0;
  border-bottom: 1px solid var(--border);
}

dt {
  color: var(--muted);
  font-size: var(--font-label);
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

dd {
  margin: 6px 0 0;
  font-size: clamp(1.4rem, 1rem + 1.6vw, 2.4rem);
  font-weight: 800;
  letter-spacing: -0.03em;
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
}

.note {
  max-width: 60ch;
  margin: 0;
  color: var(--muted);
  font-size: var(--font-small);
}

.route {
  position: absolute;
  top: 60px;
  right: -40px;
  display: none;
  width: 46%;
  max-width: 560px;
}

.route path {
  fill: none;
  stroke: var(--accent);
  stroke-width: 10;
  stroke-linecap: round;
}

@media (min-width: 640px) {
  .rates {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .rates div {
    padding: var(--space-5) var(--space-5) 0 0;
    border-bottom: 0;
  }

  .rates div + div {
    padding-left: var(--space-5);
    border-left: 1px solid var(--border);
  }
}

@media (min-width: 760px) {
  .route {
    display: block;
  }
}

/* Scroll-linked where the browser supports it; everywhere else the number and the route simply sit there. */
@supports (animation-timeline: view()) {
  @media (prefers-reduced-motion: no-preference) {
    .amount {
      animation: amount-in linear both;
      animation-timeline: view();
      animation-range: entry 10% cover 40%;
    }

    .route path {
      stroke-dasharray: 1400;
      animation: route-in linear both;
      animation-timeline: view();
      animation-range: entry 0% cover 60%;
    }
  }
}

@keyframes amount-in {
  from {
    transform: translateX(-10%);
    letter-spacing: 0.06em;
  }
}

@keyframes route-in {
  from {
    stroke-dashoffset: 1400;
  }

  to {
    stroke-dashoffset: 0;
  }
}
</style>
