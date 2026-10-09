<script setup lang="ts">
import type { Promotion } from '~/types/api'

definePageMeta({ roles: ['admin'] })

const { t } = useI18n()
const route = useRoute()
const { request } = useApi()
const apiError = useApiError()

const id = computed(() => route.params.id as string)
const { data: promotion, status, error } = await useAsyncData(
  `promotion-${id.value}`,
  () => request<Promotion>(`/admin/promotions/${id.value}`),
)

function onSaved(saved: Promotion) {
  promotion.value = saved
  navigateTo(`/promotions/${saved.id}`)
}
</script>

<template>
  <UDashboardPanel id="promotion-edit">
    <template #header>
      <UDashboardNavbar :title="promotion ? t('promotions.editTitle', { name: promotion.name }) : t('nav.promotions')">
        <template #leading>
          <UButton
            icon="i-lucide-arrow-left"
            color="neutral"
            variant="ghost"
            :aria-label="t('common.back')"
            :to="`/promotions/${id}`"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <UAlert
        v-if="error && !promotion"
        color="error"
        variant="subtle"
        icon="i-lucide-circle-alert"
        :title="apiError(error)"
      />
      <USkeleton
        v-else-if="status === 'pending' && !promotion"
        class="h-96 max-w-3xl"
      />
      <PromotionForm
        v-if="promotion"
        :promotion="promotion"
        @saved="onSaved"
      />
    </template>
  </UDashboardPanel>
</template>
