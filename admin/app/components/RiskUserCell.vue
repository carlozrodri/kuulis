<script setup lang="ts">
import type { RiskUser } from '~/types/api'

/** A person in a risk row (doc 16): name linking to their driver or user page, email and risk score. */
defineProps<{ user: RiskUser | null | undefined, score?: boolean }>()

const { t } = useI18n()
</script>

<template>
  <div v-if="user">
    <NuxtLink
      :to="riskUserLink(user)"
      class="font-medium text-primary hover:underline"
      @click.stop
    >
      {{ user.name || user.email || user.id.slice(0, 8) }}
    </NuxtLink>
    <UBadge
      v-if="score"
      :color="riskScoreColor(user.risk_score)"
      variant="subtle"
      size="sm"
      class="ml-1 tabular-nums"
      :title="t('risk.score')"
    >
      {{ user.risk_score }}
    </UBadge>
    <p
      v-if="user.name"
      class="text-xs text-(--ui-text-muted)"
    >
      {{ user.email ?? t('verification.duplicates.erased') }}
    </p>
  </div>
  <span
    v-else
    class="text-(--ui-text-muted)"
  >—</span>
</template>
