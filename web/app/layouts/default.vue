<script setup lang="ts">
const { t, locale, setLocale } = useI18n()
const config = useRuntimeConfig()
const route = useRoute()
const open = ref(false)
watch([() => route.fullPath, locale], () => (open.value = false))

const links = computed(() => [
  { to: '/motorizados', label: t('nav.drivers') },
  { to: '/descargar', label: t('nav.download') },
  { to: '/legal', label: t('nav.legal') },
])
const other = computed(() => (locale.value === 'es' ? 'en' : 'es'))
const year = new Date().getFullYear()
</script>

<template>
  <div class="page">
    <a
      href="#main"
      class="sr-only"
    >{{ t('nav.skip') }}</a>
    <header class="header">
      <div class="container bar">
        <NuxtLink
          to="/"
          class="brand"
        >
          <KuulisWordmark :size="28" />
        </NuxtLink>
        <nav
          class="nav"
          :class="{ open }"
          :aria-label="t('nav.label')"
        >
          <NuxtLink
            v-for="link in links"
            :key="link.to"
            :to="link.to"
          >
            {{ link.label }}
          </NuxtLink>
          <button
            type="button"
            class="lang"
            :aria-label="t('nav.language')"
            @click="setLocale(other)"
          >
            {{ other.toUpperCase() }}
          </button>
          <NuxtLink
            to="/descargar"
            class="btn btn-accent cta"
          >
            {{ t('nav.getApp') }}
          </NuxtLink>
        </nav>
        <button
          type="button"
          class="menu"
          :aria-expanded="open"
          :aria-label="t('nav.menu')"
          @click="open = !open"
        >
          <span /><span /><span />
        </button>
      </div>
    </header>

    <main id="main">
      <slot />
    </main>

    <footer class="footer">
      <div class="container cols">
        <div>
          <KuulisWordmark :size="24" />
          <p class="muted small">
            {{ t('footer.tagline') }}
          </p>
        </div>
        <div class="links">
          <NuxtLink to="/motorizados">
            {{ t('nav.drivers') }}
          </NuxtLink>
          <NuxtLink to="/descargar">
            {{ t('nav.download') }}
          </NuxtLink>
          <NuxtLink to="/legal/terms">
            {{ t('legal.kinds.terms') }}
          </NuxtLink>
          <NuxtLink to="/legal/privacy">
            {{ t('legal.kinds.privacy') }}
          </NuxtLink>
          <NuxtLink to="/legal/community">
            {{ t('legal.kinds.community') }}
          </NuxtLink>
          <a
            v-if="config.public.supportEmail"
            :href="`mailto:${config.public.supportEmail}`"
          >{{ config.public.supportEmail }}</a>
        </div>
      </div>
      <div class="container small muted copy">
        © {{ year }} Kuulis · {{ t('footer.made') }}
      </div>
    </footer>
  </div>
</template>

<style scoped>
.page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

main {
  flex: 1;
}

.header {
  position: sticky;
  top: 0;
  z-index: 10;
  background: color-mix(in srgb, var(--bg) 88%, transparent);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--border);
}

.bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 68px;
}

.brand {
  color: var(--primary);
  text-decoration: none;
}

.nav {
  display: flex;
  align-items: center;
  gap: 22px;
}

.nav a:not(.btn) {
  color: var(--text);
  font-weight: 600;
  text-decoration: none;
}

.nav a.router-link-active:not(.btn) {
  color: var(--primary);
}

.lang {
  border: 0;
  background: var(--surface-alt);
  color: var(--text);
  font: inherit;
  font-weight: 700;
  font-size: 0.8rem;
  border-radius: 999px;
  padding: 6px 10px;
  cursor: pointer;
}

.cta {
  min-height: 44px;
  padding: 0 18px;
}

.menu {
  display: none;
  border: 0;
  background: transparent;
  padding: 10px;
  cursor: pointer;
}

.menu span {
  display: block;
  width: 22px;
  height: 2px;
  margin: 5px 0;
  background: var(--text);
  border-radius: 2px;
}

@media (max-width: 760px) {
  .menu {
    display: block;
  }

  .nav {
    display: none;
    position: absolute;
    top: 68px;
    left: 0;
    right: 0;
    flex-direction: column;
    align-items: stretch;
    gap: 4px;
    padding: 12px 20px 20px;
    background: var(--bg);
    border-bottom: 1px solid var(--border);
  }

  .nav.open {
    display: flex;
  }

  .nav a:not(.btn) {
    padding: 12px 0;
  }

  .lang {
    align-self: flex-start;
    margin: 8px 0;
  }
}

.footer {
  border-top: 1px solid var(--border);
  padding: 40px 0 28px;
  margin-top: 40px;
}

.cols {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 24px;
}

.footer .links {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 22px;
  align-items: flex-start;
}

.footer .links a {
  color: var(--text);
  text-decoration: none;
  font-weight: 600;
  font-size: 0.95rem;
}

.small {
  font-size: 0.9rem;
}

.copy {
  margin-top: 24px;
}
</style>
