<script setup lang="ts">
// How it works (Kuulis de noche): three steps scroll past a phone that stays in place and changes screen with each
// one. Without JavaScript every step is readable and the phone shows the first screen.
defineProps<{ cities: string[] }>()
const { t } = useI18n()
const steps = [1, 2, 3] as const
// Which app screen each step shows: the home screen, then the quote.
const screenFor = (step: number) => (step === 1 ? 0 : 1)

const active = ref(1)
const list = ref<HTMLElement>()
let observer: IntersectionObserver | undefined

onMounted(() => {
  if (!list.value || !('IntersectionObserver' in window)) return
  const narrow = matchMedia('(max-width: 959px)').matches
  observer = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (entry.isIntersecting) active.value = Number((entry.target as HTMLElement).dataset.step)
    }
  }, { rootMargin: narrow ? '-62% 0px -20% 0px' : '-45% 0px -45% 0px' })
  list.value.querySelectorAll('.step').forEach(el => observer!.observe(el))
})
onBeforeUnmount(() => observer?.disconnect())
</script>

<template>
  <section class="story band-ink">
    <div class="container-wide">
      <p class="eyebrow">
        {{ t('home.eyebrow.how') }}
      </p>
      <BrandHeadline
        v-reveal
        :text="t('home.how.title')"
      />
      <p class="cities">
        <strong>{{ t('home.cities') }}</strong> {{ cities.join(' · ') }}
      </p>
      <div class="grid-story">
        <ol
          ref="list"
          class="steps"
        >
          <li
            v-for="n in steps"
            :key="n"
            class="step"
            :class="{ on: active === n }"
            :data-step="n"
          >
            <span
              class="n"
              aria-hidden="true"
            >0{{ n }}</span>
            <h3>{{ t(`home.story.step${n}.title`) }}</h3>
            <p>{{ t(`home.story.step${n}.body`) }}</p>
          </li>
        </ol>
        <div
          class="stage"
          :class="{ paid: active === 3 }"
        >
          <div class="glow" />
          <AppPhone
            class="phone"
            :screens="['inicio', 'cotizacion']"
            :active="screenFor(active)"
          >
            <p class="chip">
              <span class="ic">✓</span><span>{{ t('home.story.chipTitle') }}<small>{{ t('home.story.chipBody') }}</small></span>
            </p>
          </AppPhone>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.story {
  padding: var(--section-y) 0 var(--space-7);
}

.eyebrow {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0 0 var(--space-4);
  color: var(--accent);
  font-size: var(--font-label);
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.eyebrow::before {
  content: '';
  width: 28px;
  height: 2px;
  background: currentcolor;
}

.story :deep(h2) {
  max-width: 12ch;
  margin: 0 0 var(--space-4);
  font-size: var(--font-h2);
  line-height: var(--leading-heading);
}

.cities {
  margin: 0;
  color: var(--on-band-soft);
}

.grid-story {
  display: flex;
  flex-direction: column-reverse;
  margin-top: var(--space-6);
}

.steps {
  margin: 0;
  padding: 0;
  list-style: none;
}

.step {
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  min-height: 64vh;
  padding: var(--space-5) 0 10vh;
  border-top: 1px solid var(--on-band-line);
}

/* The step on screen lights up: its number turns yellow and its title moves in a little. Every step stays readable. */
.n {
  color: var(--on-band-soft);
  transition: color 400ms var(--ease-out);
  font-family: var(--font-poster);
  font-size: 3rem;
  font-weight: 900;
  font-stretch: 62%;
  line-height: 1;
}

.step.on .n {
  color: var(--accent);
}

.step h3 {
  transition: transform 400ms var(--ease-out);
  margin: 10px 0 8px;
  font-size: clamp(1.6rem, 1.2rem + 1.4vw, 2.4rem);
  font-weight: 800;
  letter-spacing: -0.03em;
  line-height: 1.05;
}

.step p {
  max-width: 36ch;
  margin: 0;
  color: var(--on-band-soft);
}

.stage {
  position: sticky;
  top: 0;
  z-index: 1;
  display: grid;
  place-items: center;
  height: 54vh;
  background: linear-gradient(var(--band-ink) 88%, transparent);
}

.glow {
  position: absolute;
  width: 70%;
  aspect-ratio: 1;
  border-radius: 50%;
  background: radial-gradient(circle, rgb(14 124 90 / 55%), transparent 65%);
  filter: blur(10px);
}

.phone {
  --phone-w: min(190px, 46vw);
}

.chip {
  position: absolute;
  bottom: 10%;
  left: -24px;
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
  opacity: 0;
  transform: translateY(14px) scale(0.96);
  transition: opacity 500ms var(--ease-out), transform 500ms var(--ease-out);
}

.paid .chip {
  opacity: 1;
  transform: none;
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
}

@media (min-width: 960px) {
  .grid-story {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    gap: var(--space-7);
  }

  .step {
    justify-content: center;
    min-height: 62vh;
    padding-bottom: var(--space-5);
  }

  .n {
    font-size: 4.5rem;
  }

  .stage {
    top: 10vh;
    height: 80vh;
    background: none;
  }

  .phone {
    --phone-w: min(330px, 100%);
  }

  .chip {
    left: -40px;
    bottom: 18%;
  }
}

@media (min-width: 960px) {
  .step.on h3 {
    transform: translateX(12px);
  }
}
</style>
