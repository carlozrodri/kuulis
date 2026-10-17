<script setup lang="ts">
// Drivers (docs/website-redesign/03 §6): the number, the fee with a worked example, what you need, how to sign up
// and the drivers' own questions. Every figure comes from GET /public/site; without it the page leaves the figure
// out instead of guessing (04 §8).
const { t } = useI18n()
const { data: site } = await useSite()
// The header sits on the hero photo until it scrolls past; the footer's Ávila rises from the night download.
definePageMeta({ heroHeader: 'photo', endsOnBrand: true })

useSeoMeta({
  title: () => t('drivers.metaTitle'),
  description: () => t('drivers.metaDescription'),
  ogTitle: () => t('drivers.metaTitle'),
  ogDescription: () => t('drivers.metaDescription'),
})

const freeMonths = computed(() => site.value?.free_months ?? 3)
const tiers = computed(() => site.value?.fee_tiers ?? [])
const minAge = computed(() => site.value?.driver.min_age ?? null)
const minYear = computed(() => site.value?.driver.vehicle_min_year.moto ?? null)
const documents = computed(() => site.value?.driver.documents ?? [])
const photos = computed(() => site.value?.driver.vehicle_photo_min_count ?? 0)

const why = computed(() => ['commission', 'free', 'direct'].map(key => ({
  key,
  title: t(`drivers.why.${key}.title`, { months: freeMonths.value }),
  body: t(`drivers.why.${key}.body`),
})))
const steps = computed(() => [1, 2, 3, 4].map(n => ({ key: `step${n}`, body: t(`drivers.steps.step${n}`) })))
const faq = computed(() => ['free', 'idle', 'paid', 'fee'].map(key => ({
  key,
  q: t(`drivers.faq.${key}.q`),
  a: t(`drivers.faq.${key}.a`, { months: freeMonths.value }),
})))
</script>

<template>
  <div>
    <PhotoHero
      photo="avila"
      :eyebrow="t('home.eyebrow.drivers')"
      :title="t('drivers.title')"
      :lead="t('drivers.lead')"
    >
      <NuxtLinkLocale
        to="/descargar"
        class="btn btn-primary"
      >
        {{ t('drivers.cta') }}
      </NuxtLinkLocale>
    </PhotoHero>

    <section
      v-reveal
      class="section number"
    >
      <div class="container-wide grid-number">
        <h2 class="zero">
          <span class="figure">{{ t('drivers.zero') }}</span>
          <span class="label">{{ t('drivers.zeroLabel') }}</span>
        </h2>
        <ul class="rows">
          <li
            v-for="row in why"
            :key="row.key"
          >
            <h3>{{ row.title }}</h3>
            <p>{{ row.body }}</p>
          </li>
        </ul>
      </div>
    </section>

    <section
      v-reveal
      class="section fees"
    >
      <div class="container-wide grid-fees">
        <div>
          <BrandHeadline :text="t('drivers.fees.title')" />
          <p class="body">
            {{ tiers.length ? t('drivers.fees.body') : t('drivers.fees.bodyNoData') }}
          </p>
          <FeeExample
            v-if="tiers.length"
            :tiers="tiers"
          />
          <p class="note">
            {{ t('drivers.fees.note', { months: freeMonths }) }}
          </p>
        </div>
        <div
          v-if="tiers.length"
          class="card"
        >
          <FeeTable :tiers="tiers" />
        </div>
      </div>
    </section>

    <section
      v-reveal
      class="section needs"
    >
      <div class="container-wide grid-needs">
        <BrandHeadline :text="t('drivers.requirements.title')" />
        <div>
          <ul class="checks">
            <li v-if="minAge">
              {{ t('drivers.requirements.age', { age: minAge }) }}
            </li>
            <li v-if="minYear">
              {{ t('drivers.requirements.year', { year: minYear }) }}
            </li>
            <li
              v-for="doc in documents"
              :key="doc"
            >
              {{ doc === 'vehicle_photo' ? t('drivers.documents.vehicle_photo', { n: photos }) : t(`drivers.documents.${doc}`) }}
            </li>
            <li>{{ t('drivers.requirements.phone') }}</li>
          </ul>
          <p class="note">
            {{ t('drivers.requirements.review') }}
          </p>
        </div>
      </div>
    </section>

    <section
      v-reveal
      class="section steps"
    >
      <div class="container-wide">
        <BrandHeadline :text="t('drivers.steps.title')" />
        <RouteStops :items="steps" />
      </div>
    </section>

    <section
      v-reveal
      class="section faq"
    >
      <div class="container narrow">
        <BrandHeadline :text="t('drivers.faq.title')" />
        <FaqList :items="faq" />
      </div>
    </section>

    <DownloadBand
      :title="t('drivers.final.title')"
      :body="t('drivers.final.body')"
    />
  </div>
</template>

<style scoped>
.section :deep(h2.headline) {
  max-width: 14ch;
  margin: 0 0 var(--space-6);
  font-size: var(--font-h2);
  line-height: var(--leading-heading);
}

.grid-needs :deep(h2.headline) {
  margin: 0;
}

.number,
.fees,
.needs,
.steps,
.faq {
  padding: var(--section-y) 0 0;
}

.faq {
  padding-bottom: var(--section-y);
}

.grid-number,
.grid-fees,
.grid-needs {
  display: grid;
  gap: var(--space-7);
}

.grid-needs {
  gap: var(--space-6);
}

.zero {
  display: flex;
  flex-direction: column;
  margin: 0;
}

.figure {
  color: var(--primary);
  white-space: nowrap;
  transform-origin: left bottom;
  font-family: var(--font-poster);
  font-size: var(--font-number);
  font-weight: 900;
  font-stretch: 62%;
  line-height: 0.8;
  letter-spacing: -0.03em;
}

.label {
  margin-top: var(--space-3);
  font-size: var(--font-h3);
  font-weight: 700;
}

.rows {
  margin: 0;
  padding: 0;
  list-style: none;
}

.rows li {
  padding: var(--space-5) 0;
  border-top: 1px solid var(--border);
}

.rows li:last-child {
  border-bottom: 1px solid var(--border);
}

.rows h3 {
  margin: 0 0 var(--space-1);
  font-size: var(--font-h3);
  letter-spacing: -0.01em;
}

.rows p,
.body,
.note {
  margin: 0;
  color: var(--muted);
}

.body {
  max-width: 34rem;
  margin-bottom: var(--space-5);
  font-size: var(--font-lead);
  line-height: 1.5;
}

.note {
  max-width: 34rem;
  margin-top: var(--space-4);
  font-size: var(--font-small);
}

.checks {
  margin: 0;
  padding: 0;
  list-style: none;
}

.checks li {
  position: relative;
  padding: var(--space-3) 0 var(--space-3) var(--space-7);
  border-top: 1px solid var(--border);
  font-weight: 600;
}

.checks li:last-child {
  border-bottom: 1px solid var(--border);
}

/* A check in the brand green. */
.checks li::before {
  content: '';
  position: absolute;
  left: 4px;
  top: calc(var(--space-3) + 6px);
  width: 14px;
  height: 8px;
  border-left: 3px solid var(--primary);
  border-bottom: 3px solid var(--primary);
  transform: rotate(-45deg);
}

@media (min-width: 960px) {
  .grid-number {
    grid-template-columns: 5fr 7fr;
    column-gap: var(--space-9);
    align-items: center;
  }

  .grid-fees {
    grid-template-columns: 6fr 5fr;
    column-gap: var(--space-9);
    align-items: start;
  }

  .grid-needs {
    grid-template-columns: 5fr 7fr;
    column-gap: var(--space-9);
  }
}

/* The 0 % grows into place as it scrolls up. */
@supports (animation-timeline: view()) {
  @media (prefers-reduced-motion: no-preference) {
    .figure {
      animation: figure-fill linear both;
      animation-timeline: view();
      animation-range: entry 20% cover 45%;
    }
  }
}

@keyframes figure-fill {
  from {
    transform: scale(0.8) translateY(10%);
  }
}
</style>
