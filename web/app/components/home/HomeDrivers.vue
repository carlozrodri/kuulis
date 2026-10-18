<script setup lang="ts">
// For drivers (Kuulis de noche): the Ávila over Altamira, a 0 % that fills in yellow as it scrolls up, and the
// facts in rows. The cap and the fee table come from GET /public/site; without them the text leaves the figure out.
import type { PublicSite } from '~/utils/types'

const props = defineProps<{ site: PublicSite | null, freeMonths: number }>()
const { t } = useI18n()
const max = computed(() => maxFee(props.site?.fee_tiers))
</script>

<template>
  <section class="drivers band-photo">
    <img
      class="photo"
      src="/img/fotos/caracas-avila-1280.webp"
      srcset="/img/fotos/caracas-avila-768.webp 768w, /img/fotos/caracas-avila-1280.webp 1280w, /img/fotos/caracas-avila-1920.webp 1920w"
      sizes="100vw"
      width="1920"
      height="1440"
      :alt="t('home.drivers.photoAlt')"
      loading="lazy"
      decoding="async"
    >
    <div class="container-wide">
      <p class="eyebrow">
        {{ t('home.eyebrow.drivers') }}
      </p>
      <div class="row">
        <p
          class="zero"
          aria-hidden="true"
        >
          0%
        </p>
        <div
          v-reveal
          class="copy"
        >
          <BrandHeadline :text="t('home.drivers.title')" />
          <p class="body">
            {{ max === null
              ? t('home.drivers.bodyNoMax', { months: freeMonths })
              : t('home.drivers.body', { max: usd(max), months: freeMonths }) }}
          </p>
        </div>
      </div>
      <div class="grid-facts">
        <ul class="facts">
          <li><b>0 %</b>{{ t('home.drivers.factZero') }}</li>
          <li><b>{{ freeMonths }}</b>{{ t('home.drivers.factFree') }}</li>
          <li><b>$0</b>{{ t('home.drivers.factIdle') }}</li>
        </ul>
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
      <NuxtLinkLocale
        to="/motorizados"
        class="btn btn-primary cta"
      >
        {{ t('home.drivers.cta') }}
      </NuxtLinkLocale>
    </div>
  </section>
</template>

<style scoped>
.drivers {
  --photo-wash: linear-gradient(180deg, rgb(7 18 14 / 60%), rgb(10 92 67 / 90%) 50%, var(--primary-deep) 100%);
  --photo-wash-narrow: var(--photo-wash);

  padding: var(--section-y) 0;
  background: var(--primary-deep);
  color: var(--on-band);
}

.photo {
  object-position: center 30%;
}

.eyebrow {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0 0 var(--space-4);
  color: var(--accent);
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

.row {
  display: grid;
  gap: var(--space-5);
  align-items: end;
}

.zero {
  margin: 0;
  color: var(--accent);
  font-family: var(--font-poster);
  font-size: var(--font-number);
  font-weight: 900;
  font-stretch: 62%;
  line-height: 0.78;
  letter-spacing: -0.03em;
}

.copy :deep(h2) {
  max-width: 12ch;
  margin: 0 0 var(--space-5);
  font-size: var(--font-h2);
  line-height: var(--leading-heading);
}

.body {
  max-width: 40ch;
  margin: 0;
  color: var(--on-band-soft);
  font-size: var(--font-lead);
  line-height: 1.5;
}

.grid-facts {
  display: grid;
  gap: var(--space-6);
  margin-top: var(--space-7);
  align-items: start;
}

.facts {
  margin: 0;
  padding: 0;
  list-style: none;
  border-top: 1px solid var(--on-band-line);
}

.facts li {
  display: flex;
  align-items: baseline;
  gap: var(--space-4);
  padding: 18px 0;
  border-bottom: 1px solid var(--on-band-line);
  font-weight: 600;
  font-size: 1.1rem;
}

.facts b {
  flex: none;
  min-width: 4.5ch;
  color: var(--accent);
  font-family: var(--font-poster);
  font-size: 1.8rem;
  font-weight: 900;
  font-stretch: 70%;
  line-height: 1;
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

.cta {
  margin-top: var(--space-7);
}

@media (min-width: 960px) {
  .row,
  .grid-facts {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    column-gap: var(--space-9);
  }
}

/* The 0 % starts as an outline and fills in as it scrolls up; the photo drifts slower than the page. */
@supports (animation-timeline: view()) {
  @media (prefers-reduced-motion: no-preference) {
    .zero {
      animation: zero-fill linear both;
      animation-timeline: view();
      animation-range: entry 20% cover 45%;
    }

    .photo {
      animation: parallax linear both;
      animation-timeline: view();
      animation-range: cover;
    }
  }
}

@keyframes zero-fill {
  from {
    color: transparent;
    -webkit-text-stroke: 3px var(--accent);
    transform: scale(0.85);
  }

  to {
    -webkit-text-stroke: 3px var(--accent);
  }
}

@keyframes parallax {
  from {
    transform: translateY(-6%) scale(1.15);
  }

  to {
    transform: translateY(6%) scale(1.15);
  }
}
</style>
