<script setup lang="ts">
// The route (docs/website-redesign/02 §1, §8): one rounded line from where you are (the ring) to where you go
// (the yellow dot). It draws itself once and the dot arrives; with reduced motion, or without CSS animations,
// it is simply there. Decorative.
withDefaults(defineProps<{ animate?: boolean }>(), { animate: true })
</script>

<template>
  <svg
    class="route"
    :class="{ animate }"
    viewBox="0 0 480 560"
    aria-hidden="true"
    focusable="false"
  >
    <path
      class="line"
      pathLength="1"
      d="M84 500C84 420 150 392 228 380S392 344 392 262 300 170 300 112 344 60 396 60"
    />
    <circle
      class="origin"
      cx="84"
      cy="500"
      r="18"
    />
    <circle
      class="destination"
      cx="396"
      cy="60"
      r="22"
    />
  </svg>
</template>

<style scoped>
.route {
  display: block;
  width: 100%;
  height: auto;
  overflow: visible;
}

.line {
  fill: none;
  stroke: currentcolor;
  stroke-width: 10;
  stroke-linecap: round;
}

.origin {
  fill: var(--band-brand);
  stroke: currentcolor;
  stroke-width: 8;
}

.destination {
  fill: var(--accent);
  transform-box: fill-box;
  transform-origin: center;
}

@media (prefers-reduced-motion: no-preference) {
  .animate .line {
    stroke-dasharray: 1;
    animation: draw 1.1s var(--ease-out) 0.2s both;
  }

  .animate .destination {
    animation: arrive 240ms var(--ease-out) 1.3s both;
  }
}

@keyframes draw {
  from {
    stroke-dashoffset: 1;
  }

  to {
    stroke-dashoffset: 0;
  }
}

@keyframes arrive {
  from {
    transform: scale(0);
  }

  to {
    transform: scale(1);
  }
}
</style>
