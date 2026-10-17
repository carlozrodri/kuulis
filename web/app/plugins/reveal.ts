/**
 * `v-reveal`: a section's content rises 16 px and fades in the first time it scrolls into view
 * (docs/website-redesign/04 §6, animation 2). Nothing is hidden on the server or without JavaScript, nothing that is
 * already on screen when the page opens, and nothing with reduced motion: the class that hides is only added here,
 * in the browser, to sections still below the fold.
 */
export default defineNuxtPlugin((nuxtApp) => {
  let observer: IntersectionObserver | undefined

  nuxtApp.vueApp.directive<HTMLElement>('reveal', {
    getSSRProps: () => ({}),
    mounted(el) {
      if (!('IntersectionObserver' in window) || matchMedia('(prefers-reduced-motion: reduce)').matches) return
      if (el.getBoundingClientRect().top < window.innerHeight) return
      observer ??= new IntersectionObserver((entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue
          entry.target.classList.remove('reveal-pending')
          observer!.unobserve(entry.target)
        }
      }, { rootMargin: '0px 0px -15% 0px' })
      el.classList.add('reveal', 'reveal-pending')
      observer.observe(el)
    },
    unmounted(el) {
      observer?.unobserve(el)
    },
  })
})
