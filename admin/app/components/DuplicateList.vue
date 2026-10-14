<script setup lang="ts">
import type { DriverDuplicate } from '~/types/api'

/** Doc 12: the same cédula, RIF, plate, phone, Binance Pay ID or device on other accounts. */
defineProps<{ duplicates: DriverDuplicate[] }>()

const { t } = useI18n()
</script>

<template>
  <ul class="space-y-1">
    <li
      v-for="dup in duplicates"
      :key="`${dup.kind}-${dup.user_id}`"
      class="flex flex-wrap items-center gap-2"
    >
      <UBadge
        color="error"
        variant="outline"
        size="sm"
      >
        {{ t(`verification.duplicates.kinds.${dup.kind}`) }}
      </UBadge>
      <NuxtLink
        v-if="dup.driver_id"
        :to="`/drivers/${dup.driver_id}`"
        class="font-medium hover:underline"
      >
        {{ dup.name || '—' }}
      </NuxtLink>
      <NuxtLink
        v-else-if="!dup.deleted"
        :to="`/users/${dup.user_id}`"
        class="font-medium hover:underline"
      >
        {{ dup.name || '—' }}
      </NuxtLink>
      <span
        v-else
        class="font-medium"
      >{{ dup.name || '—' }}</span>
      <span class="text-(--ui-text-muted)">{{ dup.email ?? t('verification.duplicates.erased') }}</span>
      <UBadge
        v-if="dup.deleted"
        color="neutral"
        variant="subtle"
        size="sm"
      >
        {{ t('verification.duplicates.deleted') }}
      </UBadge>
      <UBadge
        v-if="dup.suspended"
        color="error"
        variant="solid"
        size="sm"
      >
        {{ t('verification.duplicates.suspended') }}
      </UBadge>
      <UBadge
        v-if="dup.driver_status"
        :color="driverStatusColor[dup.driver_status]"
        variant="subtle"
        size="sm"
      >
        {{ t(`drivers.statuses.${dup.driver_status}`) }}
      </UBadge>
    </li>
  </ul>
</template>
