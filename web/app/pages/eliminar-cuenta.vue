<script setup lang="ts">
// How to delete an account (Google Play asks for a web page that works without the app installed). The app does
// the deletion itself (Perfil → Ajustes → Privacidad); without it, a message from Contacto starts it.
const { t } = useI18n()
useSeoMeta({ title: () => t('deleteAccount.metaTitle'), description: () => t('deleteAccount.metaDescription') })
</script>

<template>
  <div class="container narrow page">
    <PageHead
      :title="t('deleteAccount.title')"
      :lead="t('deleteAccount.lead')"
    />
    <section>
      <h2>{{ t('deleteAccount.inAppTitle') }}</h2>
      <ol>
        <li>{{ t('deleteAccount.step1') }}</li>
        <li>{{ t('deleteAccount.step2') }}</li>
        <li>{{ t('deleteAccount.step3') }}</li>
      </ol>
    </section>
    <section>
      <h2>{{ t('deleteAccount.noAppTitle') }}</h2>
      <p>
        {{ t('deleteAccount.noAppBody') }}
        <NuxtLinkLocale to="/contacto">
          {{ t('deleteAccount.contactLink') }}
        </NuxtLinkLocale>.
      </p>
    </section>
    <section>
      <h2>{{ t('deleteAccount.whatTitle') }}</h2>
      <p>{{ t('deleteAccount.erased') }}</p>
      <p>{{ t('deleteAccount.kept') }}</p>
      <p>{{ t('deleteAccount.grace') }}</p>
      <p>
        <NuxtLinkLocale to="/legal/privacy">
          {{ t('deleteAccount.privacyLink') }}
        </NuxtLinkLocale>
      </p>
    </section>
  </div>
</template>

<style scoped>
.page {
  padding-bottom: var(--section-y);
}

section + section {
  margin-top: var(--space-6);
}

ol {
  padding-left: 1.25rem;
}
</style>
