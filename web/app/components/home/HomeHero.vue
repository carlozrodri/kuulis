<script setup lang="ts">
// Home hero (Kuulis de noche): Caracas at night, the poster headline rising word by word to the yellow dot, the
// route drawing itself along the bottom and the app's real home screen. The header sits on this field until it
// scrolls out from under it (SiteHeader watches #hero, page meta heroHeader: 'photo').
const { t } = useI18n()
const words = computed(() => {
  const title = t('home.hero.title')
  return { list: (title.endsWith('.') ? title.slice(0, -1) : title).split(' '), dot: title.endsWith('.') }
})
// The last two words are drawn in outline, the way a poster sets its sign-off.
const outlineFrom = computed(() => Math.max(1, words.value.list.length - 2))

useHead({
  link: [{
    rel: 'preload',
    as: 'image',
    imagesrcset: '/img/fotos/caracas-noche-768.webp 768w, /img/fotos/caracas-noche-1280.webp 1280w, /img/fotos/caracas-noche-1920.webp 1920w',
    imagesizes: '100vw',
    fetchpriority: 'high',
    // Ahead of the font preloads: the photo is what a phone paints largest first.
    tagPriority: 'critical',
  }],
})
</script>

<template>
  <section
    id="hero"
    class="hero band-photo"
  >
    <img
      class="photo"
      src="/img/fotos/caracas-noche-1280.webp"
      srcset="/img/fotos/caracas-noche-768.webp 768w, /img/fotos/caracas-noche-1280.webp 1280w, /img/fotos/caracas-noche-1920.webp 1920w"
      sizes="100vw"
      width="1920"
      height="1280"
      :alt="t('home.hero.photoAlt')"
      fetchpriority="high"
    >
    <svg
      class="route route-draw"
      viewBox="0 0 1440 160"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <path
        pathLength="1"
        d="M-20 140 C 260 140, 360 60, 620 80 S 1040 150, 1200 70 S 1400 30, 1460 40"
      />
    </svg>
    <div class="container-wide grid-hero">
      <div class="copy">
        <h1 class="title">
          <template
            v-for="(word, i) in words.list.slice(0, -1)"
            :key="i"
          >
            <span
              class="word"
              :class="{ outline: i >= outlineFrom }"
            ><span :style="{ animationDelay: `${i * 70}ms` }">{{ word }}</span></span>{{ ' ' }}
          </template>
          <span class="tail"><span
            class="word"
            :class="{ outline: words.list.length - 1 >= outlineFrom }"
          ><span :style="{ animationDelay: `${(words.list.length - 1) * 70}ms` }">{{ words.list.at(-1) }}</span></span><span
            v-if="words.dot"
            class="dot"
          >.</span></span>
        </h1>
        <p class="lead">
          {{ t('home.hero.lead') }}
        </p>
        <div class="actions">
          <NuxtLinkLocale
            to="/descargar"
            class="btn btn-primary"
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
        <p class="note">
          {{ t('home.hero.note') }}
        </p>
      </div>
      <AppPhone
        class="phone"
        :screens="['inicio']"
        eager
      >
        <p class="chip chip-a">
          <span class="ic">$</span><span>$1.80<small>{{ t('home.hero.chipPrice') }}</small></span>
        </p>
        <p class="chip chip-b">
          <span class="ic">0%</span><span>0 %<small>{{ t('home.hero.chipZero') }}</small></span>
        </p>
      </AppPhone>
    </div>
  </section>
</template>

<style scoped>
.hero {
  --photo-wash: linear-gradient(90deg, rgb(7 18 14 / 92%) 0%, rgb(7 18 14 / 70%) 45%, rgb(7 18 14 / 20%) 80%),
    linear-gradient(0deg, var(--night) 0%, transparent 35%),
    linear-gradient(180deg, rgb(7 18 14 / 60%) 0%, transparent 20%);

  /* The header (64/72 px) sits on this field. */
  margin-top: -64px;
  padding: calc(64px + clamp(32px, 8vw, 96px)) 0 clamp(48px, 7vw, 96px);
  background: var(--night);
  color: var(--on-band);
}

/* Every movement here settles within five seconds (WCAG 2.2.2); the photo eases in from a closer zoom. */
.photo {
  object-position: 60% 40%;
  animation: settle 5s cubic-bezier(0.2, 0.7, 0.2, 1) both;
}

@keyframes settle {
  from {
    transform: scale(1.16) translate3d(-2%, -1.5%, 0);
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
  height: 160px;
  pointer-events: none;
}

.grid-hero {
  display: grid;
  gap: var(--space-7);
  align-items: end;
}

.title {
  margin: 0 0 var(--space-6);
  font-family: var(--font-poster);
  font-size: var(--font-display);
  font-weight: 900;
  font-stretch: 66%;
  line-height: var(--leading-tight);
  letter-spacing: var(--tracking-display);
  text-transform: uppercase;
}

.tail {
  white-space: nowrap;
}

.word {
  display: inline-block;
  padding-bottom: 0.04em;
  overflow: hidden;
  vertical-align: top;
}

.word > span {
  display: inline-block;
  animation: rise 900ms cubic-bezier(0.2, 0.8, 0.2, 1) both;
}

.outline > span {
  color: transparent;
  -webkit-text-stroke: 2px var(--on-band);
}

.dot {
  display: inline-block;
  width: 0.2em;
  height: 0.2em;
  margin-left: 0.04em;
  border-radius: 50%;
  background: var(--accent);
  color: transparent;
  line-height: 0;
  overflow: hidden;
  animation: drop 700ms 900ms cubic-bezier(0.3, 1.6, 0.5, 1) both, pulse 1.6s 1.6s 2;
}

@keyframes rise {
  from {
    transform: translateY(105%);
  }
}

@keyframes drop {
  from {
    opacity: 0;
    transform: translateY(-3em) scale(0.4);
  }
}

@keyframes pulse {
  0% {
    box-shadow: 0 0 0 0 rgb(255 200 61 / 55%);
  }

  70%,
  100% {
    box-shadow: 0 0 0 0.35em rgb(255 200 61 / 0%);
  }
}

.lead {
  max-width: 34ch;
  margin: 0 0 var(--space-6);
  color: var(--on-band-soft);
  font-size: var(--font-lead);
  font-weight: 500;
  line-height: 1.45;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
}

.note {
  margin: var(--space-4) 0 0;
  color: var(--on-band-soft);
  font-size: var(--font-small);
}

.lead,
.actions,
.note {
  animation: fade-up 800ms 500ms var(--ease-out) both;
}

@keyframes fade-up {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
}

.phone {
  --phone-w: min(260px, 64vw);

  justify-self: center;
  rotate: -6deg;
  animation: phone-in 1.2s 300ms cubic-bezier(0.2, 0.8, 0.2, 1) backwards;
}

@keyframes phone-in {
  from {
    opacity: 0;
    transform: translateY(40%);
    rotate: 4deg;
  }
}

.chip {
  position: absolute;
  z-index: 2;
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0;
  padding: 12px 16px;
  border-radius: 18px;
  background: var(--surface);
  color: var(--text);
  font-weight: 800;
  font-size: 0.95rem;
  line-height: 1.2;
  white-space: nowrap;
  box-shadow: 0 18px 40px rgb(0 0 0 / 35%);
  animation: float 2.4s 1.2s ease-in-out 2;
}

.chip small {
  display: block;
  color: var(--muted);
  font-weight: 500;
  font-size: 0.75rem;
}

.ic {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border-radius: 10px;
  background: var(--surface-alt);
  color: var(--primary);
  font-size: 0.8rem;
}

.chip-a {
  top: 22%;
  left: -12px;
}

.chip-b {
  right: -8px;
  bottom: 16%;
  animation-delay: 1.6s;
}

@keyframes float {
  50% {
    translate: 0 -10px;
  }
}

@media (min-width: 600px) {
  .chip-a {
    left: -64px;
  }

  .chip-b {
    right: -28px;
  }
}

@media (min-width: 960px) {
  .hero {
    margin-top: -72px;
    padding-top: calc(72px + 96px);
  }

  .grid-hero {
    grid-template-columns: minmax(0, 1.3fr) minmax(0, 0.7fr);
  }

  .phone {
    --phone-w: min(300px, 100%);

    justify-self: end;
  }
}

@media (prefers-reduced-motion: reduce) {
  .photo {
    transform: scale(1.04);
  }
}
</style>
