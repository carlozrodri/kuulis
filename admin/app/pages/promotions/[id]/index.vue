<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { Page, Promotion, PromotionRide } from '~/types/api'

const { t, locale } = useI18n()
const route = useRoute()
const { request } = useApi()
const auth = useAuth()
const toast = useToast()
const apiError = useApiError()

const id = computed(() => route.params.id as string)
const { data: promotion, status, error } = await useAsyncData(
  `promotion-${id.value}`,
  () => request<Promotion>(`/admin/promotions/${id.value}`),
)

const usage = computed(() => (promotion.value ? budgetUsage(promotion.value) : 0))
const committed = computed(() => committedBudget(promotion.value?.stats))

// ---- Activate / deactivate ------------------------------------------------------------------

const toggling = ref(false)
async function toggleActive() {
  if (!promotion.value) return
  toggling.value = true
  try {
    promotion.value = await request<Promotion>(`/admin/promotions/${id.value}`, {
      method: 'PATCH',
      body: { is_active: !promotion.value.is_active },
    })
    toast.add({ title: promotion.value.is_active ? t('promotions.activated') : t('promotions.deactivated'), color: 'success' })
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    toggling.value = false
  }
}

// ---- Rides that used it ---------------------------------------------------------------------

const page = ref(1)
const limit = 20
const ridesQuery = computed(() => ({ limit, offset: (page.value - 1) * limit }))

const { data: rides, status: ridesStatus, error: ridesError } = await useAsyncData(
  `promotion-${id.value}-rides`,
  () => request<Page<PromotionRide>>(`/admin/promotions/${id.value}/rides`, { query: ridesQuery.value }),
  { watch: [ridesQuery] },
)

const columns = computed<TableColumn<PromotionRide>[]>(() => [
  { accessorKey: 'requested_at', header: t('rides.requestedAt') },
  { accessorKey: 'passenger_name', header: t('rides.passenger') },
  { accessorKey: 'driver_name', header: t('rides.driver') },
  { accessorKey: 'fare', header: t('rides.fare') },
  { accessorKey: 'discount', header: t('rides.discount') },
  { accessorKey: 'total', header: t('rides.totalToPay') },
  { accessorKey: 'status', header: t('rides.status') },
  { accessorKey: 'completed_at', header: t('promotions.completedAt') },
])

const all = (list: string[] | undefined) => (list?.length ? list : null)
</script>

<template>
  <UDashboardPanel id="promotion-detail">
    <template #header>
      <UDashboardNavbar :title="promotion?.name || t('nav.promotions')">
        <template #leading>
          <UButton
            icon="i-lucide-arrow-left"
            color="neutral"
            variant="ghost"
            :aria-label="t('common.back')"
            to="/promotions"
          />
        </template>
        <template #trailing>
          <UBadge
            v-if="promotion"
            :color="promotionStatusColor[promotion.status] ?? 'neutral'"
            variant="subtle"
          >
            {{ t(`promotions.statuses.${promotion.status}`, promotion.status) }}
          </UBadge>
        </template>
        <template #right>
          <template v-if="promotion && auth.isAdmin.value">
            <UButton
              :icon="promotion.is_active ? 'i-lucide-pause' : 'i-lucide-play'"
              color="neutral"
              variant="outline"
              :label="promotion.is_active ? t('promotions.deactivate') : t('promotions.activate')"
              :loading="toggling"
              @click="toggleActive"
            />
            <UButton
              icon="i-lucide-pencil"
              :label="t('promotions.edit')"
              :to="`/promotions/${id}/edit`"
            />
          </template>
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
      <div
        v-else-if="status === 'pending' && !promotion"
        class="grid gap-4 lg:grid-cols-2"
      >
        <USkeleton class="h-48" />
        <USkeleton class="h-48" />
      </div>

      <div
        v-if="promotion"
        class="grid gap-6"
      >
        <div class="grid gap-6 lg:grid-cols-2">
          <UCard>
            <template #header>
              <h2 class="font-semibold">
                {{ t('promotions.conditions') }}
              </h2>
              <p
                v-if="promotion.description"
                class="text-sm text-(--ui-text-muted)"
              >
                {{ promotion.description }}
              </p>
            </template>
            <dl class="grid grid-cols-2 gap-4 text-sm">
              <div>
                <dt class="text-(--ui-text-muted)">
                  {{ t('promotions.code') }}
                </dt>
                <dd>
                  <span
                    v-if="promotion.code"
                    class="font-mono font-medium"
                  >{{ promotion.code }}</span>
                  <span v-else>{{ t('promotions.automatic') }}</span>
                </dd>
              </div>
              <div>
                <dt class="text-(--ui-text-muted)">
                  {{ t('promotions.discount') }}
                </dt>
                <dd>
                  {{ formatDiscount(promotion, locale) }}
                  <span
                    v-if="promotion.discount_type === 'percent' && promotion.max_discount"
                    class="text-(--ui-text-muted)"
                  >· {{ t('promotions.upTo', { amount: formatMoney(promotion.max_discount, locale) }) }}</span>
                </dd>
              </div>
              <div>
                <dt class="text-(--ui-text-muted)">
                  {{ t('promotions.startsAt') }}
                </dt>
                <dd>{{ formatDate(promotion.starts_at, locale) }}</dd>
              </div>
              <div>
                <dt class="text-(--ui-text-muted)">
                  {{ t('promotions.endsAt') }}
                </dt>
                <dd>{{ formatDate(promotion.ends_at, locale) }}</dd>
              </div>
              <div>
                <dt class="text-(--ui-text-muted)">
                  {{ t('promotions.minFare') }}
                </dt>
                <dd>{{ Number(promotion.min_fare) > 0 ? formatMoney(promotion.min_fare, locale) : t('promotions.none') }}</dd>
              </div>
              <div>
                <dt class="text-(--ui-text-muted)">
                  {{ t('promotions.firstRideOnly') }}
                </dt>
                <dd>{{ promotion.first_ride_only ? t('promotions.yes') : t('promotions.no') }}</dd>
              </div>
              <div>
                <dt class="text-(--ui-text-muted)">
                  {{ t('promotions.maxUsesPerPassenger') }}
                </dt>
                <dd>{{ promotion.max_uses_per_passenger }}</dd>
              </div>
              <div>
                <dt class="text-(--ui-text-muted)">
                  {{ t('promotions.maxTotalUses') }}
                </dt>
                <dd>{{ promotion.max_total_uses ?? t('promotions.unlimited') }}</dd>
              </div>
              <div>
                <dt class="text-(--ui-text-muted)">
                  {{ t('promotions.serviceAreas') }}
                </dt>
                <dd>{{ all(promotion.service_areas)?.join(', ') ?? t('promotions.allAreas') }}</dd>
              </div>
              <div>
                <dt class="text-(--ui-text-muted)">
                  {{ t('promotions.vehicleTypes') }}
                </dt>
                <dd>{{ all(promotion.vehicle_types)?.map(v => t(`vehicleTypes.${v}`, v)).join(', ') ?? t('promotions.allVehicles') }}</dd>
              </div>
              <div>
                <dt class="text-(--ui-text-muted)">
                  {{ t('promotions.createdAt') }}
                </dt>
                <dd>{{ formatDate(promotion.created_at, locale) }}</dd>
              </div>
              <div>
                <dt class="text-(--ui-text-muted)">
                  {{ t('promotions.updatedAt') }}
                </dt>
                <dd>{{ formatDate(promotion.updated_at, locale) }}</dd>
              </div>
            </dl>
          </UCard>

          <UCard>
            <template #header>
              <h2 class="font-semibold">
                {{ t('promotions.budgetUsage') }}
              </h2>
            </template>
            <div class="space-y-6">
              <div class="space-y-2">
                <div class="flex items-baseline justify-between gap-2">
                  <span class="text-2xl font-semibold tabular-nums">{{ formatMoney(committed, locale) }}</span>
                  <span class="text-sm text-(--ui-text-muted)">{{ t('promotions.ofBudget', { amount: formatMoney(promotion.budget, locale) }) }}</span>
                </div>
                <UProgress
                  :model-value="usage"
                  :color="usage >= 90 ? 'warning' : 'primary'"
                />
              </div>
              <dl class="grid grid-cols-2 gap-4 text-sm sm:grid-cols-3">
                <div>
                  <dt class="text-(--ui-text-muted)">
                    {{ t('promotions.stats.credited') }}
                  </dt>
                  <dd class="font-medium tabular-nums">
                    {{ formatMoney(promotion.stats.credited, locale) }}
                  </dd>
                </div>
                <div>
                  <dt class="text-(--ui-text-muted)">
                    {{ t('promotions.stats.reserved') }}
                  </dt>
                  <dd class="font-medium tabular-nums">
                    {{ formatMoney(promotion.stats.reserved, locale) }}
                  </dd>
                </div>
                <div>
                  <dt class="text-(--ui-text-muted)">
                    {{ t('promotions.stats.remaining') }}
                  </dt>
                  <dd class="font-medium tabular-nums">
                    {{ formatMoney(promotion.stats.remaining, locale) }}
                  </dd>
                </div>
                <div>
                  <dt class="text-(--ui-text-muted)">
                    {{ t('promotions.stats.uses') }}
                  </dt>
                  <dd class="font-medium tabular-nums">
                    {{ promotion.stats.uses }}
                  </dd>
                </div>
                <div>
                  <dt class="text-(--ui-text-muted)">
                    {{ t('promotions.stats.completed') }}
                  </dt>
                  <dd class="font-medium tabular-nums">
                    {{ promotion.stats.completed }}
                  </dd>
                </div>
              </dl>
              <p class="text-xs text-(--ui-text-muted)">
                {{ t('promotions.stats.help') }}
              </p>
            </div>
          </UCard>
        </div>

        <section class="space-y-3">
          <h2 class="font-semibold">
            {{ t('promotions.rides') }}
          </h2>
          <UAlert
            v-if="ridesError"
            color="error"
            variant="subtle"
            icon="i-lucide-circle-alert"
            :title="apiError(ridesError)"
          />
          <UTable
            :data="rides?.items ?? []"
            :columns="columns"
            :loading="ridesStatus === 'pending'"
            :empty="t('promotions.noRides')"
            class="cursor-pointer"
            @select="(_e: Event, row: { original: PromotionRide }) => navigateTo(`/rides/${row.original.ride_id}`)"
          >
            <template #requested_at-cell="{ row }">
              <span class="whitespace-nowrap">{{ formatDate(row.original.requested_at, locale) }}</span>
            </template>
            <template #passenger_name-cell="{ row }">
              {{ row.original.passenger_name || '—' }}
            </template>
            <template #driver_name-cell="{ row }">
              {{ row.original.driver_name || '—' }}
            </template>
            <template #fare-cell="{ row }">
              <span class="tabular-nums">{{ formatMoney(row.original.fare, locale) }}</span>
            </template>
            <template #discount-cell="{ row }">
              <span class="tabular-nums text-success">−{{ formatMoney(row.original.discount, locale) }}</span>
            </template>
            <template #total-cell="{ row }">
              <span class="font-medium tabular-nums">{{ formatMoney(row.original.total, locale) }}</span>
            </template>
            <template #status-cell="{ row }">
              <UBadge
                :color="rideStatusColor(row.original.status)"
                variant="subtle"
                size="sm"
              >
                {{ t(`rides.statuses.${row.original.status}`, row.original.status) }}
              </UBadge>
            </template>
            <template #completed_at-cell="{ row }">
              <span class="whitespace-nowrap">{{ formatDate(row.original.completed_at, locale) }}</span>
            </template>
          </UTable>

          <div class="flex items-center justify-between border-t border-(--ui-border) pt-4">
            <span class="text-sm text-(--ui-text-muted)">
              {{ t('rides.total', { n: rides?.total ?? 0 }) }}
            </span>
            <UPagination
              v-model:page="page"
              :total="rides?.total ?? 0"
              :items-per-page="limit"
            />
          </div>
        </section>
      </div>
    </template>
  </UDashboardPanel>
</template>
