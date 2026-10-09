<script setup lang="ts">
import type { PersonSummary } from '~/types/api'

/** One side of a report (who reports / who is reported) with what moderation needs to decide. */
defineProps<{ summary: PersonSummary, title: string, highlight?: boolean }>()
defineEmits<{ suspend: [] }>()

const { t, locale } = useI18n()
</script>

<template>
  <UCard :class="highlight ? 'ring-1 ring-warning/50' : ''">
    <template #header>
      <div class="flex items-start justify-between gap-2">
        <div class="min-w-0">
          <p class="text-xs font-medium tracking-wide text-(--ui-text-muted) uppercase">
            {{ title }}
            <template v-if="summary.role_in_ride">
              · {{ t(`reports.roles.${summary.role_in_ride}`) }}
            </template>
          </p>
          <NuxtLink
            :to="`/users/${summary.user_id}`"
            class="font-semibold text-primary hover:underline"
          >
            {{ summary.name || summary.email || summary.user_id.slice(0, 8) }}
          </NuxtLink>
          <p class="text-xs break-all text-(--ui-text-muted)">
            {{ [summary.email, summary.phone].filter(Boolean).join(' · ') }}
          </p>
        </div>
        <UBadge
          v-if="summary.suspension && isSuspensionInForce(summary.suspension)"
          color="error"
          variant="solid"
          icon="i-lucide-user-x"
          class="shrink-0"
        >
          {{ t('suspensions.suspended') }}
        </UBadge>
      </div>
    </template>

    <dl class="grid grid-cols-2 gap-3 text-sm">
      <div>
        <dt class="text-(--ui-text-muted)">
          {{ t('reports.summary.rating') }}
        </dt>
        <dd class="flex items-center gap-1">
          <template v-if="formatRating(summary.rating_avg) && summary.rating_count">
            <UIcon
              name="i-lucide-star"
              class="size-4 text-warning"
            />
            {{ formatRating(summary.rating_avg) }}
            <span class="text-(--ui-text-muted)">({{ summary.rating_count }})</span>
          </template>
          <template v-else>
            —
          </template>
        </dd>
      </div>
      <div>
        <dt class="text-(--ui-text-muted)">
          {{ t('reports.summary.ridesCompleted') }}
        </dt>
        <dd>{{ formatNumber(summary.rides_completed, locale) }}</dd>
      </div>
      <div class="col-span-2">
        <dt class="text-(--ui-text-muted)">
          {{ t('reports.summary.reportsAgainst') }}
        </dt>
        <dd :class="summary.reports_against.total > 1 ? 'font-medium text-warning' : ''">
          {{ t('reports.summary.reportsAgainstValue', {
            total: summary.reports_against.total,
            open: summary.reports_against.open,
            recent: summary.reports_against.last_90_days,
          }) }}
        </dd>
      </div>
      <div
        v-if="summary.driver_profile_id"
        class="col-span-2"
      >
        <dt class="text-(--ui-text-muted)">
          {{ t('reports.summary.driverProfile') }}
        </dt>
        <dd class="flex items-center gap-2">
          <NuxtLink
            :to="`/drivers/${summary.driver_profile_id}`"
            class="text-primary hover:underline"
          >
            {{ t('reports.summary.openDriver') }}
          </NuxtLink>
          <UBadge
            v-if="summary.driver_status"
            :color="driverStatusColor[summary.driver_status] ?? 'neutral'"
            variant="subtle"
            size="sm"
          >
            {{ t(`drivers.statuses.${summary.driver_status}`, summary.driver_status) }}
          </UBadge>
        </dd>
      </div>
    </dl>

    <UAlert
      v-if="summary.suspension && isSuspensionInForce(summary.suspension)"
      class="mt-3"
      color="error"
      variant="subtle"
      icon="i-lucide-ban"
      :title="summary.suspension.until ? t('suspensions.until', { date: formatDate(summary.suspension.until, locale) }) : t('suspensions.indefinite')"
      :description="summary.suspension.reason"
    />

    <template #footer>
      <div class="flex flex-wrap gap-2">
        <UButton
          icon="i-lucide-user-x"
          color="error"
          variant="soft"
          size="sm"
          :label="t('reports.suspendPerson', { name: summary.name || summary.email || '' })"
          @click="$emit('suspend')"
        />
        <UButton
          icon="i-lucide-user"
          color="neutral"
          variant="ghost"
          size="sm"
          :label="t('reports.summary.openUser')"
          :to="`/users/${summary.user_id}`"
        />
      </div>
    </template>
  </UCard>
</template>
