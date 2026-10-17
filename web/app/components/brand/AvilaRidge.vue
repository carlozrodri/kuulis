<script setup lang="ts">
// The skyline of El Ávila seen from Caracas (docs/website-redesign/02 §1). Traced from SRTM elevation data
// (Open-Meteo elevation API, 2026-10-17): the highest point per longitude between 67.06° W and 66.66° W, north
// of the city, lightly smoothed. West is on the left; the high point on the right is the Silla/Naiguatá area.
// Decorative: hidden from screen readers.
</script>

<template>
  <svg
    class="ridge"
    viewBox="0 0 1440 120"
    preserveAspectRatio="none"
    aria-hidden="true"
    focusable="false"
  >
    <path d="M0 120V87.7Q0 87.7 18 90.3Q36 92.9 54 98.3Q72 103.7 90 102.8Q108 101.9 126 103.1Q144 104.3 162 98.65Q180 93 198 93.4Q216 93.8 234 96.7Q252 99.6 270 95.9Q288 92.2 306 86.45Q324 80.7 342 78.7Q360 76.7 378 76.55Q396 76.4 414 72.05Q432 67.7 450 62.8Q468 57.9 486 54.65Q504 51.4 522 48.9Q540 46.4 558 46.35Q576 46.3 594 44.8Q612 43.3 630 39.05Q648 34.8 666 32.8Q684 30.8 702 23.9Q720 17 738 17.75Q756 18.5 774 14.45Q792 10.4 810 14.8Q828 19.2 846 22.15Q864 25.1 882 22.35Q900 19.6 918 12.4Q936 5.2 954 2.6Q972 0 990 1.8Q1008 3.6 1026 12.95Q1044 22.3 1062 28.7Q1080 35.1 1098 37.2Q1116 39.3 1134 35.75Q1152 32.2 1170 31.35Q1188 30.5 1206 28.1Q1224 25.7 1242 25.15Q1260 24.6 1278 24.8Q1296 25 1314 24.1Q1332 23.2 1350 26.4Q1368 29.6 1386 32.55Q1404 35.5 1422 38.25T1440 41V120Z" />
  </svg>
</template>

<style scoped>
.ridge {
  display: block;
  width: 100%;
  height: clamp(40px, 7vw, 110px);
  fill: currentcolor;
}
</style>
