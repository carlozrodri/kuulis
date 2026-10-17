<script setup lang="ts">
// Safety (docs/website-redesign/03 §7): what the app does before, during and after a ride, as stops on one route.
// Each feature was checked in the app and API code (08 §6). The PIN row names the cities where the app asks for it
// and the SOS row the emergency number, both from GET /config/public; without PIN cities the row is left out. The
// page promises no response team: the team alert on SOS is off by default (`safety.sos_team_alert`).
import type { IconName } from '~/components/LineIcon.vue'

const { t } = useI18n()
const { pinAreas, emergency } = await useSafetySettings()
definePageMeta({ heroHeader: true, endsOnBrand: true })

useSeoMeta({
  title: () => t('safety.metaTitle'),
  description: () => t('safety.metaDescription'),
  ogTitle: () => t('safety.metaTitle'),
  ogDescription: () => t('safety.metaDescription'),
})

interface Row { key: string, icon: IconName, params?: Record<string, string> }
const phases = computed<{ key: string, rows: Row[] }[]>(() => [
  { key: 'before', rows: [{ key: 'verified', icon: 'shield-check' }, { key: 'identity', icon: 'id-card' }] },
  {
    key: 'during',
    rows: [
      ...(pinAreas.value.length ? [{ key: 'pin', icon: 'key-round' as const, params: { cities: pinAreas.value.join(', ') } }] : []),
      { key: 'live', icon: 'map-pin' },
      { key: 'chat', icon: 'message-circle' },
      { key: 'other', icon: 'user-plus' },
      { key: 'checkin', icon: 'route' },
    ],
  },
  {
    key: 'trouble',
    rows: [{ key: 'sos', icon: 'phone-call', params: { number: emergency.value } }, { key: 'report', icon: 'flag' }],
  },
  { key: 'after', rows: [{ key: 'rating', icon: 'star' }, { key: 'community', icon: 'book-open' }] },
])
</script>

<template>
  <div>
    <section
      id="hero"
      class="hero band-brand"
    >
      <div class="container-wide grid-hero">
        <div>
          <BrandHeadline
            as="h1"
            class="title"
            :text="t('safety.title')"
          />
          <p class="lead">
            {{ t('safety.lead') }}
          </p>
        </div>
        <BrandPinDigits
          v-if="pinAreas.length"
          class="art"
          digits="4817"
          :label="t('safety.pinLabel')"
          :caption="t('safety.pinCaption')"
        />
      </div>
    </section>

    <div class="container-wide phases">
      <section
        v-for="(phase, index) in phases"
        :key="phase.key"
        v-reveal
        class="phase"
        :class="{ last: index === phases.length - 1 }"
        :aria-labelledby="`phase-${phase.key}`"
      >
        <span
          class="stop"
          aria-hidden="true"
        />
        <h2 :id="`phase-${phase.key}`">
          {{ t(`safety.${phase.key}.title`) }}
        </h2>
        <ul class="rows">
          <li
            v-for="row in phase.rows"
            :key="row.key"
          >
            <LineIcon
              :name="row.icon"
              class="row-icon"
            />
            <div>
              <h3>{{ t(`safety.${phase.key}.${row.key}.title`) }}</h3>
              <p>{{ t(`safety.${phase.key}.${row.key}.body`, row.params ?? {}) }}</p>
              <NuxtLinkLocale
                v-if="row.key === 'community'"
                to="/legal/community"
                class="more"
              >
                {{ t('safety.after.community.link') }}
              </NuxtLinkLocale>
            </div>
          </li>
        </ul>
      </section>

      <p class="notice">
        <LineIcon
          name="phone-call"
          class="notice-icon"
        />
        <span>{{ t('safety.notice', { number: emergency }) }}</span>
      </p>
    </div>

    <DownloadBand
      :title="t('safety.final.title')"
      :body="t('safety.final.body')"
    />
  </div>
</template>

<style scoped>
.hero {
  /* The header (64/72 px) sits on this field. */
  margin-top: -64px;
  padding: calc(64px + clamp(40px, 8vw, 112px)) 0 clamp(64px, 8vw, 128px);
}

.grid-hero {
  display: grid;
  gap: var(--space-7);
  align-items: end;
}

.title {
  max-width: 13ch;
  margin: 0 0 var(--space-5);
  font-size: var(--font-h1);
  line-height: var(--leading-tight);
  letter-spacing: var(--tracking-display);
}

.lead {
  max-width: 34rem;
  margin: 0;
  font-size: var(--font-lead);
  font-weight: 500;
  line-height: 1.45;
}

.art :deep(figcaption) {
  color: var(--on-band);
}

.phases {
  padding-block: var(--section-y);
}

/* Each phase is a stop on the route; the line runs down to the next one and ends in the yellow dot. */
.phase {
  --stop: 28px;

  position: relative;
  padding: 0 0 var(--space-8) calc(var(--stop) + var(--space-5));
}

.phase:not(.last)::before {
  content: '';
  position: absolute;
  top: calc(var(--stop) / 2);
  bottom: calc(-1 * var(--stop) / 2);
  left: calc(var(--stop) / 2 - 3px);
  width: 6px;
  background: var(--primary);
}

.stop {
  position: absolute;
  z-index: 1;
  top: 0;
  left: 0;
  width: var(--stop);
  height: var(--stop);
  border-radius: 50%;
  background: var(--bg);
  box-shadow: inset 0 0 0 6px var(--primary);
}

.last .stop {
  background: var(--accent);
  box-shadow: inset 0 0 0 7px var(--primary);
}

.phase h2 {
  margin: 0 0 var(--space-4);
  font-size: var(--font-h2);
  line-height: var(--stop);
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

.rows p {
  margin: 0;
  max-width: 60ch;
  color: var(--muted);
}

.more {
  display: inline-flex;
  align-items: center;
  min-height: 44px;
  margin-top: var(--space-1);
  color: var(--primary);
  font-weight: 700;
}

.notice {
  display: flex;
  gap: var(--space-4);
  align-items: flex-start;
  max-width: 48rem;
  margin: var(--space-4) 0 0;
  padding: var(--space-5);
  border-radius: var(--radius-md);
  background: var(--surface-alt);
  font-size: 1.125rem;
  font-weight: 700;
}

.notice-icon {
  flex: none;
  color: var(--primary);
}

@media (min-width: 960px) {
  .hero {
    margin-top: -72px;
    padding-top: calc(72px + 112px);
  }

  .grid-hero {
    grid-template-columns: 7fr 5fr;
  }

  .art {
    justify-self: end;
  }

  .phase {
    display: grid;
    grid-template-columns: 4fr 8fr;
    column-gap: var(--space-7);
    align-items: start;
  }

  .phase h2 {
    margin: 0;
  }

  .rows li:first-child {
    padding-top: 0;
    border-top: 0;
  }
}
</style>
