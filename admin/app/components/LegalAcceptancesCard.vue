<script setup lang="ts">
/** Which legal texts a user accepted, when and from where (doc 07). */
import type { LegalAcceptance } from '~/types/api'

const props = defineProps<{ userId: string }>()
const { t, locale } = useI18n()
const { request } = useApi()

const { data } = await useAsyncData(`legal-${props.userId}`, () =>
  request<LegalAcceptance[]>(`/admin/users/${props.userId}/legal`).catch(() => []),
)
</script>

<template>
  <UCard>
    <template #header>
      <h2 class="font-semibold">
        {{ t('legal.acceptances') }}
      </h2>
    </template>
    <p
      v-if="!data?.length"
      class="text-sm text-(--ui-text-muted)"
    >
      {{ t('legal.noAcceptances') }}
    </p>
    <ul
      v-else
      class="divide-y divide-(--ui-border) text-sm"
    >
      <li
        v-for="item in data"
        :key="`${item.kind}-${item.version}-${item.created_at}`"
        class="flex flex-wrap justify-between gap-2 py-2"
      >
        <span>{{ t(`legal.kinds.${item.kind}`) }} · v{{ item.version }}</span>
        <span class="text-(--ui-text-muted)">
          {{ formatDate(item.created_at, locale) }}<template v-if="item.platform"> · {{ item.platform }}</template><template v-if="item.ip"> · {{ item.ip }}</template>
        </span>
      </li>
    </ul>
  </UCard>
</template>
