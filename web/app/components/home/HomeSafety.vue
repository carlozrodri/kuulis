<script setup lang="ts">
// Safety (docs/website-redesign/03 §5.5): four features, each checked in the app (08 §6). The PIN row names the
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
  <section class="section safety">
    <div class="container-wide grid-safety">
      <div class="intro">
        <BrandHeadline :text="t('home.safety.title')" />
        <BrandPinDigits
          v-if="pinAreas.length"
          class="pin"
          digits="4817"
          :label="t('home.safety.pinLabel')"
          :caption="t('home.safety.pinCaption')"
        />
      </div>
      <ul class="rows">
        <li
          v-for="row in rows"
          :key="row.key"
        >
          <LineIcon
            :name="row.icon"
            class="row-icon"
          />
          <div>
            <h3>{{ t(`home.safety.${row.key}.title`) }}</h3>
            <p>{{ row.body }}</p>
          </div>
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

.grid-safety {
  display: grid;
  gap: var(--space-7);
}

.intro :deep(h2) {
  max-width: 16ch;
  margin: 0 0 var(--space-6);
  font-size: var(--font-h2);
  line-height: var(--leading-heading);
  letter-spacing: var(--tracking-heading);
}

.rows {
  margin: 0;
  padding: 0;
  list-style: none;
}

.rows li {
  display: flex;
  gap: var(--space-4);
  padding: var(--space-5) 0;
  border-top: 1px solid var(--border);
}

.rows li:last-child {
  border-bottom: 1px solid var(--border);
}

.row-icon {
  flex: none;
  margin-top: 2px;
  color: var(--primary);
}

h3 {
  margin: 0 0 var(--space-1);
  font-size: var(--font-h3);
}

p {
  margin: 0;
  color: var(--muted);
}

.more {
  color: var(--primary);
  font-weight: 700;
}

@media (min-width: 960px) {
  .grid-safety {
    grid-template-columns: 5fr 6fr;
    column-gap: var(--space-9);
    align-items: start;
  }

  .intro {
    grid-row: span 2;
  }

  .more {
    grid-column: 2;
    margin-top: calc(-1 * var(--space-5));
  }
}
</style>
