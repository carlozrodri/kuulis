<script setup lang="ts">
// A yellow strip that runs sideways under the hero (Kuulis de noche): the commission, the price in two currencies
// and the payment methods the app offers (GET /public/site). It stands still with reduced motion, and its button
// stops it (WCAG 2.2.2: anything that moves for more than five seconds can be paused).
const props = defineProps<{ methods: string[] }>()
const { t, te } = useI18n()
const items = computed(() => [
  t('home.ticker.zero'),
  ...props.methods.map(m => (te(`payments.${m}`) ? t(`payments.${m}`) : m)),
  t('home.ticker.prices'),
  t('home.ticker.haggle'),
])
const paused = ref(false)
</script>

<template>
  <div class="ticker-wrap">
    <div
      class="ticker"
      :class="{ paused }"
    >
      <div class="track">
        <ul :aria-label="t('home.ticker.label')">
          <li
            v-for="item in items"
            :key="item"
          >
            {{ item }}
          </li>
        </ul>
        <ul aria-hidden="true">
          <li
            v-for="item in items"
            :key="item"
          >
            {{ item }}
          </li>
        </ul>
      </div>
      <button
        type="button"
        class="toggle"
        :aria-label="paused ? t('home.ticker.play') : t('home.ticker.pause')"
        :aria-pressed="paused"
        @click="paused = !paused"
      >
        <svg
          viewBox="0 0 16 16"
          aria-hidden="true"
        >
          <path
            v-if="paused"
            d="M5 3l8 5-8 5z"
          />
          <path
            v-else
            d="M4 3h3v10H4zM9 3h3v10H9z"
          />
        </svg>
      </button>
    </div>
  </div>
</template>

<style scoped>
/* The strip is tilted; its corners must not widen the page. */
.ticker-wrap {
  position: relative;
  z-index: 2;
  margin-top: -14px;
  overflow-x: clip;
}

.ticker {
  position: relative;
  overflow: hidden;
  border-block: 2px solid var(--night);
  background: var(--accent);
  color: #14201b;
  rotate: -1.2deg;
}

.track {
  display: flex;
  width: max-content;
  animation: marquee 36s linear infinite;
}

ul {
  display: flex;
  margin: 0;
  padding: 14px 0;
  list-style: none;
  font-family: var(--font-poster);
  font-size: clamp(1.1rem, 0.9rem + 1vw, 1.6rem);
  font-weight: 800;
  font-stretch: 75%;
  line-height: 1;
  letter-spacing: 0.02em;
  text-transform: uppercase;
}

li {
  display: flex;
  align-items: center;
  gap: 28px;
  padding-right: 28px;
  white-space: nowrap;
}

li::after {
  content: '';
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #0e7c5a;
}

.paused .track {
  animation-play-state: paused;
}

.toggle {
  position: absolute;
  top: 50%;
  right: max(8px, env(safe-area-inset-right, 0px));
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  border: 0;
  border-radius: 50%;
  background: var(--night);
  color: #fff;
  cursor: pointer;
  translate: 0 -50%;
}

.toggle svg {
  width: 16px;
  height: 16px;
  fill: currentcolor;
}

.toggle:focus-visible {
  outline: 2px solid #fff;
  box-shadow: 0 0 0 4px var(--night);
}

@media (prefers-reduced-motion: reduce) {
  .toggle {
    display: none;
  }
}

@keyframes marquee {
  to {
    transform: translateX(-50%);
  }
}
</style>
