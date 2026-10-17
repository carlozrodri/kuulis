<script setup lang="ts">
const { t, tm, rt } = useI18n()
const { data: site } = await useSite()
// The header wears the hero's green until the hero scrolls past (SiteHeader).
definePageMeta({ heroHeader: true })

useSeoMeta({
  title: () => t('home.metaTitle'),
  description: () => t('home.metaDescription'),
  ogTitle: () => t('home.metaTitle'),
  ogDescription: () => t('home.metaDescription'),
})

const freeMonths = computed(() => site.value?.free_months ?? 3)
const cities = computed(() => site.value?.cities ?? ['Caracas'])
const paymentMethods = computed(() => site.value?.payment_methods ?? [])
const faq = computed(() => (tm('home.faq.items') as { q: unknown, a: unknown }[]).map(item => ({ q: rt(item.q as never), a: rt(item.a as never) })))
</script>

<template>
  <div>
    <HomeHero />
    <HomePrice :methods="paymentMethods" />

    <section class="section drivers">
      <div class="container-wide grid grid-2 split">
        <div>
          <span class="eyebrow">{{ t('home.drivers.eyebrow') }}</span>
          <h2>{{ t('home.drivers.title') }}</h2>
          <p class="lead-muted">
            {{ t('home.drivers.body', { months: freeMonths }) }}
          </p>
          <NuxtLinkLocale
            to="/motorizados"
            class="btn btn-primary"
          >
            {{ t('home.drivers.cta') }}
          </NuxtLinkLocale>
        </div>
        <div class="card">
          <h3>{{ t('home.drivers.tableTitle') }}</h3>
          <FeeTable
            v-if="site?.fee_tiers?.length"
            :tiers="site.fee_tiers"
          />
          <p class="muted small note">
            {{ t('home.drivers.tableNote', { months: freeMonths }) }}
          </p>
        </div>
      </div>
    </section>

    <section class="section">
      <div class="container-wide">
        <span class="eyebrow">{{ t('home.how.eyebrow') }}</span>
        <h2>{{ t('home.how.title') }}</h2>
        <ol class="steps">
          <li
            v-for="n in 3"
            :key="n"
          >
            <span class="num">{{ n }}</span>
            <div>
              <h3>{{ t(`home.how.step${n}.title`) }}</h3>
              <p class="muted">
                {{ t(`home.how.step${n}.body`) }}
              </p>
            </div>
          </li>
        </ol>
        <p class="cities">
          <strong>{{ t('home.cities') }}</strong> {{ cities.join(' · ') }}
        </p>
      </div>
    </section>

    <section class="section">
      <div class="container narrow">
        <h2>{{ t('home.faq.title') }}</h2>
        <details
          v-for="item in faq"
          :key="item.q"
          class="faq"
        >
          <summary>{{ item.q }}</summary>
          <p class="muted">
            {{ item.a }}
          </p>
        </details>
      </div>
    </section>

    <section class="container-wide">
      <div class="final">
        <h2>{{ t('home.final.title') }}</h2>
        <p>{{ t('home.final.body') }}</p>
        <NuxtLinkLocale
          to="/descargar"
          class="btn btn-accent"
        >
          {{ t('home.download') }}
        </NuxtLinkLocale>
      </div>
    </section>
  </div>
</template>

<style scoped>
.small {
  font-size: 0.85rem;
}

.drivers {
  background: var(--surface-alt);
}

.split {
  align-items: center;
  gap: 32px;
}

.lead-muted {
  color: var(--muted);
  font-size: 1.1rem;
}

.note {
  margin: 14px 0 0;
}

.steps {
  list-style: none;
  padding: 0;
  margin: 24px 0 0;
  display: grid;
  gap: 16px;
}

@media (min-width: 720px) {
  .steps {
    grid-template-columns: repeat(3, 1fr);
  }
}

.steps li {
  display: flex;
  gap: 14px;
}

.num {
  flex: none;
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  background: var(--primary);
  color: var(--on-primary);
  font-weight: 800;
}

.cities {
  margin-top: 28px;
}

.faq {
  background: var(--surface);
  border-radius: 16px;
  padding: 18px 20px;
  margin-bottom: 10px;
  box-shadow: var(--shadow);
}

.faq summary {
  font-weight: 700;
  cursor: pointer;
}

.faq p {
  margin: 10px 0 0;
}

.final {
  background: var(--text);
  color: var(--bg);
  border-radius: 28px;
  padding: 44px 28px;
  text-align: center;
}

.final p {
  opacity: 0.8;
}
</style>
