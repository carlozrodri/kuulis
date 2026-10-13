<script setup lang="ts">
import type { AlertOutcome, Page, SafetyAlert } from '~/types/api'
import { ALERT_OUTCOMES } from '~/types/api'
import type { MapLine, MapMarker } from '~/utils/geo'

definePageMeta({ permission: 'safety.view' })

const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const { request } = useApi()
const toast = useToast()
const apiError = useApiError()
const auth = useAuth()
const safety = useSafetySummary()

const canManage = computed(() => auth.can('safety.manage'))

type Filter = 'active' | 'checking' | 'closed'
const filter = ref<Filter>('active')
const alerts = ref<SafetyAlert[]>([])
const loading = ref(false)
const loaded = ref(false)
const loadError = ref<string | null>(null)
const selectedId = ref<string | null>((route.query.alert as string) || null)

async function load() {
  if (loading.value) return
  loading.value = true
  try {
    const page = await request<Page<SafetyAlert>>('/admin/safety/alerts', { query: { status: filter.value, limit: 100, offset: 0 } })
    alerts.value = page.items
    loadError.value = null
    // An alert opened from a link (Telegram) may be in another tab: fetch it on its own.
    if (selectedId.value && !alerts.value.some(a => a.id === selectedId.value)) {
      try {
        extra.value = await request<SafetyAlert>(`/admin/safety/alerts/${selectedId.value}`)
      }
      catch {
        extra.value = null
      }
    }
    else {
      extra.value = null
    }
  }
  catch (err) {
    loadError.value = apiError(err)
  }
  finally {
    loading.value = false
    loaded.value = true
  }
}

const extra = ref<SafetyAlert | null>(null)
const selected = computed(() => alerts.value.find(a => a.id === selectedId.value) ?? extra.value)

function select(id: string) {
  selectedId.value = id
  router.replace({ query: { ...route.query, alert: id } })
}

watch(filter, () => {
  loaded.value = false
  load()
})
// A new alert (the layout's poll) refreshes the list at once.
watch(() => safety.summary.value?.latest_id, () => load())

let timer: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  load()
  timer = setInterval(() => {
    if (document.visibilityState === 'visible') load()
  }, 5000)
})
onBeforeUnmount(() => clearInterval(timer))

const kindLabel = (alert: Pick<SafetyAlert, 'kind'>) => t(`safety.kinds.${alert.kind}`)

function since(value: string | null): string {
  if (!value) return '—'
  const minutes = Math.max(0, Math.round((Date.now() - new Date(value).getTime()) / 60000))
  return minutes < 1 ? t('safety.justNow') : t('safety.minutesAgo', { n: minutes })
}

function answerOf(alert: SafetyAlert, userId: string | undefined): string {
  const value = userId ? alert.answers?.[userId] : undefined
  return value ? t(`safety.answers.${value}`) : t('safety.answers.none')
}

// ---- Map ------------------------------------------------------------------------------------

const mapMarkers = computed<MapMarker[]>(() => {
  const a = selected.value
  if (!a) {
    return alerts.value.flatMap((item) => {
      const pos = alertPosition(item)
      return pos ? [{ id: item.id, lat: pos[0], lng: pos[1], color: ALERT_COLORS[item.kind], radius: 10, label: `${kindLabel(item)} · ${item.raised_by?.name ?? ''}` }] : []
    })
  }
  const list: MapMarker[] = []
  if (a.pickup) list.push({ id: 'pickup', lat: a.pickup.lat, lng: a.pickup.lng, color: MAP_COLORS.pickup, hollow: true, label: `${t('rides.pickup')}: ${shortAddress(a.pickup)}` })
  if (a.dropoff) list.push({ id: 'dropoff', lat: a.dropoff.lat, lng: a.dropoff.lng, color: MAP_COLORS.dropoff, hollow: true, label: `${t('rides.dropoff')}: ${shortAddress(a.dropoff)}` })
  if (a.driver_location) {
    list.push({ id: 'driver', lat: a.driver_location.lat, lng: a.driver_location.lng, color: MAP_COLORS.driverBusy, radius: 8, label: `${t('rides.driver')}: ${a.driver?.name ?? ''}` })
  }
  if (a.lat !== null && a.lng !== null) {
    list.push({ id: a.id, lat: a.lat, lng: a.lng, color: ALERT_COLORS[a.kind], radius: 11, label: `${kindLabel(a)} · ${since(a.location_at)}` })
  }
  return list
})

const mapLines = computed<MapLine[]>(() => {
  const a = selected.value
  const route = a ? decodeRoute(a.polyline) : []
  return route.length > 1 ? [{ id: 'route', points: route, color: MAP_COLORS.route, dashed: true }] : []
})

// ---- Actions --------------------------------------------------------------------------------

const busy = ref(false)
const notes = ref('')
watch(selected, (a) => {
  notes.value = a?.notes ?? ''
}, { immediate: true })

function replace(updated: SafetyAlert) {
  const index = alerts.value.findIndex(a => a.id === updated.id)
  if (index >= 0) alerts.value[index] = updated
  else extra.value = updated
}

async function act(path: string, body?: Record<string, unknown>, method: 'POST' | 'PUT' = 'POST') {
  const a = selected.value
  if (!a) return
  busy.value = true
  try {
    replace(await request<SafetyAlert>(`/admin/safety/alerts/${a.id}/${path}`, { method, body }))
    await safety.refresh()
    return true
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
    return false
  }
  finally {
    busy.value = false
  }
}

async function acknowledge() {
  if (await act('acknowledge')) toast.add({ title: t('safety.acknowledged'), color: 'success' })
}

async function saveNotes() {
  if (await act('notes', { notes: notes.value }, 'PUT')) toast.add({ title: t('safety.notesSaved'), color: 'success' })
}

const resolveOpen = ref(false)
const outcome = ref<AlertOutcome>('assisted')
const outcomeItems = computed(() => ALERT_OUTCOMES.map(value => ({ label: t(`safety.outcomes.${value}`), value })))

async function resolve() {
  if (await act('resolve', { outcome: outcome.value, notes: notes.value })) {
    resolveOpen.value = false
    toast.add({ title: t('safety.resolved'), color: 'success' })
  }
}

const tabs = computed(() => [
  { label: t('safety.filters.active'), value: 'active' },
  { label: t('safety.filters.checking'), value: 'checking' },
  { label: t('safety.filters.closed'), value: 'closed' },
])
</script>

<template>
  <UDashboardPanel id="safety">
    <template #header>
      <UDashboardNavbar :title="t('nav.safety')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <USwitch
            :model-value="!safety.muted.value"
            :label="t('safety.sound')"
            size="sm"
            @update:model-value="(v) => (safety.muted.value = !v)"
          />
          <UButton
            icon="i-lucide-volume-2"
            color="neutral"
            variant="ghost"
            :aria-label="t('safety.testSound')"
            @click="playAlarm()"
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
      <p class="text-sm text-(--ui-text-muted)">
        {{ t('safety.help') }}
      </p>

      <div class="flex min-h-[32rem] flex-1 flex-col gap-4 lg:flex-row">
        <aside class="flex min-h-0 w-full flex-col gap-3 lg:w-96">
          <UTabs
            v-model="filter"
            :items="tabs"
            :content="false"
            size="sm"
            class="w-full"
          />
          <div class="min-h-0 flex-1 overflow-y-auto lg:max-h-[calc(100vh-14rem)]">
            <template v-if="!loaded">
              <USkeleton
                v-for="n in 3"
                :key="n"
                class="mb-2 h-20"
              />
            </template>
            <p
              v-else-if="!alerts.length"
              class="p-4 text-center text-sm text-(--ui-text-muted)"
            >
              {{ t(`safety.empty.${filter}`) }}
            </p>
            <ul
              v-else
              class="space-y-2"
            >
              <li
                v-for="alert in alerts"
                :key="alert.id"
              >
                <div
                  role="button"
                  tabindex="0"
                  class="w-full cursor-pointer rounded-md border p-3 text-left text-sm transition hover:bg-(--ui-bg-elevated)"
                  :class="[
                    selectedId === alert.id ? 'border-primary bg-primary/5' : 'border-(--ui-border)',
                    alert.status === 'open' ? 'border-l-4 border-l-error' : '',
                  ]"
                  @click="select(alert.id)"
                  @keydown.enter.self="select(alert.id)"
                >
                  <div class="flex items-center justify-between gap-2">
                    <span class="flex items-center gap-2 font-medium">
                      <UIcon
                        :name="alert.kind === 'sos' ? 'i-lucide-siren' : 'i-lucide-triangle-alert'"
                        class="size-4"
                        :style="{ color: ALERT_COLORS[alert.kind] }"
                      />
                      {{ kindLabel(alert) }}
                      <span
                        v-if="alertDetail(alert)"
                        class="text-xs font-normal text-(--ui-text-muted)"
                      >{{ alertDetail(alert) }}</span>
                    </span>
                    <UBadge
                      :color="alertStatusColor(alert.status)"
                      variant="subtle"
                      size="sm"
                    >
                      {{ t(`safety.statuses.${alert.status}`) }}
                    </UBadge>
                  </div>
                  <p class="mt-1 truncate">
                    {{ alert.raised_by?.name || '—' }}
                    <span class="text-xs text-(--ui-text-muted)">· {{ alert.raised_by ? t(`safety.roles.${alert.raised_by.role}`) : '' }}</span>
                  </p>
                  <p class="text-xs text-(--ui-text-muted)">
                    {{ formatDate(alert.created_at, locale) }} · {{ since(alert.escalated_at ?? alert.created_at) }}
                  </p>
                </div>
              </li>
            </ul>
          </div>
        </aside>

        <div class="flex min-w-0 flex-1 flex-col gap-4">
          <div class="h-[24rem] lg:h-[28rem]">
            <MapView
              :markers="mapMarkers"
              :lines="mapLines"
              :selected="selected?.id ?? null"
              @select="(id) => alerts.some(a => a.id === id) && select(id)"
            />
          </div>

          <UCard v-if="selected">
            <template #header>
              <div class="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h2 class="font-semibold">
                    {{ kindLabel(selected) }}
                    <UBadge
                      :color="alertStatusColor(selected.status)"
                      variant="subtle"
                      size="sm"
                      class="ml-2"
                    >
                      {{ t(`safety.statuses.${selected.status}`) }}
                    </UBadge>
                  </h2>
                  <p class="text-sm text-(--ui-text-muted)">
                    {{ formatDate(selected.created_at, locale) }}
                    <template v-if="selected.details?.reason">
                      · {{ t(`safety.reasons.${selected.details.reason}`) }}
                    </template>
                    <template v-if="selected.handled_by_name">
                      · {{ t('safety.handledBy', { name: selected.handled_by_name }) }}
                    </template>
                  </p>
                </div>
                <div
                  v-if="canManage && isAlertActive(selected.status) || canManage && selected.status === 'checking'"
                  class="flex gap-2"
                >
                  <UButton
                    v-if="selected.status !== 'acknowledged'"
                    :label="t('safety.acknowledge')"
                    icon="i-lucide-hand"
                    color="warning"
                    :loading="busy"
                    @click="acknowledge"
                  />
                  <UButton
                    :label="t('safety.resolve')"
                    icon="i-lucide-check"
                    color="success"
                    variant="soft"
                    :disabled="busy"
                    @click="resolveOpen = true"
                  />
                </div>
              </div>
            </template>

            <div class="grid gap-4 text-sm sm:grid-cols-2">
              <div
                v-for="party in [selected.passenger, selected.driver].filter(Boolean)"
                :key="party!.id"
                class="rounded-md border border-(--ui-border) p-3"
              >
                <p class="text-xs text-(--ui-text-muted)">
                  {{ t(`safety.roles.${party!.role}`) }}
                  <UBadge
                    v-if="selected.raised_by?.id === party!.id && selected.kind === 'sos'"
                    color="error"
                    size="sm"
                    class="ml-1"
                  >
                    SOS
                  </UBadge>
                </p>
                <p class="font-medium">
                  {{ party!.name || '—' }}
                </p>
                <p class="text-xs">
                  {{ party!.email }}
                </p>
                <a
                  v-if="party!.phone"
                  :href="`tel:${party!.phone}`"
                  class="mt-1 inline-flex items-center gap-1 text-primary hover:underline"
                >
                  <UIcon
                    name="i-lucide-phone"
                    class="size-4"
                  />{{ party!.phone }}
                </a>
                <p
                  v-if="selected.kind !== 'sos'"
                  class="mt-1 text-xs"
                >
                  {{ t('safety.answer') }}: {{ answerOf(selected, party!.id) }}
                </p>
              </div>
              <div
                v-if="selected.vehicle"
                class="rounded-md border border-(--ui-border) p-3"
              >
                <p class="text-xs text-(--ui-text-muted)">
                  {{ t('safety.vehicle') }}
                </p>
                <p class="font-medium">
                  {{ selected.vehicle.brand }} {{ selected.vehicle.model }} · {{ selected.vehicle.color }}
                </p>
                <p class="font-mono">
                  {{ selected.vehicle.plate }}
                </p>
              </div>
              <div class="rounded-md border border-(--ui-border) p-3">
                <p class="text-xs text-(--ui-text-muted)">
                  {{ t('safety.position') }}
                </p>
                <p v-if="selected.lat !== null && selected.lng !== null">
                  <a
                    :href="`https://maps.google.com/?q=${selected.lat},${selected.lng}`"
                    target="_blank"
                    rel="noopener"
                    class="text-primary hover:underline"
                  >{{ selected.lat.toFixed(5) }}, {{ selected.lng!.toFixed(5) }}</a>
                  <span class="text-xs text-(--ui-text-muted)"> · {{ since(selected.location_at) }}</span>
                </p>
                <p v-else>
                  —
                </p>
                <NuxtLink
                  v-if="selected.ride_id"
                  :to="`/rides/${selected.ride_id}`"
                  class="mt-1 inline-block text-primary hover:underline"
                >
                  {{ t('live.openRide') }}
                  <template v-if="selected.ride_status">
                    ({{ t(`rides.statuses.${selected.ride_status}`) }})
                  </template>
                </NuxtLink>
              </div>
            </div>

            <div class="mt-4 space-y-2">
              <UFormField :label="t('safety.notes')">
                <UTextarea
                  v-model="notes"
                  :rows="3"
                  :maxlength="2000"
                  class="w-full"
                  :disabled="!canManage"
                />
              </UFormField>
              <div class="flex items-center justify-between gap-2">
                <p
                  v-if="selected.outcome"
                  class="text-sm"
                >
                  {{ t('safety.outcome') }}: {{ t(`safety.outcomes.${selected.outcome}`) }}
                </p>
                <span v-else />
                <UButton
                  v-if="canManage"
                  :label="t('safety.saveNotes')"
                  color="neutral"
                  variant="soft"
                  size="sm"
                  :disabled="busy || notes === selected.notes"
                  @click="saveNotes"
                />
              </div>
            </div>
          </UCard>
          <p
            v-else-if="loaded && alerts.length"
            class="text-center text-sm text-(--ui-text-muted)"
          >
            {{ t('safety.pick') }}
          </p>
        </div>
      </div>

      <UModal
        v-model:open="resolveOpen"
        :title="t('safety.resolveTitle')"
      >
        <template #body>
          <div class="space-y-4">
            <UFormField :label="t('safety.outcome')">
              <USelect
                v-model="outcome"
                :items="outcomeItems"
                class="w-full"
              />
            </UFormField>
            <UFormField :label="t('safety.notes')">
              <UTextarea
                v-model="notes"
                :rows="3"
                :maxlength="2000"
                class="w-full"
              />
            </UFormField>
          </div>
        </template>
        <template #footer>
          <div class="flex w-full justify-end gap-2">
            <UButton
              :label="t('common.cancel')"
              color="neutral"
              variant="ghost"
              @click="resolveOpen = false"
            />
            <UButton
              :label="t('safety.resolve')"
              color="success"
              :loading="busy"
              @click="resolve"
            />
          </div>
        </template>
      </UModal>
    </template>
  </UDashboardPanel>
</template>
