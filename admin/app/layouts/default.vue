<script setup lang="ts">
import type { NavigationMenuItem } from '@nuxt/ui'

const { t, locale, locales, setLocale } = useI18n()
const auth = useAuth()
const config = useRuntimeConfig()

const links = computed<NavigationMenuItem[]>(() => [
  { label: t('nav.dashboard'), icon: 'i-lucide-layout-dashboard', to: '/' },
  { label: t('nav.users'), icon: 'i-lucide-users', to: '/users' },
  { label: t('nav.notifications'), icon: 'i-lucide-bell', to: '/notifications' },
  { label: t('nav.profile'), icon: 'i-lucide-user-cog', to: '/profile' },
])

const localeItems = computed(() =>
  locales.value.map(l => ({ label: l.name ?? l.code, value: l.code })),
)
</script>

<template>
  <UDashboardGroup>
    <UDashboardSidebar
      collapsible
      resizable
    >
      <template #header="{ collapsed }">
        <div class="flex items-center gap-2 font-semibold">
          <UIcon
            name="i-lucide-shield-check"
            class="size-5 text-primary"
          />
          <span v-if="!collapsed">Kuulis Admin</span>
          <UBadge
            v-if="!collapsed && config.public.appEnv !== 'production'"
            color="warning"
            variant="subtle"
            size="sm"
          >
            {{ config.public.appEnv }}
          </UBadge>
        </div>
      </template>

      <template #default="{ collapsed }">
        <UNavigationMenu
          :items="links"
          orientation="vertical"
          :collapsed="collapsed"
        />
      </template>

      <template #footer="{ collapsed }">
        <div class="flex w-full flex-col gap-2">
          <USelect
            v-if="!collapsed"
            :model-value="locale"
            :items="localeItems"
            size="sm"
            @update:model-value="(v) => setLocale(v as 'es' | 'en')"
          />
          <UButton
            :label="collapsed ? undefined : t('auth.logout')"
            icon="i-lucide-log-out"
            color="neutral"
            variant="ghost"
            block
            @click="auth.logout()"
          />
        </div>
      </template>
    </UDashboardSidebar>

    <slot />
  </UDashboardGroup>
</template>
