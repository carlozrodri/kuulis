<script setup lang="ts">
// A phone showing real app screens (captured from the passenger app on 2026-10-17, public/img/app). With several
// screens, `active` picks the one on display and the others fade out. Each screen follows the visitor's theme.
const props = withDefaults(defineProps<{ screens: string[], active?: number, eager?: boolean }>(), { active: 0, eager: false })
</script>

<template>
  <div
    class="phone"
    aria-hidden="true"
  >
    <div class="screen">
      <picture
        v-for="(screen, i) in props.screens"
        :key="screen"
        :class="{ on: i === active }"
      >
        <source
          :srcset="`/img/app/${screen}-oscuro.webp`"
          media="(prefers-color-scheme: dark)"
        >
        <img
          :src="`/img/app/${screen}-claro.webp`"
          alt=""
          width="590"
          height="1278"
          :loading="eager ? 'eager' : 'lazy'"
          decoding="async"
        >
      </picture>
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

picture {
  position: absolute;
  inset: 0;
  opacity: 0;
  transform: scale(1.04);
  transition: opacity 600ms var(--ease-out), transform 600ms var(--ease-out);
}

picture.on {
  opacity: 1;
  transform: none;
}

img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
</style>
