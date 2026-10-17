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
  <section class="section">
    <div class="container narrow">
      <div
        v-if="!invite"
        class="card"
      >
        <KuulisWordmark
          :size="26"
          class="mark"
        />
        <h1>{{ t('invite.invalidTitle') }}</h1>
        <p class="muted">
          {{ t('invite.invalidBody') }}
        </p>
        <NuxtLink
          class="btn btn-primary"
          to="/motorizados"
        >
          {{ t('invite.drivers') }}
        </NuxtLink>
      </div>

      <template v-else>
        <span class="eyebrow">{{ t('invite.eyebrow') }}</span>
        <h1>{{ title }}</h1>
        <p class="lead">
          {{ t('invite.lead') }}
        </p>
        <p
          v-if="invite.program.active && invite.program.referred_free_month"
          class="notice notice-success"
        >
          {{ t('invite.freeMonth', { trips: invite.program.required_trips, days: invite.program.window_days }) }}
        </p>
        <p
          v-if="!invite.program.active"
          class="notice"
        >
          {{ t('invite.paused') }}
        </p>

        <div class="card code-card">
          <p class="muted small">
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
        </div>

        <ol class="steps">
          <li>{{ t('invite.steps.download') }}</li>
          <li>{{ t('invite.steps.signUp') }}</li>
          <li>{{ t('invite.steps.code') }}</li>
        </ol>

        <div class="actions">
          <NuxtLink
            class="btn btn-accent"
            to="/descargar"
          >
            {{ t('invite.download') }}
          </NuxtLink>
          <a
            class="btn btn-ghost"
            :href="appInviteLink(invite.code)"
          >{{ t('invite.openApp') }}</a>
        </div>
        <p class="muted small">
          {{ t('invite.more') }}
          <NuxtLink to="/motorizados">
            {{ t('invite.drivers') }}
          </NuxtLink>
        </p>
      </template>
    </div>
  </section>
</template>

<style scoped>
.mark {
  color: var(--primary);
  display: block;
  margin-bottom: 24px;
}

.code-card {
  margin: 24px 0;
  text-align: center;
}

.code {
  font-size: 2.2rem;
  font-weight: 800;
  letter-spacing: 0.12em;
  margin: 4px 0 12px;
  font-variant-numeric: tabular-nums;
}

.steps {
  display: grid;
  gap: 8px;
  margin: 0 0 24px;
  padding-left: 1.25rem;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
}

.small {
  font-size: 0.9rem;
}
</style>
