<script setup lang="ts">
import type { AdminRide, RideMessage, RideRating } from '~/types/api'
import type { MapLine, MapMarker } from '~/utils/geo'

const { t, te, locale } = useI18n()
const route = useRoute()
const { request } = useApi()
const toast = useToast()
const apiError = useApiError()

const id = computed(() => route.params.id as string)
const { data: ride, refresh, status, error } = await useAsyncData(
  `ride-${id.value}`,
  () => request<AdminRide>(`/admin/rides/${id.value}`),
)

const active = computed(() => !!ride.value && isActiveRide(ride.value.status))

// Keep an in-flight ride fresh (driver position, status, chat) without a manual reload.
let timer: ReturnType<typeof setInterval> | undefined
watch(active, (value) => {
  clearInterval(timer)
  if (value) {
    timer = setInterval(() => {
      if (document.visibilityState === 'visible' && !cancelOpen.value) refresh()
    }, 15_000)
  }
}, { immediate: true })
onBeforeUnmount(() => clearInterval(timer))

const label = (key: string, fallback: string) => (te(key) ? t(key) : fallback)

// ---- Timeline -------------------------------------------------------------------------------

interface Step { key: string, at: string | null, icon: string, done: boolean, tone?: 'error' | 'success' }

const timeline = computed<Step[]>(() => {
  const r = ride.value
  if (!r) return []
  const base: Step[] = [
    { key: 'requested', at: r.requested_at, icon: 'i-lucide-hand', done: true },
    { key: 'assigned', at: r.assigned_at, icon: 'i-lucide-user-check', done: !!r.assigned_at },
    { key: 'arrived', at: r.arrived_at, icon: 'i-lucide-map-pin-check', done: !!r.arrived_at },
    { key: 'started', at: r.started_at, icon: 'i-lucide-bike', done: !!r.started_at },
    { key: 'completed', at: r.completed_at, icon: 'i-lucide-flag', done: !!r.completed_at, tone: 'success' },
  ]
  if (isCancelledRide(r.status) || r.status === 'no_drivers') {
    return [
      ...base.filter(s => s.done && s.key !== 'completed'),
      {
        key: r.status === 'no_drivers' ? 'noDrivers' : 'cancelled',
        at: r.cancelled_at,
        icon: r.status === 'no_drivers' ? 'i-lucide-search-x' : 'i-lucide-circle-x',
        done: true,
        tone: 'error',
      },
    ]
  }
  return base
})

// ---- Map ------------------------------------------------------------------------------------

const routePoints = computed(() => decodeRoute(ride.value?.polyline))
const mapLines = computed<MapLine[]>(() => {
  const r = ride.value
  if (!r) return []
  if (routePoints.value.length > 1) return [{ id: 'route', points: routePoints.value, color: MAP_COLORS.route }]
  // No polyline (OSRM unavailable): straight dashed line as a visual hint only.
  return [{ id: 'route', points: [[r.pickup.lat, r.pickup.lng], [r.dropoff.lat, r.dropoff.lng]], color: MAP_COLORS.route, dashed: true }]
})
const mapMarkers = computed<MapMarker[]>(() => {
  const r = ride.value
  if (!r) return []
  const markers: MapMarker[] = [
    { id: 'pickup', lat: r.pickup.lat, lng: r.pickup.lng, color: MAP_COLORS.pickup, label: `${t('rides.pickup')}: ${shortAddress(r.pickup)}` },
    { id: 'dropoff', lat: r.dropoff.lat, lng: r.dropoff.lng, color: MAP_COLORS.dropoff, label: `${t('rides.dropoff')}: ${shortAddress(r.dropoff)}` },
  ]
  if (r.driver_location && active.value) {
    markers.push({
      id: 'driver',
      lat: r.driver_location.lat,
      lng: r.driver_location.lng,
      color: MAP_COLORS.driverBusy,
      radius: 9,
      label: `${t('rides.driver')}: ${personName(r.driver)}`,
    })
  }
  return markers
})

// ---- Fare -----------------------------------------------------------------------------------

const surge = computed(() => Number(ride.value?.surge_multiplier ?? 1))
// The final fare is rounded up after the surge, so the pre-surge amount is an approximation.
const preSurgeFare = computed(() => (ride.value && surge.value > 1 ? Number(ride.value.fare) / surge.value : null))

// ---- Chat & ratings -------------------------------------------------------------------------

function senderRole(message: RideMessage): 'passenger' | 'driver' | 'other' {
  if (message.sender_id === ride.value?.passenger.id) return 'passenger'
  if (ride.value?.driver && message.sender_id === ride.value.driver.id) return 'driver'
  return 'other'
}

function raterRole(rating: RideRating): 'passenger' | 'driver' | 'other' {
  if (rating.rater_role) return rating.rater_role
  if (rating.rater_id && rating.rater_id === ride.value?.passenger.id) return 'passenger'
  if (rating.rater_id && rating.rater_id === ride.value?.driver?.id) return 'driver'
  return 'other'
}

const messages = computed(() => [...(ride.value?.messages ?? [])].sort((a, b) => a.created_at.localeCompare(b.created_at)))
const offers = computed(() => ride.value?.offers ?? [])

const offerStatusColor = (value: string) =>
  (({ accepted: 'success', declined: 'error', expired: 'neutral', pending: 'warning', cancelled: 'neutral' } as const)[value] ?? 'neutral')

// ---- Admin cancel ---------------------------------------------------------------------------

const cancelOpen = ref(false)
const cancelReason = ref('')
const cancelling = ref(false)

function askCancel() {
  cancelReason.value = ''
  cancelOpen.value = true
}

async function confirmCancel() {
  const reason = cancelReason.value.trim()
  if (!reason) return
  cancelling.value = true
  try {
    await request(`/admin/rides/${id.value}/cancel`, { method: 'POST', body: { reason } })
    toast.add({ title: t('rides.cancel.done'), color: 'success' })
    cancelOpen.value = false
    await refresh()
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    cancelling.value = false
  }
}
</script>

<template>
  <UDashboardPanel id="ride-detail">
    <template #header>
      <UDashboardNavbar :title="t('rides.detailTitle', { id: id.slice(0, 8) })">
        <template #leading>
          <UButton
            icon="i-lucide-arrow-left"
            color="neutral"
            variant="ghost"
            :aria-label="t('common.back')"
            to="/rides"
          />
        </template>
        <template #trailing>
          <UBadge
            v-if="ride"
            :color="rideStatusColor(ride.status)"
            variant="subtle"
          >
            {{ label(`rides.statuses.${ride.status}`, ride.status) }}
          </UBadge>
        </template>
        <template #right>
          <UButton
            v-if="active"
            icon="i-lucide-circle-x"
            color="error"
            variant="soft"
            :label="t('rides.cancel.action')"
            @click="askCancel"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <UAlert
        v-if="error && !ride"
        color="error"
        variant="subtle"
        icon="i-lucide-circle-alert"
        :title="apiError(error)"
      />
      <div
        v-else-if="status === 'pending' && !ride"
        class="grid gap-4 lg:grid-cols-3"
      >
        <USkeleton class="h-80 lg:col-span-2" />
        <USkeleton class="h-80" />
      </div>

      <div
        v-if="ride"
        class="grid gap-6 lg:grid-cols-3"
      >
        <UAlert
          v-if="ride.cancel_reason"
          class="lg:col-span-3"
          color="warning"
          variant="subtle"
          icon="i-lucide-message-square-warning"
          :title="t('rides.cancelReason')"
          :description="te(`rides.cancelReasons.${ride.cancel_reason}`) ? t(`rides.cancelReasons.${ride.cancel_reason}`) : ride.cancel_reason"
        />

        <!-- Main column -->
        <div class="grid content-start gap-6 lg:col-span-2">
          <UCard :ui="{ body: 'p-0 sm:p-0' }">
            <div class="h-80 lg:h-96">
              <MapView
                :markers="mapMarkers"
                :lines="mapLines"
              />
            </div>
            <div class="grid gap-3 p-4 text-sm sm:grid-cols-2">
              <div class="flex gap-2">
                <UIcon
                  name="i-lucide-circle-dot"
                  class="mt-0.5 size-4 shrink-0 text-primary"
                />
                <div>
                  <p class="text-(--ui-text-muted)">
                    {{ t('rides.pickup') }}
                  </p>
                  <p>{{ shortAddress(ride.pickup) }}</p>
                </div>
              </div>
              <div class="flex gap-2">
                <UIcon
                  name="i-lucide-map-pin"
                  class="mt-0.5 size-4 shrink-0 text-error"
                />
                <div>
                  <p class="text-(--ui-text-muted)">
                    {{ t('rides.dropoff') }}
                  </p>
                  <p>{{ shortAddress(ride.dropoff) }}</p>
                </div>
              </div>
              <p
                v-if="!ride.polyline"
                class="text-xs text-(--ui-text-muted) sm:col-span-2"
              >
                {{ t('rides.estimatedRoute') }}
              </p>
            </div>
          </UCard>

          <UCard>
            <template #header>
              <h2 class="font-semibold">
                {{ t('rides.chat.title') }}
              </h2>
            </template>
            <p
              v-if="!messages.length"
              class="text-sm text-(--ui-text-muted)"
            >
              {{ t('rides.chat.empty') }}
            </p>
            <ul
              v-else
              class="max-h-96 space-y-3 overflow-y-auto"
            >
              <li
                v-for="message in messages"
                :key="message.id"
                class="flex"
                :class="senderRole(message) === 'driver' ? 'justify-end' : 'justify-start'"
              >
                <div
                  class="max-w-[80%] rounded-lg px-3 py-2 text-sm"
                  :class="senderRole(message) === 'driver' ? 'bg-primary/10' : 'bg-(--ui-bg-elevated)'"
                >
                  <p class="mb-0.5 text-xs font-medium text-(--ui-text-muted)">
                    {{ t(`rides.chat.${senderRole(message)}`) }} · {{ formatTime(message.created_at, locale) }}
                  </p>
                  <p class="whitespace-pre-wrap break-words">
                    {{ message.text }}
                  </p>
                </div>
              </li>
            </ul>
          </UCard>

          <UCard>
            <template #header>
              <h2 class="font-semibold">
                {{ t('rides.offers.title') }}
              </h2>
            </template>
            <p
              v-if="!offers.length"
              class="text-sm text-(--ui-text-muted)"
            >
              {{ t('rides.offers.empty') }}
            </p>
            <div
              v-else
              class="overflow-x-auto"
            >
              <table class="w-full text-left text-sm">
                <thead class="text-(--ui-text-muted)">
                  <tr>
                    <th class="py-2 pr-4 font-medium">
                      {{ t('rides.driver') }}
                    </th>
                    <th class="py-2 pr-4 font-medium">
                      {{ t('rides.offers.sentAt') }}
                    </th>
                    <th class="py-2 pr-4 font-medium">
                      {{ t('rides.offers.distance') }}
                    </th>
                    <th class="py-2 pr-4 font-medium">
                      {{ t('rides.offers.respondedAt') }}
                    </th>
                    <th class="py-2 font-medium">
                      {{ t('rides.status') }}
                    </th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-(--ui-border)">
                  <tr
                    v-for="(offer, index) in offers"
                    :key="offer.id ?? `${offer.driver_id}-${index}`"
                  >
                    <td class="py-2 pr-4">
                      <NuxtLink
                        :to="driverLink(offer.driver_id, offer.driver_profile_id)"
                        class="text-primary hover:underline"
                      >
                        {{ offer.driver_name || offer.driver_id.slice(0, 8) }}
                      </NuxtLink>
                    </td>
                    <td class="py-2 pr-4 whitespace-nowrap">
                      {{ formatTime(offer.sent_at ?? offer.created_at, locale) }}
                    </td>
                    <td class="py-2 pr-4 whitespace-nowrap">
                      {{ formatDistance(offer.pickup_distance_m, locale) }}
                    </td>
                    <td class="py-2 pr-4 whitespace-nowrap">
                      {{ formatTime(offer.responded_at, locale) }}
                    </td>
                    <td class="py-2">
                      <UBadge
                        :color="offerStatusColor(offer.status)"
                        variant="subtle"
                        size="sm"
                      >
                        {{ label(`rides.offers.statuses.${offer.status}`, offer.status) }}
                      </UBadge>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </UCard>
        </div>

        <!-- Side column -->
        <div class="grid content-start gap-6">
          <UCard>
            <template #header>
              <h2 class="font-semibold">
                {{ t('rides.fareBreakdown') }}
              </h2>
            </template>
            <dl class="space-y-2 text-sm">
              <div
                v-if="preSurgeFare !== null"
                class="flex justify-between gap-4"
              >
                <dt class="text-(--ui-text-muted)">
                  {{ t('rides.preSurgeFare') }}
                </dt>
                <dd>≈ {{ formatMoney(preSurgeFare, locale) }}</dd>
              </div>
              <div class="flex justify-between gap-4">
                <dt class="text-(--ui-text-muted)">
                  {{ t('rides.surge') }}
                </dt>
                <dd>
                  <UBadge
                    :color="surge > 1 ? 'warning' : 'neutral'"
                    variant="subtle"
                    size="sm"
                  >
                    {{ formatMultiplier(ride.surge_multiplier) }}
                  </UBadge>
                </dd>
              </div>
              <div class="flex justify-between gap-4 border-t border-(--ui-border) pt-2 text-base font-semibold">
                <dt>{{ t('rides.fare') }}</dt>
                <dd>{{ formatMoney(ride.fare, locale) }}</dd>
              </div>
              <div class="flex justify-between gap-4 pt-2">
                <dt class="text-(--ui-text-muted)">
                  {{ t('rides.paymentMethod') }}
                </dt>
                <dd>{{ label(`paymentMethods.${ride.payment_method}`, ride.payment_method) }}</dd>
              </div>
              <div class="flex justify-between gap-4">
                <dt class="text-(--ui-text-muted)">
                  {{ t('rides.vehicleType') }}
                </dt>
                <dd>{{ label(`vehicleTypes.${ride.vehicle_type}`, ride.vehicle_type) }}</dd>
              </div>
              <div class="flex justify-between gap-4">
                <dt class="text-(--ui-text-muted)">
                  {{ t('rides.distance') }}
                </dt>
                <dd>{{ formatDistance(ride.distance_m, locale) }}</dd>
              </div>
              <div class="flex justify-between gap-4">
                <dt class="text-(--ui-text-muted)">
                  {{ t('rides.duration') }}
                </dt>
                <dd>{{ formatDuration(ride.duration_s) }}</dd>
              </div>
            </dl>
          </UCard>

          <UCard>
            <template #header>
              <h2 class="font-semibold">
                {{ t('rides.people') }}
              </h2>
            </template>
            <div class="space-y-4 text-sm">
              <div>
                <p class="text-(--ui-text-muted)">
                  {{ t('rides.passenger') }}
                </p>
                <NuxtLink
                  :to="`/users/${ride.passenger.id}`"
                  class="font-medium text-primary hover:underline"
                >
                  {{ personName(ride.passenger) }}
                </NuxtLink>
                <p
                  v-if="formatRating(ride.passenger.rating)"
                  class="text-(--ui-text-muted)"
                >
                  ★ {{ formatRating(ride.passenger.rating) }}
                </p>
                <p
                  v-if="ride.passenger.phone || ride.passenger.email"
                  class="text-(--ui-text-muted)"
                >
                  {{ [ride.passenger.phone, ride.passenger.email].filter(Boolean).join(' · ') }}
                </p>
              </div>
              <div>
                <p class="text-(--ui-text-muted)">
                  {{ t('rides.driver') }}
                </p>
                <template v-if="ride.driver">
                  <div class="flex items-center gap-3">
                    <UAvatar
                      :src="ride.driver.photo_url ?? undefined"
                      :alt="personName(ride.driver)"
                      size="md"
                    />
                    <div>
                      <NuxtLink
                        :to="driverLink(ride.driver.id, ride.driver.profile_id)"
                        class="font-medium text-primary hover:underline"
                      >
                        {{ personName(ride.driver) }}
                      </NuxtLink>
                      <p
                        v-if="formatRating(ride.driver.rating)"
                        class="text-(--ui-text-muted)"
                      >
                        ★ {{ formatRating(ride.driver.rating) }}
                      </p>
                    </div>
                  </div>
                  <p
                    v-if="ride.driver.vehicle"
                    class="mt-2"
                  >
                    {{ ride.driver.vehicle.brand }} {{ ride.driver.vehicle.model }} · {{ ride.driver.vehicle.color }}
                    · <span class="font-mono">{{ ride.driver.vehicle.plate }}</span>
                  </p>
                  <p
                    v-if="ride.driver.phone || ride.driver.email"
                    class="text-(--ui-text-muted)"
                  >
                    {{ [ride.driver.phone, ride.driver.email].filter(Boolean).join(' · ') }}
                  </p>
                </template>
                <p
                  v-else
                  class="text-(--ui-text-muted)"
                >
                  {{ t('rides.noDriver') }}
                </p>
              </div>
            </div>
          </UCard>

          <UCard>
            <template #header>
              <h2 class="font-semibold">
                {{ t('rides.timeline.title') }}
              </h2>
            </template>
            <ol class="space-y-0">
              <li
                v-for="(step, index) in timeline"
                :key="step.key"
                class="relative flex gap-3 pb-4 last:pb-0"
              >
                <span
                  v-if="index < timeline.length - 1"
                  class="absolute top-7 left-3.5 h-[calc(100%-1.5rem)] w-px bg-(--ui-border)"
                  aria-hidden="true"
                />
                <span
                  class="flex size-7 shrink-0 items-center justify-center rounded-full"
                  :class="!step.done
                    ? 'bg-(--ui-bg-elevated) text-(--ui-text-dimmed)'
                    : step.tone === 'error'
                      ? 'bg-error/10 text-error'
                      : 'bg-primary/10 text-primary'"
                >
                  <UIcon
                    :name="step.icon"
                    class="size-4"
                  />
                </span>
                <div class="text-sm">
                  <p :class="step.done ? 'font-medium' : 'text-(--ui-text-muted)'">
                    {{ step.key === 'cancelled' ? label(`rides.statuses.${ride.status}`, ride.status) : t(`rides.timeline.${step.key}`) }}
                  </p>
                  <p class="text-xs text-(--ui-text-muted)">
                    {{ step.at ? formatDate(step.at, locale) : t('rides.timeline.pending') }}
                  </p>
                </div>
              </li>
            </ol>
          </UCard>

          <UCard>
            <template #header>
              <h2 class="font-semibold">
                {{ t('rides.ratings.title') }}
              </h2>
            </template>
            <p
              v-if="!ride.ratings?.length"
              class="text-sm text-(--ui-text-muted)"
            >
              {{ t('rides.ratings.empty') }}
            </p>
            <ul
              v-else
              class="space-y-4"
            >
              <li
                v-for="(rating, index) in ride.ratings"
                :key="rating.id ?? index"
                class="space-y-1 text-sm"
              >
                <div class="flex items-center justify-between gap-2">
                  <span class="text-(--ui-text-muted)">{{ t(`rides.ratings.from.${raterRole(rating)}`) }}</span>
                  <span
                    class="text-warning"
                    :aria-label="t('rides.ratings.stars', { n: rating.stars })"
                  >
                    {{ '★'.repeat(rating.stars) }}<span class="text-(--ui-text-dimmed)">{{ '★'.repeat(Math.max(0, 5 - rating.stars)) }}</span>
                  </span>
                </div>
                <div
                  v-if="rating.tags?.length"
                  class="flex flex-wrap gap-1"
                >
                  <UBadge
                    v-for="tag in rating.tags"
                    :key="tag"
                    color="neutral"
                    variant="subtle"
                    size="sm"
                  >
                    {{ label(`rides.ratings.tags.${tag}`, tag) }}
                  </UBadge>
                </div>
                <p
                  v-if="rating.comment"
                  class="whitespace-pre-wrap break-words"
                >
                  “{{ rating.comment }}”
                </p>
              </li>
            </ul>
          </UCard>
        </div>
      </div>

      <UModal
        v-model:open="cancelOpen"
        :title="t('rides.cancel.title')"
        :description="t('rides.cancel.help')"
      >
        <template #body>
          <form
            id="cancel-ride-form"
            @submit.prevent="confirmCancel"
          >
            <UFormField
              :label="t('rides.cancel.reason')"
              required
            >
              <UTextarea
                v-model="cancelReason"
                class="w-full"
                :rows="4"
                maxlength="500"
                autofocus
                required
              />
            </UFormField>
          </form>
        </template>
        <template #footer>
          <div class="flex w-full justify-end gap-2">
            <UButton
              color="neutral"
              variant="ghost"
              :label="t('common.cancel')"
              @click="cancelOpen = false"
            />
            <UButton
              type="submit"
              form="cancel-ride-form"
              color="error"
              :label="t('rides.cancel.confirm')"
              :disabled="!cancelReason.trim()"
              :loading="cancelling"
            />
          </div>
        </template>
      </UModal>
    </template>
  </UDashboardPanel>
</template>
