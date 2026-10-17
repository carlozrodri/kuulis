<script setup lang="ts">
// Site footer (docs/website-redesign/03 §3): the Ávila skyline, brand, site links, support contacts (only when
// configured) and the legal texts.
const { t } = useI18n()
const { whatsapp, email } = await useSupport()
const year = new Date().getFullYear()
// A page that ends on a green field (page meta `endsOnBrand`) has the Ávila rise from that field.
const route = useRoute()

const legal = ['terms', 'privacy', 'community', 'driver_terms', 'wallet'] as const
</script>

<template>
  <footer
    class="footer"
    :class="{ 'on-brand': route.meta.endsOnBrand }"
  >
    <BrandAvilaRidge class="skyline" />
    <div class="band">
      <div class="container-wide grid-footer">
        <div class="brand">
          <NuxtLinkLocale
            to="/"
            class="logo"
            aria-label="Kuulis"
          >
            <KuulisWordmark :size="32" />
          </NuxtLinkLocale>
          <p>{{ t('footer.tagline') }}</p>
        </div>

        <nav :aria-label="t('footer.kuulis')">
          <h2>{{ t('footer.kuulis') }}</h2>
          <ul>
            <li>
              <NuxtLinkLocale to="/">
                {{ t('nav.home') }}
              </NuxtLinkLocale>
            </li>
            <li>
              <NuxtLinkLocale to="/motorizados">
                {{ t('nav.drivers') }}
              </NuxtLinkLocale>
            </li>
            <li>
              <NuxtLinkLocale to="/descargar">
                {{ t('nav.download') }}
              </NuxtLinkLocale>
            </li>
          </ul>
        </nav>

        <nav :aria-label="t('footer.help')">
          <h2>{{ t('footer.help') }}</h2>
          <ul>
            <li>
              <NuxtLinkLocale to="/ayuda">
                {{ t('footer.helpCenter') }}
              </NuxtLinkLocale>
            </li>
            <li>
              <NuxtLinkLocale to="/contacto">
                {{ t('nav.contact') }}
              </NuxtLinkLocale>
            </li>
            <li v-if="whatsapp">
              <a
                :href="whatsapp"
                rel="noopener"
                target="_blank"
              >{{ t('footer.whatsapp') }}</a>
            </li>
            <li v-if="email">
              <a :href="`mailto:${email}`">{{ email }}</a>
            </li>
          </ul>
        </nav>

        <nav :aria-label="t('footer.legal')">
          <h2>{{ t('footer.legal') }}</h2>
          <ul>
            <li
              v-for="kind in legal"
              :key="kind"
            >
              <NuxtLinkLocale :to="`/legal/${kind}`">
                {{ t(`legal.kinds.${kind}`) }}
              </NuxtLinkLocale>
            </li>
          </ul>
        </nav>
      </div>

      <div class="container-wide bottom">
        <p>© {{ year }} Kuulis · {{ t('footer.made') }}</p>
        <LanguageSwitch />
      </div>
    </div>
  </footer>
</template>

<style scoped>
.footer {
  --footer-bg: var(--primary-deep);

  margin-top: var(--space-8);
  color: var(--on-band);
}

.skyline {
  color: var(--footer-bg);
  margin-bottom: -1px;
}

.on-brand {
  margin-top: 0;
}

.on-brand .skyline {
  background: var(--band-brand);
}

.band {
  background: var(--footer-bg);
  padding: var(--space-6) 0 var(--space-5);
  --focus-outer: var(--on-band);
}

.grid-footer {
  display: grid;
  gap: var(--space-6) var(--space-5);
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.brand {
  grid-column: 1 / -1;
}

.logo {
  color: var(--on-band);
  text-decoration: none;
}

.brand p {
  margin: var(--space-3) 0 0;
  max-width: 30ch;
  color: rgb(255 255 255 / 78%);
}

h2 {
  margin: 0 0 var(--space-3);
  font-size: var(--font-label);
  font-weight: 700;
  letter-spacing: var(--tracking-label);
  text-transform: uppercase;
  color: rgb(255 255 255 / 70%);
}

ul {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: var(--space-1);
}

a {
  display: inline-block;
  padding: var(--space-1) 0;
  color: var(--on-band);
  font-weight: 600;
  text-decoration: none;
  overflow-wrap: anywhere;
}

@media (hover: hover) {
  a:hover {
    text-decoration: underline;
  }
}

.bottom {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  margin-top: var(--space-7);
  padding-top: var(--space-4);
  border-top: 1px solid rgb(255 255 255 / 16%);
  font-size: var(--font-small);
  color: rgb(255 255 255 / 78%);
}

.bottom p {
  margin: 0;
}

.bottom .lang {
  color: var(--on-band);
}

@media (min-width: 720px) {
  .grid-footer {
    grid-template-columns: 1.4fr repeat(3, minmax(0, 1fr));
  }

  .brand {
    grid-column: auto;
  }
}
</style>
