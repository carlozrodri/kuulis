<script setup lang="ts">
import type { Promotion } from '~/types/api'

definePageMeta({ roles: ['admin'] })

const { t } = useI18n()

function onSaved(promotion: Promotion) {
  navigateTo(`/promotions/${promotion.id}`, { replace: true })
}
</script>

<template>
  <UDashboardPanel id="promotion-new">
    <template #header>
      <UDashboardNavbar :title="t('promotions.new')">
        <template #leading>
          <UButton
            icon="i-lucide-arrow-left"
            color="neutral"
            variant="ghost"
            :aria-label="t('common.back')"
            to="/promotions"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <PromotionForm @saved="onSaved" />
    </template>
  </UDashboardPanel>
</template>
