<script setup lang="ts">
// A phone showing real app screens (captured by Carlos from the passenger app in dark mode on 2026-10-18,
// public/img/app). With several screens, `active` picks the one on display and the others fade out.
const props = withDefaults(defineProps<{ screens: string[], active?: number, eager?: boolean }>(), { active: 0, eager: false })
</script>

<template>
  <div
    class="phone"
    aria-hidden="true"
  >
    <div class="screen">
      <img
        v-for="(screen, i) in props.screens"
        :key="screen"
        :class="{ on: i === active }"
        :src="`/img/app/${screen}.webp`"
        alt=""
        width="590"
        height="1278"
        :loading="eager ? 'eager' : 'lazy'"
        decoding="async"
      >
    </div>
    <slot />
  </div>
</template>

<style scoped>
.phone {
  position: relative;
  width: var(--phone-w, min(300px, 72vw));
  aspect-ratio: 590 / 1278;
  padding: 10px;
  border-radius: 44px;
  background: #0b0f0d;
  box-shadow:
    inset 0 0 0 1.5px rgb(255 255 255 / 14%),
    0 40px 80px rgb(0 0 0 / 50%),
    0 0 120px rgb(255 200 61 / 12%);
}

.phone::after {
  content: '';
  position: absolute;
  top: 20px;
  left: 50%;
  width: 30%;
  height: 22px;
  border-radius: var(--radius-pill);
  background: #0b0f0d;
  translate: -50% 0;
}

.screen {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  border-radius: 34px;
  background: var(--surface-alt);
}

img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  opacity: 0;
  transform: scale(1.04);
  transition: opacity 600ms var(--ease-out), transform 600ms var(--ease-out);
}

img.on {
  opacity: 1;
  transform: none;
}
</style>
