<script setup lang="ts">
const { t } = useI18n()
const { data: site } = await useSite()

useSeoMeta({
  title: () => t('drivers.metaTitle'),
  description: () => t('drivers.metaDescription'),
  ogTitle: () => t('drivers.metaTitle'),
  ogDescription: () => t('drivers.metaDescription'),
})

const freeMonths = computed(() => site.value?.free_months ?? 3)
const minAge = computed(() => site.value?.driver.min_age ?? 21)
const minYear = computed(() => site.value?.driver.vehicle_min_year.moto ?? null)
const documents = computed(() => site.value?.driver.documents ?? [])
const photos = computed(() => site.value?.driver.vehicle_photo_min_count ?? 0)
</script>

<template>
  <div>
    <section class="section">
      <div class="container narrow">
        <span class="eyebrow">{{ t('drivers.eyebrow') }}</span>
        <h1>{{ t('drivers.title') }}</h1>
        <p class="lead">
          {{ t('drivers.lead', { months: freeMonths }) }}
        </p>
        <NuxtLinkLocale
          to="/descargar"
          class="btn btn-primary"
        >
          {{ t('drivers.cta') }}
        </NuxtLinkLocale>
      </div>
    </section>

    <section class="container">
      <div class="grid grid-3">
        <div
          v-for="key in ['commission', 'free', 'direct']"
          :key="key"
          class="card"
        >
          <h3>{{ t(`drivers.why.${key}.title`, { months: freeMonths }) }}</h3>
          <p class="muted">
            {{ t(`drivers.why.${key}.body`, { months: freeMonths }) }}
          </p>
        </div>
      </div>
    </section>

    <section class="section">
      <div class="container grid grid-2 two">
        <div class="card">
          <h2>{{ t('drivers.requirements.title') }}</h2>
          <ul class="checks">
            <li>{{ t('drivers.requirements.age', { age: minAge }) }}</li>
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
        </div>
        <div class="card">
          <h2>{{ t('drivers.fees.title') }}</h2>
          <p class="muted">
            {{ t('drivers.fees.body', { months: freeMonths }) }}
          </p>
          <FeeTable
            v-if="site?.fee_tiers?.length"
            :tiers="site.fee_tiers"
          />
        </div>
      </div>
    </section>

    <section class="container narrow">
      <h2>{{ t('drivers.steps.title') }}</h2>
      <ol class="steps">
        <li
          v-for="n in 4"
          :key="n"
        >
          {{ t(`drivers.steps.step${n}`) }}
        </li>
      </ol>
    </section>
  </div>
</template>

<style scoped>
.lead {
  font-size: 1.2rem;
  color: var(--muted);
}

.two {
  align-items: start;
}

.checks {
  list-style: none;
  padding: 0;
  margin: 0;
}

.checks li {
  position: relative;
  padding: 10px 0 10px 32px;
  border-top: 1px solid var(--border);
}

.checks li::before {
  content: '';
  position: absolute;
  left: 4px;
  top: 16px;
  width: 14px;
  height: 8px;
  border-left: 3px solid var(--primary);
  border-bottom: 3px solid var(--primary);
  transform: rotate(-45deg);
}

.steps {
  padding-left: 1.3em;
}

.steps li {
  margin-bottom: 10px;
}
</style>
