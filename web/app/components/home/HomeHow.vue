<script setup lang="ts">
// How it works (docs/website-redesign/03 §5.3): three stops on the route; the last one is where you arrive.
defineProps<{ cities: string[] }>()
const { t } = useI18n()
</script>

<template>
  <section class="section how">
    <div class="container-wide">
      <BrandHeadline :text="t('home.how.title')" />
      <ol class="stops">
        <li
          v-for="n in 3"
          :key="n"
          :class="{ last: n === 3 }"
        >
          <span
            class="stop"
            aria-hidden="true"
          />
          <h3>{{ t(`home.how.stop${n}.title`) }}</h3>
          <p>{{ t(`home.how.stop${n}.body`) }}</p>
        </li>
      </ol>
      <p class="cities">
        <strong>{{ t('home.cities') }}</strong> {{ cities.join(' · ') }}
      </p>
    </div>
  </section>
</template>

<style scoped>
.how {
  padding: var(--section-y) 0;
}

.how :deep(h2) {
  margin: 0 0 var(--space-7);
  font-size: var(--font-h2);
  letter-spacing: var(--tracking-heading);
}

.stops {
  --stop: 28px;

  display: grid;
  gap: var(--space-6);
  margin: 0;
  padding: 0;
  list-style: none;
}

.stops li {
  position: relative;
  padding-left: calc(var(--stop) + var(--space-4));
}

/* The route between stops: down on phones, across on wide screens. */
.stops li:not(.last)::after {
  content: '';
  position: absolute;
  top: calc(var(--stop) / 2);
  bottom: calc(-1 * var(--space-6) - var(--stop) / 2);
  left: calc(var(--stop) / 2 - 3px);
  width: 6px;
  background: var(--primary);
}

.stop {
  position: absolute;
  z-index: 1;
  top: 0;
  left: 0;
  width: var(--stop);
  height: var(--stop);
  border-radius: 50%;
  background: var(--bg);
  box-shadow: inset 0 0 0 6px var(--primary);
}

/* Arrival: the green stop with the brand's yellow dot inside. */
.last .stop {
  background: var(--accent);
  box-shadow: inset 0 0 0 7px var(--primary);
}

h3 {
  margin: 0 0 var(--space-1);
  font-size: var(--font-h3);
  line-height: var(--stop);
}

p {
  margin: 0;
  color: var(--muted);
}

.cities {
  margin-top: var(--space-7);
  color: var(--text);
}

@media (min-width: 720px) {
  .stops {
    grid-template-columns: repeat(3, 1fr);
    gap: var(--space-6);
  }

  .stops li {
    padding: calc(var(--stop) + var(--space-4)) var(--space-4) 0 0;
  }

  .stops li:not(.last)::after {
    top: calc(var(--stop) / 2 - 3px);
    bottom: auto;
    left: var(--stop);
    right: calc(-1 * var(--space-6));
    width: auto;
    height: 6px;
  }
}
</style>
