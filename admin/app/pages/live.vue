<script setup lang="ts">
import type { AppConfig, OnlineDriver, Page, Ride } from '~/types/api'
import type { MapLine, MapMarker, MapRectangle } from '~/utils/geo'

const { t, te, locale } = useI18n()
const { request } = useApi()
const apiError = useApiError()

const REFRESH_MS = 10_000
/** Drivers stop receiving offers after 60 s without a location update (docs/api/phase-1b.md). */
const STALE_MS = 60_000

const drivers = ref<OnlineDriver[]>([])
const rides = ref<Ride[]>([])
const serviceArea = ref<AppConfig['service_area'] | null>(null)
const loading = ref(false)
const loaded = ref(false)
const loadError = ref<string | null>(null)
const lastUpdated = ref<Date | null>(null)
const autoRefresh = ref(true)
const now = ref(Date.now())

async function load() {
  if (loading.value) return
  loading.value = true
  // Independent requests: one failing must not blank the other half of the screen.
  const [driversResult, ridesResult] = await Promise.allSettled([
    request<OnlineDriver[] | Page<OnlineDriver>>('/admin/drivers/online'),
    request<Ride[] | Page<Ride>>('/admin/rides/live'),
  ])
  if (driversResult.status === 'fulfilled') drivers.value = asList(driversResult.value)
  if (ridesResult.status === 'fulfilled') rides.value = asList(ridesResult.value)
  const failed = [driversResult, ridesResult].find(r => r.status === 'rejected') as PromiseRejectedResult | undefined
  loadError.value = failed ? apiError(failed.reason) : null
  if (!failed) lastUpdated.value = new Date()
  now.value = Date.now()
  loaded.value = true
  loading.value = false
}

function asList<T>(value: T[] | Page<T> | null | undefined): T[] {
  if (!value) return []
  return Array.isArray(value) ? value : value.items ?? []
}

let timer: ReturnType<typeof setInterval> | undefined
function onVisibility() {
  if (document.visibilityState === 'visible' && autoRefresh.value) load()
}
onMounted(() => {
  load()
  timer = setInterval(() => {
    if (autoRefresh.value && document.visibilityState === 'visible') load()
  }, REFRESH_MS)
  document.addEventListener('visibilitychange', onVisibility)
  // The service area is only context for the map; ignore failures.
  request<AppConfig>('/admin/config').then((c) => {
    serviceArea.value = c.service_area ?? null
  }).catch(() => {})
})
onBeforeUnmount(() => {
  clearInterval(timer)
  document.removeEventListener('visibilitychange', onVisibility)
})

const isStale = (driver: OnlineDriver) =>
  !!driver.last_seen_at && now.value - new Date(driver.last_seen_at).getTime() > STALE_MS

function secondsAgo(value: string | null): string {
  if (!value) return '—'
  const seconds = Math.max(0, Math.round((now.value - new Date(value).getTime()) / 1000))
  return seconds < 60 ? t('live.secondsAgo', { n: seconds }) : t('live.minutesAgo', { n: Math.round(seconds / 60) })
}

const label = (key: string, fallback: string) => (te(key) ? t(key) : fallback)

const busyDrivers = computed(() => drivers.value.filter(d => d.active_ride_id).length)

// ---- Selection & map ------------------------------------------------------------------------

const tab = ref<'rides' | 'drivers'>('rides')
const selected = ref<string | null>(null)
const selectedRide = computed(() =>
  selected.value?.startsWith('ride:') ? rides.value.find(r => `ride:${r.id}` === selected.value) ?? null : null,
)

function select(markerId: string) {
  // The drop-off and driver markers of the selected ride select the ride itself.
  const id = markerId.replace(/^(dropoff|ride-driver):/, 'ride:')
  selected.value = id
  tab.value = id.startsWith('ride:') ? 'rides' : 'drivers'
  // Bring the matching row into view in the side list.
  nextTick(() => document.getElementById(`live-${id}`)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }))
}

const driverColor = (driver: OnlineDriver) =>
  isStale(driver) ? '#64748b' : driver.active_ride_id ? MAP_COLORS.driverBusy : MAP_COLORS.driverFree

const markers = computed<MapMarker[]>(() => {
  const list: MapMarker[] = drivers.value.map(d => ({
    id: `driver:${d.driver_id}`,
    lat: d.lat,
    lng: d.lng,
    color: driverColor(d),
    radius: 6,
    label: `${d.name || t('live.unnamed')} · ${d.active_ride_id ? t('live.busy') : t('live.free')}`,
  }))
  for (const ride of rides.value) {
    list.push({
      id: `ride:${ride.id}`,
      lat: ride.pickup.lat,
      lng: ride.pickup.lng,
      color: rideStatusHex[ride.status] ?? MAP_COLORS.route,
      radius: 9,
      hollow: true,
      label: `${label(`rides.statuses.${ride.status}`, ride.status)} · ${personName(ride.passenger)} · ${shortAddress(ride.pickup)}`,
    })
  }
  const ride = selectedRide.value
  if (ride) {
    list.push({
      id: `dropoff:${ride.id}`,
      lat: ride.dropoff.lat,
      lng: ride.dropoff.lng,
      color: MAP_COLORS.dropoff,
      radius: 7,
      label: `${t('rides.dropoff')}: ${shortAddress(ride.dropoff)}`,
    })
    if (ride.driver_location) {
      list.push({
        id: `ride-driver:${ride.id}`,
        lat: ride.driver_location.lat,
        lng: ride.driver_location.lng,
        color: MAP_COLORS.driverBusy,
        radius: 8,
        label: `${t('rides.driver')}: ${personName(ride.driver)}`,
      })
    }
  }
  return list
})

const lines = computed<MapLine[]>(() => {
  const ride = selectedRide.value
  if (!ride) return []
  const route = decodeRoute(ride.polyline)
  const result: MapLine[] = [{
    id: 'route',
    points: route.length > 1 ? route : [[ride.pickup.lat, ride.pickup.lng], [ride.dropoff.lat, ride.dropoff.lng]],
    color: MAP_COLORS.route,
    dashed: route.length < 2,
  }]
  if (ride.driver_location && (ride.status === 'driver_assigned' || ride.status === 'driver_arrived')) {
    result.push({
      id: 'approach',
      points: [[ride.driver_location.lat, ride.driver_location.lng], [ride.pickup.lat, ride.pickup.lng]],
      color: MAP_COLORS.driverBusy,
      dashed: true,
    })
  }
  return result
})

const rectangles = computed<MapRectangle[]>(() => {
  const area = serviceArea.value
  if (!area) return []
  return [{ id: 'area', bounds: [[area.min_lat, area.min_lng], [area.max_lat, area.max_lng]], color: MAP_COLORS.serviceArea }]
})

const tabs = computed(() => [
  { label: t('live.activeRides', { n: rides.value.length }), value: 'rides' },
  { label: t('live.onlineDrivers', { n: drivers.value.length }), value: 'drivers' },
])

const sortedRides = computed(() => [...rides.value].sort((a, b) => b.requested_at.localeCompare(a.requested_at)))
const sortedDrivers = computed(() =>
  [...drivers.value].sort((a, b) => Number(!!a.active_ride_id) - Number(!!b.active_ride_id) || (a.name ?? '').localeCompare(b.name ?? '')),
)
</script>

<template>
  <UDashboardPanel id="live">
    <template #header>
      <UDashboardNavbar :title="t('nav.live')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <span
            v-if="lastUpdated"
            class="hidden text-xs text-(--ui-text-muted) sm:inline"
          >
            {{ t('live.updatedAt', { time: formatTime(lastUpdated.toISOString(), locale) }) }}
          </span>
          <USwitch
            v-model="autoRefresh"
            :label="t('live.autoRefresh')"
            size="sm"
          />
          <UButton
            icon="i-lucide-refresh-cw"
            color="neutral"
            variant="ghost"
            :loading="loading"
            :aria-label="t('live.refresh')"
            @click="load"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <UAlert
        v-if="loadError"
        color="error"
        variant="subtle"
        icon="i-lucide-circle-alert"
        :title="loadError"
      />

      <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <UCard :ui="{ body: 'p-3 sm:p-3' }">
          <p class="text-xs text-(--ui-text-muted)">
            {{ t('live.statOnline') }}
          </p>
          <p class="text-xl font-semibold">
            {{ drivers.length }}
          </p>
        </UCard>
        <UCard :ui="{ body: 'p-3 sm:p-3' }">
          <p class="text-xs text-(--ui-text-muted)">
            {{ t('live.statFree') }}
          </p>
          <p class="text-xl font-semibold text-success">
            {{ drivers.length - busyDrivers }}
          </p>
        </UCard>
        <UCard :ui="{ body: 'p-3 sm:p-3' }">
          <p class="text-xs text-(--ui-text-muted)">
            {{ t('live.statRides') }}
          </p>
          <p class="text-xl font-semibold">
            {{ rides.length }}
          </p>
        </UCard>
        <UCard :ui="{ body: 'p-3 sm:p-3' }">
          <p class="text-xs text-(--ui-text-muted)">
            {{ t('live.statSearching') }}
          </p>
          <p class="text-xl font-semibold text-warning">
            {{ rides.filter(r => r.status === 'searching').length }}
          </p>
        </UCard>
      </div>

      <div class="flex min-h-[32rem] flex-1 flex-col gap-4 lg:flex-row">
        <div class="relative h-[28rem] min-w-0 flex-1 lg:h-auto">
          <MapView
            :markers="markers"
            :lines="lines"
            :rectangles="rectangles"
            :selected="selected"
            fit="once"
            @select="select"
          />
          <div class="pointer-events-none absolute bottom-6 left-2 z-[1000] flex flex-wrap gap-x-3 gap-y-1 rounded-md bg-(--ui-bg)/90 px-2 py-1 text-xs shadow">
            <span class="flex items-center gap-1"><span
              class="size-2.5 rounded-full"
              :style="{ background: MAP_COLORS.driverFree }"
            />{{ t('live.free') }}</span>
            <span class="flex items-center gap-1"><span
              class="size-2.5 rounded-full"
              :style="{ background: MAP_COLORS.driverBusy }"
            />{{ t('live.busy') }}</span>
            <span class="flex items-center gap-1"><span class="size-2.5 rounded-full bg-slate-500" />{{ t('live.stale') }}</span>
            <span class="flex items-center gap-1"><span
              class="size-3 rounded-full border-2"
              :style="{ borderColor: rideStatusHex.searching }"
            />{{ t('live.ridePickup') }}</span>
          </div>
        </div>

        <aside class="flex min-h-0 w-full flex-col gap-3 lg:w-96">
          <UTabs
            v-model="tab"
            :items="tabs"
            :content="false"
            size="sm"
            class="w-full"
          />
          <div class="min-h-0 flex-1 overflow-y-auto lg:max-h-[calc(100vh-16rem)]">
            <template v-if="!loaded">
              <USkeleton
                v-for="n in 4"
                :key="n"
                class="mb-2 h-16"
              />
            </template>

            <template v-else-if="tab === 'rides'">
              <p
                v-if="!sortedRides.length"
                class="p-4 text-center text-sm text-(--ui-text-muted)"
              >
                {{ t('live.noRides') }}
              </p>
              <ul
                v-else
                class="space-y-2"
              >
                <li
                  v-for="ride in sortedRides"
                  :id="`live-ride:${ride.id}`"
                  :key="ride.id"
                >
                  <div
                    role="button"
                    tabindex="0"
                    class="w-full cursor-pointer rounded-md border p-3 text-left text-sm transition hover:bg-(--ui-bg-elevated)"
                    :class="selected === `ride:${ride.id}` ? 'border-primary bg-primary/5' : 'border-(--ui-border)'"
                    @click="select(`ride:${ride.id}`)"
                    @keydown.enter.self="select(`ride:${ride.id}`)"
                  >
                    <div class="flex items-center justify-between gap-2">
                      <UBadge
                        :color="rideStatusColor(ride.status)"
                        variant="subtle"
                        size="sm"
                      >
                        {{ label(`rides.statuses.${ride.status}`, ride.status) }}
                      </UBadge>
                      <span class="text-xs text-(--ui-text-muted)">{{ formatTime(ride.requested_at, locale) }}</span>
                    </div>
                    <p class="mt-2 truncate">
                      <span class="font-medium">{{ personName(ride.passenger) }}</span>
                      <template v-if="ride.driver">
                        → {{ personName(ride.driver) }}
                      </template>
                    </p>
                    <p class="truncate text-xs text-(--ui-text-muted)">
                      {{ shortAddress(ride.pickup) }} → {{ shortAddress(ride.dropoff) }}
                    </p>
                    <div class="mt-2 flex items-center justify-between text-xs">
                      <span>{{ formatMoney(ride.fare, locale) }} · {{ label(`paymentMethods.${ride.payment_method}`, ride.payment_method) }}</span>
                      <NuxtLink
                        :to="`/rides/${ride.id}`"
                        class="text-primary hover:underline"
                        @click.stop
                      >
                        {{ t('live.openRide') }}
                      </NuxtLink>
                    </div>
                  </div>
                </li>
              </ul>
            </template>

            <template v-else>
              <p
                v-if="!sortedDrivers.length"
                class="p-4 text-center text-sm text-(--ui-text-muted)"
              >
                {{ t('live.noDrivers') }}
              </p>
              <ul
                v-else
                class="space-y-2"
              >
                <li
                  v-for="driver in sortedDrivers"
                  :id="`live-driver:${driver.driver_id}`"
                  :key="driver.driver_id"
                >
                  <div
                    role="button"
                    tabindex="0"
                    class="flex w-full cursor-pointer items-center gap-3 rounded-md border p-3 text-left text-sm transition hover:bg-(--ui-bg-elevated)"
                    :class="selected === `driver:${driver.driver_id}` ? 'border-primary bg-primary/5' : 'border-(--ui-border)'"
                    @click="select(`driver:${driver.driver_id}`)"
                    @keydown.enter.self="select(`driver:${driver.driver_id}`)"
                  >
                    <span
                      class="size-2.5 shrink-0 rounded-full"
                      :style="{ background: driverColor(driver) }"
                    />
                    <div class="min-w-0 flex-1">
                      <p class="truncate font-medium">
                        {{ driver.name || t('live.unnamed') }}
                      </p>
                      <p class="text-xs text-(--ui-text-muted)">
                        {{ isStale(driver) ? t('live.stale') : driver.active_ride_id ? t('live.busy') : t('live.free') }}
                        · {{ t('live.lastSeen', { ago: secondsAgo(driver.last_seen_at) }) }}
                      </p>
                    </div>
                    <div class="flex shrink-0 flex-col items-end gap-1 text-xs">
                      <NuxtLink
                        :to="driverLink(driver.driver_id, driver.driver_profile_id)"
                        class="text-primary hover:underline"
                        @click.stop
                      >
                        {{ t('live.openDriver') }}
                      </NuxtLink>
                      <NuxtLink
                        v-if="driver.active_ride_id"
                        :to="`/rides/${driver.active_ride_id}`"
                        class="text-primary hover:underline"
                        @click.stop
                      >
                        {{ t('live.openRide') }}
                      </NuxtLink>
                    </div>
                  </div>
                </li>
              </ul>
            </template>
          </div>
        </aside>
      </div>
    </template>
  </UDashboardPanel>
</template>
