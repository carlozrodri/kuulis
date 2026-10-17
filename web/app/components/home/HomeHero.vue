<script setup lang="ts">
// Home hero (docs/website-redesign/03 §5.1): what Kuulis is and the way to download, on a flat green field.
// The route draws itself to the yellow dot; the Ávila closes the field. The header sits on this field until the
// sentinel at its end scrolls past (SiteHeader).
const { t } = useI18n()
</script>

<template>
  <section class="hero band-brand">
    <div class="container-wide grid-hero">
      <div class="copy">
        <BrandHeadline
          as="h1"
          class="title"
          :text="t('home.hero.title')"
        />
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
      <BrandRouteLine class="art" />
    </div>
    <BrandAvilaRidge class="ridge" />
    <div
      id="hero-end"
      aria-hidden="true"
    />
  </section>
</template>

<style scoped>
.hero {
  position: relative;
  /* The header (64/72 px) sits on this field. */
  margin-top: -64px;
  padding-top: calc(64px + clamp(24px, 6vw, 96px));
  overflow: hidden;
}

.grid-hero {
  display: grid;
  gap: var(--space-6);
  align-items: center;
}

.title {
  max-width: 12ch;
  margin: 0 0 var(--space-5);
  font-size: var(--font-display);
  line-height: var(--leading-tight);
  letter-spacing: var(--tracking-display);
}

.lead {
  max-width: 34rem;
  margin: 0 0 var(--space-6);
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
  font-size: var(--font-small);
}

.art {
  justify-self: center;
  width: min(100%, 420px);
  color: var(--on-band);
}

.ridge {
  position: relative;
  margin-top: clamp(-40px, -3vw, 0px);
  color: var(--primary-deep);
}

#hero-end {
  position: absolute;
  bottom: 0;
  height: 1px;
  width: 1px;
}

/* Phones: the headline, lead and main button fit in a 360×640 screen; the route is a small accent below. */
@media (max-width: 599px) {
  .art {
    width: 70%;
    max-width: 260px;
    justify-self: end;
    margin-top: calc(-1 * var(--space-5));
  }
}

@media (min-width: 960px) {
  .hero {
    margin-top: -72px;
    padding-top: calc(72px + 72px);
  }

  .grid-hero {
    grid-template-columns: 7fr 5fr;
  }

  .title {
    max-width: 13ch;
  }
}
</style>
