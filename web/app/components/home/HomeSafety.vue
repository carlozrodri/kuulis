<script setup lang="ts">
// Safety (Kuulis de noche, on the night field): four features, each checked in the app (08 §6). The PIN row names the
// cities where the app asks for it and the SOS row the emergency number, both from GET /config/public; without
// the PIN cities the row is left out.
const { t } = useI18n()
const { pinAreas, emergency } = await useSafetySettings()

const rows = computed(() => [
  { key: 'verified', icon: 'shield-check' as const, body: t('home.safety.verified.body') },
  ...(pinAreas.value.length
    ? [{ key: 'pin', icon: 'key-round' as const, body: t('home.safety.pin.body', { cities: pinAreas.value.join(', ') }) }]
    : []),
  { key: 'live', icon: 'map-pin' as const, body: t('home.safety.live.body') },
  { key: 'sos', icon: 'phone-call' as const, body: t('home.safety.sos.body', { number: emergency.value }) },
])
</script>

<template>
  <section class="safety band-ink">
    <div class="container-wide">
      <p class="eyebrow">
        {{ t('home.eyebrow.safety') }}
      </p>
      <div
        v-reveal
        class="intro"
      >
        <BrandHeadline :text="t('home.safety.title')" />
        <BrandPinDigits
          v-if="pinAreas.length"
          class="pin"
          digits="4817"
          :label="t('home.safety.pinLabel')"
          :caption="t('home.safety.pinCaption')"
        />
      </div>
      <ul
        v-reveal
        class="grid"
      >
        <li
          v-for="row in rows"
          :key="row.key"
        >
          <span
            v-if="row.key === 'sos'"
            class="sos"
            aria-hidden="true"
          >SOS</span>
          <LineIcon
            v-else
            :name="row.icon"
            class="row-icon"
          />
          <h3>{{ t(`home.safety.${row.key}.title`) }}</h3>
          <p>{{ row.body }}</p>
        </li>
      </ul>
      <NuxtLinkLocale
        to="/seguridad"
        class="more"
      >
        {{ t('home.safety.more') }}
      </NuxtLinkLocale>
    </div>
  </section>
</template>

<style scoped>
.safety {
  padding: var(--section-y) 0;
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

.intro {
  display: grid;
  gap: var(--space-6);
  align-items: end;
}

.intro :deep(h2) {
  max-width: 20ch;
  margin: 0;
  font-size: var(--font-h2);
  line-height: var(--leading-heading);
}

.grid {
  display: grid;
  margin: var(--space-7) 0 0;
  padding: 0;
  list-style: none;
  border-top: 1px solid var(--on-band-line);
}

.grid li {
  padding: var(--space-5) var(--space-5) var(--space-6) 0;
  border-bottom: 1px solid var(--on-band-line);
}

.row-icon {
  color: var(--accent);
}

.sos {
  display: inline-grid;
  place-items: center;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: #d92d20;
  color: #fff;
  font-family: var(--font-poster);
  font-size: 0.8rem;
  font-weight: 900;
  letter-spacing: 0.06em;
  animation: sos 2s 2;
}

@keyframes sos {
  0% {
    box-shadow: 0 0 0 0 rgb(217 45 32 / 60%);
  }

  70%,
  100% {
    box-shadow: 0 0 0 16px rgb(217 45 32 / 0%);
  }
}

h3 {
  margin: var(--space-3) 0 var(--space-1);
  font-size: 1.35rem;
  letter-spacing: -0.02em;
}

p {
  max-width: 34ch;
  margin: 0;
  color: var(--on-band-soft);
}

.more {
  display: inline-flex;
  align-items: center;
  min-height: 44px;
  margin-top: var(--space-5);
  color: var(--accent);
  font-weight: 700;
}

@media (min-width: 760px) {
  .grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (min-width: 960px) {
  .intro {
    grid-template-columns: minmax(0, 1.4fr) minmax(0, 0.6fr);
  }

  .grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}
</style>
