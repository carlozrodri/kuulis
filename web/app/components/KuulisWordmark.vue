<script setup lang="ts">
// The «K punto» logo (marketing/brand/logo): the k whose leg is the yellow dot, then «kuulis.». Inline so it takes the
// color of where it sits: `negative` (white k and letters) on the dark header and footer, `auto` the color version on
// light surfaces and the negative one in the dark theme. `size` is the old font size of the wordmark, so call sites
// keep their scale.
withDefaults(defineProps<{ size?: number, tone?: 'auto' | 'negative' }>(), { size: 28, tone: 'auto' })
</script>

<template>
  <svg
    class="wordmark"
    :class="`tone-${tone}`"
    viewBox="48 32 929.45 195.04"
    :style="{ height: `${Math.round(size * 0.8)}px` }"
    role="img"
    aria-label="Kuulis"
  >
    <path
      class="k color"
      d="M48 32H96V224H48ZM96 120L130.48 85.52H198.37L96 187.88Z"
    />
    <path
      class="k negative"
      d="M48.75 32.75H95.25V223.25H48.75ZM95.25 121.81L131.54 86.27H197.31L95.25 187.57Z"
    />
    <circle
      class="dot color"
      cx="174"
      cy="194"
      r="31"
    />
    <circle
      class="dot negative"
      cx="174"
      cy="194"
      r="30.25"
    />
    <path
      class="letters"
      d="M265 224V32H303.04V155.01L288.84 150.45L349.97 85.52H396.89L346.67 141.32L396.64 224H353.52L311.67 153.74L333.73 148.16L291.38 194.32L303.04 172.26V224ZM455.73 227.04Q438.99 227.04 427.2 219.82Q415.4 212.59 409.32 199.65Q403.23 186.72 403.23 169.47V85.52H441.27V166.43Q441.27 174.29 444.45 180.25Q447.62 186.21 453.45 189.51Q459.28 192.8 466.64 192.8Q474.25 192.8 479.95 189.51Q485.66 186.21 488.83 180.25Q492 174.29 492 166.43V85.52H530.05V224H494.54V196.61L496.57 202.69Q491.75 215.12 480.97 221.08Q470.19 227.04 455.73 227.04ZM600.05 227.04Q583.31 227.04 571.52 219.82Q559.72 212.59 553.63 199.65Q547.55 186.72 547.55 169.47V85.52H585.59V166.43Q585.59 174.29 588.76 180.25Q591.93 186.21 597.77 189.51Q603.6 192.8 610.96 192.8Q618.56 192.8 624.27 189.51Q629.98 186.21 633.15 180.25Q636.32 174.29 636.32 166.43V85.52H674.36V224H638.85V196.61L640.88 202.69Q636.06 215.12 625.29 221.08Q614.51 227.04 600.05 227.04ZM694.65 224V32H732.7V224ZM752.99 224V85.52H791.03V224ZM752.99 73.09V35.04H791.03V73.09ZM865.6 227.04Q842.78 227.04 825.91 216.26Q809.04 205.48 802.96 187.22L830.85 174.03Q836.18 185.19 845.31 191.54Q854.44 197.88 865.6 197.88Q873.72 197.88 878.03 194.58Q882.34 191.28 882.34 185.45Q882.34 182.4 880.82 180.25Q879.3 178.09 876.25 176.32Q873.21 174.54 868.65 173.27L845.06 166.68Q828.06 161.86 818.93 151.08Q809.8 140.3 809.8 125.59Q809.8 112.66 816.4 103.02Q822.99 93.38 834.91 87.93Q846.83 82.47 862.31 82.47Q882.6 82.47 897.94 91.98Q913.29 101.5 919.63 118.74L891.47 131.93Q888.43 123.31 880.44 118.11Q872.45 112.91 862.31 112.91Q854.95 112.91 850.76 115.95Q846.58 119 846.58 124.32Q846.58 127.11 848.1 129.39Q849.62 131.68 853.05 133.45Q856.47 135.23 861.54 136.75L883.61 143.34Q900.86 148.42 909.99 158.69Q919.12 168.96 919.12 183.93Q919.12 196.86 912.4 206.5Q905.68 216.14 893.76 221.59Q881.83 227.04 865.6 227.04Z"
    />
    <circle
      class="dot"
      cx="956.15"
      cy="204.22"
      r="21.31"
    />
  </svg>
</template>

<style scoped>
.wordmark {
  display: block;
  width: auto;
  overflow: visible;
}

/* The brand's own colors, not the theme tokens: the logo never changes hue (README §6). */
.k {
  fill: #0e7c5a;
}

.letters {
  fill: #14201b;
}

.dot {
  fill: #ffc83d;
}

.negative {
  display: none;
}

/* White on dark is drawn 0.75 units thinner (lo claro sobre oscuro se ve más grueso). */
.tone-negative .color {
  display: none;
}

.tone-negative .negative {
  display: inline;
}

.tone-negative .k,
.tone-negative .letters {
  fill: #fff;
}

@media (prefers-color-scheme: dark) {
  .tone-auto .color {
    display: none;
  }

  .tone-auto .negative {
    display: inline;
  }

  .tone-auto .k,
  .tone-auto .letters {
    fill: #fff;
  }
}
</style>
