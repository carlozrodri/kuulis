<script setup lang="ts">
// Live ride page (doc 11): what a trusted contact opens from WhatsApp. No login; the token is the access.
const { t, locale } = useI18n()
const route = useRoute()
const { request } = useApi()
useSeoMeta({ title: () => t('shared.metaTitle'), robots: 'noindex, nofollow' })

const token = computed(() => String(route.params.token ?? ''))
type State = 'live' | 'ended' | 'invalid' | 'failed'
// useState: what the server rendered is handed to the browser, which then keeps polling.
const state = useState<State>(`shared-state-${token.value}`, () => 'live')
const ride = useState<SharedRide | null>(`shared-ride-${token.value}`, () => null)

async function load() {
  try {
    ride.value = await request<SharedRide>(`/public/rides/shared/${encodeURIComponent(token.value)}`)
    state.value = 'live'
  }
  catch (error) {
    const status = (error as { statusCode?: number }).statusCode ?? 0
    if (status === 410) state.value = 'ended'
    else if (status === 404 || status === 422) state.value = 'invalid'
    // A blip keeps the last known position on screen.
    else if (!ride.value) state.value = 'failed'
  }
}

await useAsyncData(`shared-${token.value}`, async () => {
  await load()
  return true
})

let timer: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  timer = setInterval(() => {
    if (state.value === 'live' || state.value === 'failed') void load()
  }, SHARED_RIDE_POLL_MS)
})
onBeforeUnmount(() => clearInterval(timer))

const center = computed(() => (ride.value ? focusPoint(ride.value) : null))
const tiles = computed(() => (center.value ? tilesAround(center.value) : []))
const markers = computed(() => {
  const current = ride.value
  const c = center.value
  if (!current || !c) return []
  const list: { key: string, point: LatLng, label: string }[] = []
  if (current.status !== 'in_progress') list.push({ key: 'pickup', point: current.pickup, label: t('shared.pickup') })
  list.push({ key: 'dropoff', point: current.dropoff, label: t('shared.dropoff') })
  if (current.driver_location) list.push({ key: 'moto', point: current.driver_location, label: t('shared.moto') })
  if (current.sos && current.sos_location) list.push({ key: 'sos', point: current.sos_location, label: t('shared.sosHere') })
  return list.map(m => ({ ...m, ...offsetFrom(c, m.point) }))
})
const statusText = computed(() => (ride.value ? t(`shared.status.${ride.value.status}`) : ''))
const vehicle = computed(() => {
  const v = ride.value?.vehicle
  return v ? [v.brand, v.model, v.color].filter(Boolean).join(' · ') : ''
})
</script>

<template>
  <section class="section">
    <div class="container box">
      <div
        v-if="state === 'ended' || state === 'invalid' || (state === 'failed' && !ride)"
        class="card"
      >
        <KuulisWordmark
          :size="26"
          class="mark"
        />
        <h1>{{ t(`shared.${state}Title`) }}</h1>
        <p class="muted">
          {{ t(`shared.${state}Body`) }}
        </p>
      </div>

      <template v-else-if="ride">
        <p
          v-if="ride.sos"
          class="notice notice-danger sos"
          role="alert"
        >
          <strong>{{ t('shared.sosTitle', { name: ride.passenger.first_name }) }}</strong>
          {{ t('shared.sosBody') }}
        </p>

        <div class="card">
          <p class="eyebrow">
            {{ t('shared.following', { name: ride.passenger.first_name }) }}
          </p>
          <h1>{{ statusText }}</h1>
          <p
            v-if="ride.eta && ride.status === 'in_progress'"
            class="muted"
          >
            {{ t('shared.eta', { time: formatClock(ride.eta, locale) }) }}
          </p>

          <div
            class="map"
            role="img"
            :aria-label="t('shared.mapLabel')"
          >
            <img
              v-for="tile in tiles"
              :key="tile.url"
              :src="tile.url"
              alt=""
              class="tile"
              :style="{ left: `calc(50% + ${tile.left}px)`, top: `calc(50% + ${tile.top}px)` }"
              loading="lazy"
              referrerpolicy="no-referrer"
            >
            <span
              v-for="marker in markers"
              :key="marker.key"
              class="marker"
              :class="marker.key"
              :title="marker.label"
              :style="{ left: `calc(50% + ${marker.left}px)`, top: `calc(50% + ${marker.top}px)` }"
            />
            <a
              class="attribution"
              href="https://www.openstreetmap.org/copyright"
              target="_blank"
              rel="noopener"
            >© OpenStreetMap</a>
          </div>
          <a
            v-if="center"
            class="btn btn-primary wide"
            :href="googleMapsUrl(center)"
            target="_blank"
            rel="noopener"
          >{{ t('shared.openMaps') }}</a>

          <div
            v-if="ride.driver"
            class="driver"
          >
            <img
              v-if="ride.driver.photo_url"
              :src="ride.driver.photo_url"
              :alt="ride.driver.first_name"
              class="avatar"
              referrerpolicy="no-referrer"
            >
            <div>
              <p class="name">
                {{ ride.driver.first_name }}
                <span
                  v-if="ride.driver.rating"
                  class="muted"
                >★ {{ ride.driver.rating.toFixed(1) }}</span>
              </p>
              <p
                v-if="vehicle"
                class="muted"
              >
                {{ vehicle }}
              </p>
              <p
                v-if="ride.vehicle"
                class="plate"
              >
                {{ formatPlate(ride.vehicle.plate) }}
              </p>
            </div>
          </div>

          <dl class="places">
            <div>
              <dt>{{ t('shared.from') }}</dt>
              <dd>{{ shortAddress(ride.pickup.address) }}</dd>
            </div>
            <div>
              <dt>{{ t('shared.to') }}</dt>
              <dd>{{ shortAddress(ride.dropoff.address) }}</dd>
            </div>
          </dl>
          <p class="muted small">
            {{ t('shared.updated', { time: formatClock(ride.updated_at, locale) }) }}
          </p>
        </div>
        <p class="muted small help">
          {{ t('shared.help') }}
        </p>
      </template>
    </div>
  </section>
</template>

<style scoped>
.box {
  max-width: 520px;
}

.mark {
  color: var(--primary);
  display: block;
  margin-bottom: 24px;
}

h1 {
  font-size: 1.6rem;
  margin: 4px 0;
}

.eyebrow {
  color: var(--primary);
  font-weight: 700;
  margin: 0;
}

.sos {
  margin-bottom: 16px;
}

.map {
  position: relative;
  overflow: hidden;
  height: 280px;
  margin: 16px 0 12px;
  border-radius: 16px;
  background: var(--surface-alt);
}

.tile {
  position: absolute;
  width: 256px;
  height: 256px;
  max-width: none;
}

.marker {
  position: absolute;
  width: 18px;
  height: 18px;
  margin: -9px 0 0 -9px;
  border: 3px solid #fff;
  border-radius: 50%;
  box-shadow: 0 1px 4px rgb(0 0 0 / 35%);
}

.marker.pickup {
  background: var(--primary);
}

.marker.dropoff {
  background: #14201b;
}

.marker.moto {
  width: 24px;
  height: 24px;
  margin: -12px 0 0 -12px;
  background: var(--accent);
}

.marker.sos {
  width: 26px;
  height: 26px;
  margin: -13px 0 0 -13px;
  background: var(--danger);
}

.attribution {
  position: absolute;
  right: 6px;
  bottom: 4px;
  font-size: 0.7rem;
  color: #14201b;
  background: rgb(255 255 255 / 80%);
  padding: 0 4px;
  border-radius: 4px;
}

.wide {
  width: 100%;
}

.driver {
  display: flex;
  gap: 14px;
  align-items: center;
  margin-top: 20px;
}

.driver p {
  margin: 0;
}

.avatar {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  object-fit: cover;
}

.name {
  font-weight: 800;
}

.plate {
  display: inline-block;
  margin-top: 4px !important;
  padding: 2px 8px;
  border: 2px solid var(--text);
  border-radius: 6px;
  font-weight: 800;
  letter-spacing: 1px;
}

.places {
  display: grid;
  gap: 8px;
  margin: 20px 0 12px;
}

.places dt {
  color: var(--muted);
  font-size: 0.85rem;
}

.places dd {
  margin: 0;
  font-weight: 700;
}

.small {
  font-size: 0.85rem;
}

.help {
  margin-top: 16px;
  text-align: center;
}
</style>
