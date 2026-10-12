<script setup lang="ts">
import type { FeatureFlag } from '~/types/api'

definePageMeta({ permission: 'flags.view' })

const { t } = useI18n()
const { request } = useApi()
const apiError = useApiError()
const auth = useAuth()
const canManage = computed(() => auth.can('flags.manage'))

const { data: flags, status, error } = await useAsyncData('feature-flags', () => request<FeatureFlag[]>('/admin/flags'))
const areas = await useServiceAreaNames()

function onSaved(flag: FeatureFlag) {
  flags.value = (flags.value ?? []).map(f => (f.key === flag.key ? flag : f))
}
</script>

<template>
  <UDashboardPanel id="flags">
    <template #header>
      <UDashboardNavbar :title="t('nav.flags')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <p class="max-w-3xl text-sm text-(--ui-text-muted)">
        {{ t('flags.help') }}
      </p>
      <UAlert
        v-if="error && !flags"
        color="error"
        variant="subtle"
        icon="i-lucide-circle-alert"
        :title="apiError(error)"
      />
      <USkeleton
        v-else-if="status === 'pending' && !flags"
        class="h-96 max-w-3xl"
      />
      <div
        v-if="flags"
        class="grid max-w-3xl gap-6"
      >
        <UAlert
          v-if="!canManage"
          color="neutral"
          variant="subtle"
          icon="i-lucide-lock"
          :title="t('flags.readOnly')"
        />
        <p
          v-if="!flags.length"
          class="text-sm text-(--ui-text-muted)"
        >
          {{ t('common.empty') }}
        </p>
        <ControlFlagCard
          v-for="flag in flags"
          :key="flag.key"
          :flag="flag"
          :areas="areas"
          :can-manage="canManage"
          @saved="onSaved"
        />
      </div>
    </template>
  </UDashboardPanel>
</template>
