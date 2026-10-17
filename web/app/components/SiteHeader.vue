<script setup lang="ts">
// Site header (docs/website-redesign/04 §2–§3): logo, main links and the download button; below 960 px the
// links move to a full-screen menu that keeps focus inside, closes with Escape and returns focus to its button.
// On a page that starts with a green hero (page meta `heroHeader`), the header wears the hero's green until the
// hero (#hero) has scrolled out from under it, then turns solid light: an IntersectionObserver, no scroll listener.
// Its green is solid, not transparent, so without JavaScript it is still readable over every section.
const open = defineModel<boolean>('open', { default: false })
const { t, locale } = useI18n()
const route = useRoute()

const links = computed(() => [
  { to: '/motorizados', label: t('nav.drivers') },
  { to: '/ayuda', label: t('nav.help') },
])
const menuLinks = computed(() => [
  { to: '/', label: t('nav.home') },
  { to: '/motorizados', label: t('nav.drivers') },
  { to: '/descargar', label: t('nav.download') },
  { to: '/ayuda', label: t('nav.help') },
  { to: '/contacto', label: t('nav.contact') },
])

const heroPassed = ref(false)
const onHero = computed(() => Boolean(route.meta.heroHeader) && !heroPassed.value && !open.value)
let observer: IntersectionObserver | undefined

function watchHero() {
  observer?.disconnect()
  heroPassed.value = false
  const hero = document.getElementById('hero')
  if (!route.meta.heroHeader || !hero) return
  // The hero starts at the top, so it stops intersecting (the area below the header) only once it is above it,
  // also after a jump to an anchor.
  observer = new IntersectionObserver(([entry]) => {
    heroPassed.value = !!entry && !entry.isIntersecting
  }, { rootMargin: '-72px 0px 0px 0px' })
  observer.observe(hero)
}

const toggle = ref<HTMLButtonElement>()
const panel = ref<HTMLElement>()

watch([() => route.fullPath, locale], () => (open.value = false))

function focusables(): HTMLElement[] {
  const inPanel = panel.value ? [...panel.value.querySelectorAll<HTMLElement>('a[href], button')] : []
  return toggle.value ? [toggle.value, ...inPanel] : inPanel
}

function onKeydown(event: KeyboardEvent) {
  if (!open.value) return
  if (event.key === 'Escape') {
    open.value = false
    return
  }
  if (event.key !== 'Tab') return
  const items = focusables()
  const first = items[0]
  const last = items[items.length - 1]
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last?.focus()
  }
  else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first?.focus()
  }
}

watch(open, async (isOpen, wasOpen) => {
  if (!import.meta.client) return
  document.documentElement.classList.toggle('menu-open', isOpen)
  if (isOpen) {
    await nextTick()
    panel.value?.querySelector<HTMLElement>('a[href]')?.focus()
  }
  else if (wasOpen) {
    toggle.value?.focus()
  }
})

onMounted(() => {
  document.addEventListener('keydown', onKeydown)
  watchHero()
})
// After a navigation the new page is rendered on the next tick.
watch(() => route.path, () => nextTick(watchHero))
onBeforeUnmount(() => {
  observer?.disconnect()
  document.removeEventListener('keydown', onKeydown)
  document.documentElement.classList.remove('menu-open')
})
</script>

<template>
  <header
    class="header"
    :class="{ 'on-hero': onHero }"
  >
    <div class="container-wide bar">
      <NuxtLinkLocale
        to="/"
        class="brand"
        aria-label="Kuulis"
      >
        <KuulisWordmark :size="28" />
      </NuxtLinkLocale>

      <nav
        class="nav"
        :aria-label="t('nav.label')"
      >
        <NuxtLinkLocale
          v-for="link in links"
          :key="link.to"
          :to="link.to"
          class="nav-link"
        >
          {{ link.label }}
        </NuxtLinkLocale>
      </nav>

      <div class="actions">
        <LanguageSwitch class="desktop-only" />
        <NuxtLinkLocale
          to="/descargar"
          class="btn btn-primary cta"
        >
          <span class="desktop-only">{{ t('nav.getApp') }}</span>
          <span class="mobile-only">{{ t('nav.download') }}</span>
        </NuxtLinkLocale>
        <button
          ref="toggle"
          type="button"
          class="menu-button mobile-only"
          :class="{ open }"
          :aria-expanded="open"
          aria-controls="mobile-menu"
          :aria-label="open ? t('nav.menuClose') : t('nav.menuOpen')"
          @click="open = !open"
        >
          <span /><span />
        </button>
      </div>
    </div>

    <div
      id="mobile-menu"
      ref="panel"
      class="panel band-ink"
      :class="{ open }"
    >
      <nav :aria-label="t('nav.label')">
        <ul>
          <li
            v-for="link in menuLinks"
            :key="link.to"
          >
            <NuxtLinkLocale :to="link.to">
              {{ link.label }}
            </NuxtLinkLocale>
          </li>
        </ul>
      </nav>
      <div class="panel-foot">
        <LanguageSwitch />
        <NuxtLinkLocale to="/legal">
          {{ t('nav.legal') }}
        </NuxtLinkLocale>
      </div>
    </div>
  </header>
</template>

<style scoped>
.header {
  position: sticky;
  top: 0;
  z-index: 20;
  background: var(--bg);
  border-bottom: 1px solid var(--border);
  transition: background-color var(--dur-base) var(--ease-out), border-color var(--dur-base) var(--ease-out);
}

/* Over the green hero: the hero's own green, white text, the yellow button and dot. */
.header.on-hero {
  background: var(--band-brand);
  border-bottom-color: var(--band-brand);
  color: var(--on-band);
  --focus-outer: var(--on-band);
}

.on-hero .brand,
.on-hero .nav-link {
  color: var(--on-band);
}

.on-hero .nav-link.router-link-active::after {
  background: var(--accent);
}

.on-hero .cta {
  background: var(--accent);
  color: var(--on-accent);
}

.on-hero .menu-button span {
  background: var(--on-band);
}

.bar {
  display: flex;
  align-items: center;
  gap: var(--space-6);
  min-height: 64px;
}

.brand {
  color: var(--primary);
  text-decoration: none;
  margin-right: auto;
}

.nav {
  display: none;
  gap: var(--space-6);
}

.nav-link {
  position: relative;
  color: var(--text);
  font-weight: 600;
  text-decoration: none;
  padding: var(--space-2) 0;
}

/* The brand dot under the current page (green: yellow does not show on light backgrounds). */
.nav-link.router-link-active::after {
  content: '';
  position: absolute;
  left: 50%;
  bottom: -4px;
  width: 6px;
  height: 6px;
  margin-left: -3px;
  border-radius: 50%;
  background: var(--primary);
}

@media (hover: hover) {
  .nav-link:hover {
    color: var(--primary);
  }

  .on-hero .nav-link:hover {
    color: var(--on-band);
    text-decoration: underline;
    text-underline-offset: 6px;
  }
}

.actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.cta {
  position: relative;
  min-height: 40px;
  padding: 0 var(--space-4);
  font-size: var(--font-small);
}

/* 44 px touch target around the 40 px button. */
.cta::before {
  content: '';
  position: absolute;
  inset: -2px;
}

.menu-button {
  display: grid;
  place-content: center;
  gap: 6px;
  width: 44px;
  height: 44px;
  margin-right: calc(var(--space-2) * -1);
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  cursor: pointer;
}

.menu-button span {
  display: block;
  width: 22px;
  height: 2px;
  border-radius: 2px;
  background: var(--text);
  transition: transform var(--dur-base) var(--ease-out);
}

.menu-button.open span:first-child {
  transform: translateY(4px) rotate(45deg);
}

.menu-button.open span:last-child {
  transform: translateY(-4px) rotate(-45deg);
}

.panel {
  position: fixed;
  inset: 65px 0 0;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: var(--space-6) var(--gutter) var(--space-7);
  overflow-y: auto;
  /* visibility (not display) so it can fade in; hidden panels are also out of the tab order. */
  visibility: hidden;
  opacity: 0;
  transform: translateY(-8px);
  transition: opacity var(--dur-base) var(--ease-out), transform var(--dur-base) var(--ease-out), visibility 0s linear var(--dur-base);
}

.panel.open {
  visibility: visible;
  opacity: 1;
  transform: none;
  transition-delay: 0s;
}

.panel ul {
  list-style: none;
  margin: 0;
  padding: 0;
}

.panel li a {
  display: block;
  padding: var(--space-2) 0;
  color: var(--on-band);
  font-size: 1.75rem;
  font-weight: 800;
  letter-spacing: var(--tracking-heading);
  text-decoration: none;
}

.panel li a.router-link-exact-active {
  color: var(--accent);
}

.panel-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding-top: var(--space-6);
  border-top: 1px solid rgb(255 255 255 / 16%);
}

.panel-foot a {
  color: var(--on-band);
  font-weight: 600;
}

.mobile-only {
  display: inline;
}

.desktop-only {
  display: none;
}

.menu-button.mobile-only {
  display: grid;
}

@media (min-width: 960px) {
  .bar {
    min-height: 72px;
  }

  .nav {
    display: flex;
  }

  .mobile-only,
  .menu-button.mobile-only {
    display: none;
  }

  .desktop-only {
    display: inline-flex;
  }

  .cta {
    min-height: 44px;
  }

  .panel {
    display: none;
  }
}
</style>

<style>
/* No page scroll behind the open menu. */
html.menu-open {
  overflow: hidden;
}
</style>
