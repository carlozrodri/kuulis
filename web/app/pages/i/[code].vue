<script setup lang="ts">
// Invite page (doc 22): what a driver's WhatsApp invitation opens. No login; shows who invites, the
// code and how to use it, and opens the app with the code typed when it is installed.
const { t } = useI18n()
const route = useRoute()
const { request } = useApi()

const code = computed(() => normalizeInviteCode(String(route.params.code ?? '')))
const { data: invite } = await useAsyncData(`invite-${code.value}`, () =>
  request<PublicInvite>(`/referrals/codes/${encodeURIComponent(code.value)}`).catch(() => null),
)

const title = computed(() => (invite.value?.name ? t('invite.titleNamed', { name: invite.value.name }) : t('invite.title')))
useSeoMeta({
  title: () => t('invite.metaTitle'),
  description: () => t('invite.metaDescription'),
  ogTitle: () => title.value,
  ogDescription: () => t('invite.metaDescription'),
  robots: 'noindex, nofollow',
})

const copied = ref(false)
const steps = computed(() => (['download', 'signUp', 'code'] as const).map(key => ({ key, body: t(`invite.steps.${key}`) })))

async function copy() {
  try {
    await navigator.clipboard.writeText(code.value)
    copied.value = true
    setTimeout(() => (copied.value = false), 2000)
  }
  catch {
    copied.value = false
  }
}
</script>

<template>
  <UtilityCard v-if="!invite">
    <h1>{{ t('invite.invalidTitle') }}</h1>
    <p class="muted">
      {{ t('invite.invalidBody') }}
    </p>
    <NuxtLinkLocale
      class="btn btn-primary wide"
      to="/motorizados"
    >
      {{ t('invite.drivers') }}
    </NuxtLinkLocale>
  </UtilityCard>

  <div
    v-else
    class="container-wide invite"
  >
    <div class="grid-invite">
      <div>
        <PageHead
          :stop="t('invite.stop')"
          :title="title"
          :lead="t('invite.lead')"
        />
        <p
          v-if="invite.program.active && invite.program.referred_free_month"
          class="notice notice-success"
        >
          {{ t('invite.freeMonth', { trips: invite.program.required_trips, days: invite.program.window_days }) }}
        </p>
        <p
          v-if="!invite.program.active"
          class="notice paused"
        >
          {{ t('invite.paused') }}
        </p>
      </div>

      <div class="card code-card">
        <p class="label">
          {{ t('invite.codeLabel') }}
        </p>
        <p class="code">
          {{ formatInviteCode(invite.code) }}
        </p>
        <button
          type="button"
          class="btn btn-ghost"
          @click="copy"
        >
          {{ copied ? t('invite.copied') : t('invite.copy') }}
        </button>
        <span
          class="sr-only"
          aria-live="polite"
        >{{ copied ? t('invite.copied') : '' }}</span>
      </div>
    </div>

    <RouteStops
      class="steps"
      :items="steps"
    />

    <div class="actions">
      <NuxtLinkLocale
        class="btn btn-primary"
        to="/descargar"
      >
        {{ t('invite.download') }}
      </NuxtLinkLocale>
      <a
        class="btn btn-ghost"
        :href="appInviteLink(invite.code)"
      >{{ t('invite.openApp') }}</a>
    </div>
    <p class="more">
      {{ t('invite.more') }}
      <NuxtLinkLocale to="/motorizados">
        {{ t('invite.drivers') }}
      </NuxtLinkLocale>
    </p>
  </div>
</template>

<style scoped>
.invite {
  padding-bottom: var(--section-y);
}

.grid-invite {
  display: grid;
  gap: var(--space-6);
  align-items: end;
  margin-bottom: var(--space-8);
}

.notice {
  max-width: 40rem;
  margin: 0;
}

.paused {
  background: var(--surface-alt);
}

.code-card {
  text-align: center;
}

.label {
  margin: 0;
  color: var(--muted);
  font-size: var(--font-small);
  font-weight: 600;
}

.code {
  margin: var(--space-2) 0 var(--space-4);
  font-size: clamp(2rem, 1.5rem + 2vw, 2.75rem);
  font-weight: 800;
  letter-spacing: 0.12em;
  font-variant-numeric: tabular-nums;
}

.steps {
  margin-bottom: var(--space-7);
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

.more {
  margin: 0;
  color: var(--muted);
}

.more a {
  color: var(--primary);
  font-weight: 700;
}

@media (min-width: 960px) {
  .grid-invite {
    grid-template-columns: 7fr 4fr;
    column-gap: var(--space-9);
  }

  .code-card {
    margin-bottom: var(--space-7);
  }
}
</style>
