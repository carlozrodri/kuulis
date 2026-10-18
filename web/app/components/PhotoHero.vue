<script setup lang="ts">
// The top of a main page (Kuulis de noche): a Caracas photograph under the night wash, an eyebrow, the poster
// headline and a lead, with the yellow route drawing itself along the bottom. The page's buttons go in the slot.
// Pages that use it set page meta `heroHeader: 'photo'`, so the header sits on the photo until it scrolls past.
const props = defineProps<{ photo: 'night' | 'avila', title: string, lead?: string, eyebrow?: string }>()
const { t } = useI18n()

// The photographs in public/img/fotos (credited in the footer) and the widths each one comes in.
const PHOTOS = {
  night: { name: 'caracas-noche', widths: [768, 1280, 1920], width: 1920, height: 1280, position: '60% 40%' },
  avila: { name: 'caracas-avila', widths: [768, 1280, 1920], width: 1920, height: 1440, position: 'center 30%' },
} as const
const image = computed(() => {
  const p = PHOTOS[props.photo]
  return {
    ...p,
    src: `/img/fotos/${p.name}-${p.widths[1]}.webp`,
    srcset: p.widths.map(w => `/img/fotos/${p.name}-${w}.webp ${w}w`).join(', '),
  }
})
useHead(() => ({
  link: [{ rel: 'preload', as: 'image', imagesrcset: image.value.srcset, imagesizes: '100vw', fetchpriority: 'high', tagPriority: 'critical' }],
}))
</script>

<template>
  <section
    id="hero"
    class="photo-hero band-photo"
  >
    <img
      class="photo"
      :src="image.src"
      :srcset="image.srcset"
      sizes="100vw"
      :width="image.width"
      :height="image.height"
      :alt="t(`photos.${props.photo}`)"
      :style="{ objectPosition: image.position }"
      fetchpriority="high"
    >
    <svg
      class="route route-draw"
      viewBox="0 0 1440 120"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <path
        pathLength="1"
        d="M-20 100 C 300 110, 420 40, 700 60 S 1100 110, 1460 30"
      />
    </svg>
    <div class="container-wide">
      <p
        v-if="eyebrow"
        class="eyebrow"
      >
        {{ eyebrow }}
      </p>
      <BrandHeadline
        as="h1"
        class="title"
        :text="title"
      />
      <p
        v-if="lead"
        class="lead"
      >
        {{ lead }}
      </p>
      <slot />
    </div>
  </section>
</template>

<style scoped>
.photo-hero {
  /* The header (64/72 px) sits on this field. */
  margin-top: -64px;
  padding: calc(64px + clamp(48px, 9vw, 128px)) 0 clamp(72px, 9vw, 136px);
  background: var(--night);
}

/* The photo eases in from a closer zoom and stops within five seconds (WCAG 2.2.2). */
.photo {
  animation: settle 5s cubic-bezier(0.2, 0.7, 0.2, 1) both;
}

@keyframes settle {
  from {
    transform: scale(1.14) translate3d(-1.5%, -1%, 0);
  }

  to {
    transform: scale(1.04);
  }
}

.route {
  position: absolute;
  inset: auto 0 0;
  z-index: -1;
  width: 100%;
  height: 120px;
  pointer-events: none;
}

.eyebrow {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0 0 var(--space-5);
  color: var(--accent);
  font-size: var(--font-label);
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  animation: fade-up 700ms var(--ease-out) both;
}

.eyebrow::before {
  content: '';
  width: 28px;
  height: 2px;
  background: currentcolor;
}

.title {
  max-width: 15ch;
  margin: 0 0 var(--space-6);
  font-size: var(--font-h1);
  line-height: var(--leading-tight);
  letter-spacing: var(--tracking-display);
  animation: fade-up 900ms 100ms cubic-bezier(0.2, 0.8, 0.2, 1) both;
}

.lead {
  max-width: 36rem;
  margin: 0 0 var(--space-6);
  color: var(--on-band-soft);
  font-size: var(--font-lead);
  font-weight: 500;
  line-height: 1.45;
  animation: fade-up 800ms 300ms var(--ease-out) both;
}

.photo-hero :slotted(*) {
  animation: fade-up 800ms 450ms var(--ease-out) both;
}

@keyframes fade-up {
  from {
    opacity: 0;
    transform: translateY(24px);
  }
}

@media (min-width: 960px) {
  .photo-hero {
    margin-top: -72px;
    padding-top: calc(72px + 136px);
  }
}

@media (prefers-reduced-motion: reduce) {
  .photo {
    transform: scale(1.04);
  }
}
</style>
