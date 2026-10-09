<script setup lang="ts">
import type { PartyRef } from '~/types/api'

/** A driver in a list row: name linking to their wallet, email below. */
defineProps<{ party: PartyRef | null | undefined, empty?: string }>()
</script>

<template>
  <div v-if="party">
    <NuxtLink
      :to="walletLink(party.id)"
      class="font-medium text-primary hover:underline"
    >
      {{ party.name || party.email || party.id.slice(0, 8) }}
    </NuxtLink>
    <p
      v-if="party.email && party.name"
      class="text-xs text-(--ui-text-muted)"
    >
      {{ party.email }}
    </p>
  </div>
  <span
    v-else
    class="text-(--ui-text-muted)"
  >{{ empty ?? '—' }}</span>
</template>
