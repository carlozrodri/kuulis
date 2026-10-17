<script setup lang="ts">
const { t, tm, rt } = useI18n()
const { data: site } = await useSite()

useSeoMeta({
  title: () => t('home.metaTitle'),
  description: () => t('home.metaDescription'),
  ogTitle: () => t('home.metaTitle'),
  ogDescription: () => t('home.metaDescription'),
})

const freeMonths = computed(() => site.value?.free_months ?? 3)
const cities = computed(() => site.value?.cities ?? ['Caracas'])
const faq = computed(() => (tm('home.faq.items') as { q: unknown, a: unknown }[]).map(item => ({ q: rt(item.q as never), a: rt(item.a as never) })))
</script>

<template>
  <div>
    <section class="hero">
      <div class="container hero-grid">
        <div>
          <span class="pill">{{ t('home.pill', { months: freeMonths }) }}</span>
          <h1>{{ t('home.title') }}</h1>
          <p class="lead">
            {{ t('home.lead') }}
          </p>
          <div class="actions">
            <NuxtLinkLocale
              to="/descargar"
              class="btn btn-accent"
            >
              {{ t('home.download') }}
            </NuxtLinkLocale>
            <NuxtLinkLocale
              to="/motorizados"
              class="btn btn-ghost"
            >
              {{ t('home.drive') }}
            </NuxtLinkLocale>
          </div>
        </div>
        <div
          class="phone"
          aria-hidden="true"
        >
          <svg
            viewBox="0 0 260 300"
            class="map"
          >
            <rect
              width="260"
              height="300"
              rx="28"
              fill="#EAF5EF"
            />
            <path
              d="M0 70 H260 M0 160 H260 M0 240 H260 M60 0 V300 M150 0 V300 M215 0 V300"
              stroke="#fff"
              stroke-width="10"
            />
            <path
              d="M60 250 C60 190 150 200 150 160 S215 120 215 60"
              fill="none"
              stroke="#0E7C5A"
              stroke-width="7"
              stroke-linecap="round"
              stroke-dasharray="1 14"
            />
            <circle
              cx="60"
              cy="250"
              r="12"
              fill="#0E7C5A"
            />
            <circle
              cx="60"
              cy="250"
              r="5"
              fill="#fff"
            />
            <circle
              cx="215"
              cy="60"
              r="14"
              fill="#FFC83D"
            />
            <circle
              cx="215"
              cy="60"
              r="5"
              fill="#3A2A00"
            />
          </svg>
          <div class="ride card">
            <div class="ride-row">
              <span class="avatar">L</span>
              <div>
                <strong>{{ t('home.card.driver') }}</strong>
                <span class="muted small">{{ t('home.card.bike') }}</span>
              </div>
              <span class="eta">4 min</span>
            </div>
            <div class="price">
              <span class="muted small">{{ t('home.card.fare') }}</span>
              <strong>$2.40</strong>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="section">
      <div class="container">
        <span class="eyebrow">{{ t('home.riders.eyebrow') }}</span>
        <h2>{{ t('home.riders.title') }}</h2>
        <div class="grid grid-3 features">
          <div
            v-for="key in ['price', 'pay', 'safe']"
            :key="key"
            class="card"
          >
            <h3>{{ t(`home.riders.${key}.title`) }}</h3>
            <p class="muted">
              {{ t(`home.riders.${key}.body`) }}
            </p>
          </div>
        </div>
      </div>
    </section>

    <section class="section drivers">
      <div class="container grid grid-2 split">
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
      <div class="container">
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

    <section class="container">
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
.hero {
  background: radial-gradient(120% 90% at 85% 10%, #18a374 0%, var(--hero) 45%, var(--hero-shade) 100%);
  color: #fff;
  padding: 56px 0 72px;
}

.hero-grid {
  display: grid;
  gap: 40px;
  align-items: center;
}

@media (min-width: 860px) {
  .hero-grid {
    grid-template-columns: 1.15fr 0.85fr;
  }
}

.pill {
  display: inline-block;
  background: rgb(255 255 255 / 14%);
  border: 1px solid rgb(255 255 255 / 25%);
  border-radius: 999px;
  padding: 6px 14px;
  font-size: 0.85rem;
  font-weight: 700;
  margin-bottom: 18px;
}

.lead {
  font-size: 1.2rem;
  opacity: 0.92;
  max-width: 34ch;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 28px;
}

.phone {
  position: relative;
  max-width: 340px;
  margin: 0 auto;
  width: 100%;
}

.map {
  width: 100%;
  height: auto;
  display: block;
  border-radius: 28px;
  box-shadow: 0 30px 60px rgb(0 0 0 / 25%);
}

.ride {
  position: absolute;
  left: -16px;
  right: 24px;
  bottom: -28px;
  color: var(--text);
  padding: 16px 18px;
}

.ride-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.ride-row div {
  display: grid;
  flex: 1;
}

.avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: var(--surface-alt);
  color: var(--primary);
  font-weight: 800;
}

.eta {
  font-weight: 800;
  color: var(--primary);
}

.price {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  border-top: 1px solid var(--border);
  margin-top: 12px;
  padding-top: 10px;
}

.price strong {
  font-size: 1.3rem;
}

.small {
  font-size: 0.85rem;
}

.features {
  margin-top: 24px;
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
