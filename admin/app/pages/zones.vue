<script setup lang="ts">
import type { ApiErrorBody, Coord, DemandSnapshot, Zone, ZoneCity, ZoneImportResult, ZoneKind } from '~/types/api'
import { ZONE_KINDS } from '~/types/api'
import type { MapMarker, MapPolygon, MapRectangle } from '~/utils/geo'
import type { ZoneForm, ZoneStatus } from '~/utils/zones'

definePageMeta({ permission: 'zones.view' })

const { t, locale } = useI18n()
const { request, download } = useApi()
const apiError = useApiError()
const auth = useAuth()
const toast = useToast()
const config = useRuntimeConfig()

const canManage = computed(() => auth.can('zones.manage'))
/** The API answers 404 to the simulation in production (docs/api/zonas.md). */
const canSimulate = computed(() => canManage.value && config.public.appEnv !== 'production')

// ---- Data -----------------------------------------------------------------------------------------

const { data: cities, error: citiesError, refresh: refreshCities } = await useAsyncData(
  'zone-cities',
  () => request<ZoneCity[]>('/admin/zones/cities'),
)

type CityFilter = string
type KindFilter = ZoneKind | 'all'
const ALL = 'all'
const cityFilter = ref<CityFilter>(ALL)
const kindFilter = ref<KindFilter>(ALL)
const zonesQuery = computed(() => ({
  ...(cityFilter.value !== ALL ? { city: cityFilter.value } : {}),
  ...(kindFilter.value !== ALL ? { kind: kindFilter.value } : {}),
}))
const { data: zones, status, error, refresh } = await useAsyncData(
  'zones',
  () => request<Zone[]>('/admin/zones', { query: zonesQuery.value }),
  { watch: [zonesQuery] },
)

const cityItems = computed(() => [
  { label: t('zones.allCities'), value: ALL },
  ...(cities.value ?? []).map(c => ({ label: c.name, value: c.name })),
])
const kindItems = computed(() => [
  { label: t('zones.allKinds'), value: ALL as KindFilter },
  ...ZONE_KINDS.map(kind => ({ label: t(`zones.kinds.${kind}`), value: kind as KindFilter })),
])

// Validity badges follow the clock.
const now = ref(Date.now())
let clock: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  clock = setInterval(() => (now.value = Date.now()), 60_000)
})
onBeforeUnmount(() => clearInterval(clock))

const STATUS_COLORS: Record<ZoneStatus, 'success' | 'info' | 'neutral' | 'warning'> = {
  inForce: 'success',
  scheduled: 'info',
  expired: 'warning',
  inactive: 'neutral',
}
const KIND_COLORS: Record<ZoneKind, 'warning' | 'error' | 'info'> = {
  surge: 'warning',
  restricted: 'error',
  pickup: 'info',
}

const weekdayLabel = (day: number) =>
  new Intl.DateTimeFormat(locale.value, { weekday: 'short', timeZone: 'UTC' }).format(new Date(Date.UTC(2024, 0, 1 + day)))
// 0 = Monday … 6 = Sunday (contract). 2024-01-01 was a Monday.
const weekdayItems = computed(() => Array.from({ length: 7 }, (_, day) => ({ label: weekdayLabel(day), value: day })))

/** One line with the zone's rules, for the list. */
function rulesSummary(zone: Zone): string {
  const rules = zone.rules ?? {}
  if (zone.kind === 'surge') {
    const parts = [`×${formatNumber(Number(rules.multiplier ?? 1), locale.value, 2)}`]
    if (rules.days?.length) parts.push(rules.days.map(weekdayLabel).join(' '))
    parts.push(rules.start && rules.end ? `${rules.start}–${rules.end}` : t('zones.allDay'))
    return parts.join(' · ')
  }
  const points = t('zones.pointsCount', rules.points?.length ?? 0)
  if (zone.kind === 'restricted') {
    const blocked = [rules.pickup ? t('zones.form.noPickup') : null, rules.dropoff ? t('zones.form.noDropoff') : null].filter(Boolean)
    return [...blocked, points].join(' · ')
  }
  return points
}

// ---- Errors ---------------------------------------------------------------------------------------

interface ErrorInfo { title: string, lines: string[] }
const DETAIL_CODES = ['zone_invalid', 'geojson_invalid', 'validation_error']
function errorInfo(err: unknown): ErrorInfo {
  const body = (err as { data?: ApiErrorBody }).data
  const code = body?.error?.code
  return { title: apiError(err), lines: code && DETAIL_CODES.includes(code) ? errorDetailLines(body?.error?.details) : [] }
}

// ---- Panel and map --------------------------------------------------------------------------------

type Mode = 'list' | 'zone' | 'city' | 'simulate'
const mode = ref<Mode>('list')
const tool = ref<'vertices' | 'points' | 'pick' | null>(null)
const focus = ref<Coord[] | null>(null)
const selectedZoneId = ref<string | null>(null)

/** The polygon being drawn (zone or city), with an undo history. */
const vertices = ref<Coord[]>([])
const history = ref<Coord[][]>([])
function setVertices(next: Coord[]) {
  history.value.push(vertices.value)
  vertices.value = next
}
function undo() {
  const previous = history.value.pop()
  if (previous) vertices.value = previous
}
function clearVertices() {
  if (vertices.value.length) setVertices([])
}
function startDrawing(initial: Coord[]) {
  vertices.value = initial.map(([lat, lng]) => [lat, lng])
  history.value = []
}

const cityBox = (c: ZoneCity) => [[c.min_lat, c.min_lng], [c.max_lat, c.max_lng]] as [Coord, Coord]
const cityCoords = (c: ZoneCity): Coord[] => c.polygon?.length ? c.polygon : boxPolygon(c)

const visibleCities = computed(() => (cities.value ?? []).filter(c => cityFilter.value === ALL || c.name === cityFilter.value))
const editingCityName = ref<string | null>(null)
const editingZoneId = ref<string | null>(null)

const cityRectangles = computed<MapRectangle[]>(() => visibleCities.value
  .filter(c => !c.polygon?.length && !(mode.value === 'city' && c.name === editingCityName.value && cityHasDraft.value))
  .map(c => ({ id: `city:${c.name}`, bounds: cityBox(c), color: ZONE_COLORS.city, label: `${c.name} · ${t('zones.cities.box')}` })))

const mapPolygons = computed<MapPolygon[]>(() => {
  const editing = mode.value !== 'list' && mode.value !== 'simulate'
  const list: MapPolygon[] = visibleCities.value
    .filter(c => c.polygon?.length && !(mode.value === 'city' && c.name === editingCityName.value))
    .map(c => ({
      id: `city:${c.name}`,
      points: c.polygon!,
      color: ZONE_COLORS.city,
      dashed: true,
      fillOpacity: 0.03,
      label: `${c.name} · ${t('zones.cities.polygon')}`,
    }))
  for (const zone of zones.value ?? []) {
    if (mode.value === 'zone' && zone.id === editingZoneId.value) continue
    const inForce = zoneStatus(zone, now.value) === 'inForce'
    const selected = zone.id === selectedZoneId.value
    list.push({
      id: `zone:${zone.id}`,
      points: zone.polygon,
      color: ZONE_COLORS[zone.kind],
      dashed: !inForce,
      weight: selected ? 4 : 2,
      fillOpacity: editing ? 0.05 : inForce ? 0.2 : 0.06,
      label: `${zone.name} · ${t(`zones.kinds.${zone.kind}`)} · ${t(`zones.statuses.${zoneStatus(zone, now.value)}`)}`,
    })
  }
  if (mode.value === 'simulate') {
    for (const cell of simResult.value?.cells ?? []) {
      list.push({
        id: `cell:${cell.cell}`,
        points: cell.boundary,
        color: DEMAND_COLORS[cell.level] ?? DEMAND_COLORS[1],
        weight: 1,
        fillOpacity: 0.35,
        label: t('zones.simulate.cell', { requests: cell.requests, unmatched: cell.unmatched }),
      })
    }
  }
  return list
})

const mapMarkers = computed<MapMarker[]>(() => {
  const list: MapMarker[] = []
  for (const zone of zones.value ?? []) {
    if (mode.value === 'zone' && zone.id === editingZoneId.value) continue
    for (const point of zone.rules?.points ?? []) {
      list.push({
        id: `zone:${zone.id}`,
        lat: point.lat,
        lng: point.lng,
        color: ZONE_COLORS[zone.kind],
        radius: 5,
        label: `${point.name} · ${zone.name}`,
      })
    }
  }
  if (mode.value === 'simulate' && simPoint.value) {
    list.push({ id: 'sim', lat: simPoint.value[0], lng: simPoint.value[1], color: DEMAND_COLORS[3], radius: 8, label: t('zones.simulate.point') })
  }
  return list
})

function selectOnMap(id: string) {
  if (!id.startsWith('zone:')) return
  selectedZoneId.value = id.slice(5)
  nextTick(() => document.getElementById(`zone-${selectedZoneId.value}`)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }))
}
function showZone(zone: Zone) {
  selectedZoneId.value = zone.id
  focus.value = zone.polygon
}

function backToList() {
  mode.value = 'list'
  tool.value = null
  editingZoneId.value = null
  editingCityName.value = null
  formError.value = null
  vertices.value = []
  history.value = []
}

const editVertices = computed(() => (mode.value === 'zone' || (mode.value === 'city' && cityHasDraft.value) ? vertices.value : null))
const editColor = computed(() => (mode.value === 'city' ? ZONE_COLORS.city : ZONE_COLORS[form.kind]))

function onPick(point: Coord) {
  if (mode.value === 'zone' && tool.value === 'points') {
    form.points.push({ name: t('zones.form.pointN', { n: form.points.length + 1 }), lat: point[0], lng: point[1] })
  }
  else if (mode.value === 'simulate') {
    simPoint.value = point
  }
}
function movePoint(index: number, point: Coord) {
  const target = form.points[index]
  if (target) Object.assign(target, { lat: point[0], lng: point[1] })
}

// ---- Zone form ------------------------------------------------------------------------------------

const form = reactive<ZoneForm>(defaultZoneForm())
const showIssues = ref(false)
const formError = ref<ErrorInfo | null>(null)
const issues = computed(() => validateZone({ ...form, polygon: vertices.value }))
const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone

const formCityItems = computed(() => (cities.value ?? []).map(c => ({ label: c.name, value: c.name })))
const formKindItems = computed(() => ZONE_KINDS.map(kind => ({ label: t(`zones.kinds.${kind}`), value: kind })))
const multiplierFormat = { minimumFractionDigits: 2, maximumFractionDigits: 2 }

function startCreate() {
  const city = cityFilter.value !== ALL ? cityFilter.value : cities.value?.[0]?.name ?? ''
  Object.assign(form, defaultZoneForm(city, kindFilter.value !== ALL ? kindFilter.value : 'surge'))
  startDrawing([])
  editingZoneId.value = null
  showIssues.value = false
  formError.value = null
  mode.value = 'zone'
  tool.value = 'vertices'
  const c = cities.value?.find(x => x.name === city)
  if (c) focus.value = cityCoords(c)
}
function startEdit(zone: Zone) {
  Object.assign(form, zoneFormFrom(zone))
  startDrawing(zone.polygon)
  editingZoneId.value = zone.id
  selectedZoneId.value = zone.id
  showIssues.value = false
  formError.value = null
  mode.value = 'zone'
  tool.value = 'vertices'
  focus.value = zone.polygon
}
watch(() => form.kind, (kind) => {
  if (kind === 'surge' && tool.value === 'points') tool.value = 'vertices'
})
function toggleDay(day: number) {
  form.days = form.days.includes(day) ? form.days.filter(d => d !== day) : [...form.days, day].sort((a, b) => a - b)
}
function removePoint(index: number) {
  form.points.splice(index, 1)
}

const saving = ref(false)
async function saveZone() {
  if (issues.value.length) {
    showIssues.value = true
    return
  }
  saving.value = true
  formError.value = null
  try {
    const id = editingZoneId.value
    const saved = await request<Zone>(id ? `/admin/zones/${id}` : '/admin/zones', {
      method: id ? 'PATCH' : 'POST',
      body: zonePayload({ ...form, polygon: vertices.value }),
    })
    toast.add({ title: t(id ? 'zones.updated' : 'zones.created'), color: 'success' })
    backToList()
    selectedZoneId.value = saved?.id ?? id
    await refresh()
  }
  catch (err) {
    formError.value = errorInfo(err)
  }
  finally {
    saving.value = false
  }
}

const deleting = ref<Zone | null>(null)
const deleteOpen = computed({
  get: () => deleting.value !== null,
  set: (v) => {
    if (!v) deleting.value = null
  },
})
const removing = ref(false)
async function removeZone() {
  if (!deleting.value) return
  removing.value = true
  try {
    await request(`/admin/zones/${deleting.value.id}`, { method: 'DELETE' })
    toast.add({ title: t('zones.deleted'), color: 'success' })
    if (editingZoneId.value === deleting.value.id) backToList()
    deleting.value = null
    await refresh()
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    removing.value = false
  }
}

function zoneActions(zone: Zone) {
  return [[
    { label: t('zones.edit'), icon: 'i-lucide-pencil', onSelect: () => startEdit(zone) },
  ], [
    { label: t('zones.delete'), icon: 'i-lucide-trash-2', color: 'error' as const, onSelect: () => { deleting.value = zone } },
  ]]
}

// ---- City polygons --------------------------------------------------------------------------------

const editingCity = computed(() => cities.value?.find(c => c.name === editingCityName.value) ?? null)
/** A city without polygon shows its box until "convert" fills the draft with its corners. */
const cityHasDraft = ref(false)
const cityIssue = computed(() => {
  if (vertices.value.length < 3) return 'polygonShort'
  if (vertices.value.length > ZONE_VERTICES_MAX) return 'polygonLong'
  if (polygonSelfIntersects(vertices.value)) return 'polygonCrosses'
  return null
})

function startCity(city: ZoneCity) {
  backToList()
  editingCityName.value = city.name
  cityHasDraft.value = !!city.polygon?.length
  startDrawing(city.polygon ?? [])
  mode.value = 'city'
  tool.value = cityHasDraft.value && canManage.value ? 'vertices' : null
  focus.value = cityCoords(city)
}
function convertBox() {
  if (!editingCity.value) return
  startDrawing(boxPolygon(editingCity.value))
  cityHasDraft.value = true
  tool.value = 'vertices'
}

const savingCity = ref(false)
async function saveCity(polygon: Coord[] | null) {
  const city = editingCity.value
  if (!city) return
  if (polygon === null && !confirm(t('zones.cities.toBoxConfirm', { city: city.name }))) return
  savingCity.value = true
  formError.value = null
  try {
    await request<ZoneCity>(`/admin/zones/cities/${encodeURIComponent(city.name)}`, { method: 'PUT', body: { polygon } })
    toast.add({ title: t(polygon ? 'zones.cities.saved' : 'zones.cities.boxRestored', { city: city.name }), color: 'success' })
    backToList()
    await refreshCities()
  }
  catch (err) {
    formError.value = errorInfo(err)
  }
  finally {
    savingCity.value = false
  }
}

// ---- Export / import ------------------------------------------------------------------------------

const exporting = ref(false)
async function exportGeojson() {
  exporting.value = true
  try {
    await download('/admin/zones/export', exportFileName())
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    exporting.value = false
  }
}

const importOpen = ref(false)
const importFile = ref<File | null>(null)
const importReplace = ref(false)
const importing = ref(false)
const importError = ref<ErrorInfo | null>(null)
const importResult = ref<ZoneImportResult | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)

function openImport() {
  importFile.value = null
  importReplace.value = false
  importError.value = null
  importResult.value = null
  importOpen.value = true
}
function onFile(event: Event) {
  const input = event.target as HTMLInputElement
  importFile.value = input.files?.[0] ?? null
  importError.value = null
  importResult.value = null
}
async function runImport() {
  if (!importFile.value) return
  importError.value = null
  let geojson: unknown
  try {
    geojson = JSON.parse(await importFile.value.text())
  }
  catch {
    importError.value = { title: t('zones.import.notJson'), lines: [] }
    return
  }
  importing.value = true
  try {
    importResult.value = await request<ZoneImportResult>('/admin/zones/import', {
      method: 'POST',
      body: { geojson, replace: importReplace.value },
    })
    await Promise.all([refresh(), refreshCities()])
  }
  catch (err) {
    importError.value = errorInfo(err)
  }
  finally {
    importing.value = false
  }
}

// ---- Demand simulation (outside production) -------------------------------------------------------

const simPoint = ref<Coord | null>(null)
const simRequests = ref(10)
const simUnmatched = ref(3)
const simulating = ref(false)
const simResult = ref<DemandSnapshot | null>(null)
const simError = ref<string | null>(null)

function startSimulate() {
  backToList()
  mode.value = 'simulate'
  tool.value = 'pick'
  simResult.value = null
  simError.value = null
}
async function simulate() {
  if (!simPoint.value) return
  simulating.value = true
  simError.value = null
  try {
    simResult.value = await request<DemandSnapshot>('/admin/zones/demand/simulate', {
      method: 'POST',
      body: { lat: simPoint.value[0], lng: simPoint.value[1], requests: simRequests.value, unmatched: simUnmatched.value },
    })
    toast.add({ title: t('zones.simulate.done'), color: 'success' })
  }
  catch (err) {
    simError.value = (err as { status?: number }).status === 404 ? t('zones.simulate.unavailable') : apiError(err)
  }
  finally {
    simulating.value = false
  }
}
</script>

<template>
  <UDashboardPanel id="zones">
    <template #header>
      <UDashboardNavbar :title="t('nav.zones')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton
            icon="i-lucide-file-down"
            color="neutral"
            variant="ghost"
            :label="t('zones.export')"
            :loading="exporting"
            @click="exportGeojson"
          />
          <UButton
            v-if="canManage"
            icon="i-lucide-file-up"
            color="neutral"
            variant="ghost"
            :label="t('zones.import.button')"
            @click="openImport"
          />
          <UButton
            v-if="canSimulate"
            icon="i-lucide-flame"
            color="neutral"
            variant="ghost"
            :label="t('zones.simulate.button')"
            class="hidden md:inline-flex"
            @click="startSimulate"
          />
          <UButton
            v-if="canManage"
            icon="i-lucide-plus"
            :label="t('zones.new')"
            :disabled="!cities?.length"
            @click="startCreate"
          />
        </template>
      </UDashboardNavbar>
      <UDashboardToolbar>
        <template #left>
          <USelect
            v-model="cityFilter"
            :items="cityItems"
            class="w-44"
            :aria-label="t('zones.city')"
          />
          <USelect
            v-model="kindFilter"
            :items="kindItems"
            class="w-44"
            :aria-label="t('zones.kind')"
          />
        </template>
      </UDashboardToolbar>
    </template>

    <template #body>
      <p class="text-sm text-(--ui-text-muted)">
        {{ t('zones.help') }}
      </p>
      <UAlert
        v-if="error || citiesError"
        color="error"
        variant="subtle"
        icon="i-lucide-circle-alert"
        :title="apiError(error || citiesError)"
      />

      <div class="flex min-h-[32rem] flex-1 flex-col gap-4 lg:flex-row">
        <div class="relative h-[28rem] min-w-0 flex-1 lg:h-auto">
          <ZoneMap
            :polygons="mapPolygons"
            :rectangles="cityRectangles"
            :markers="mapMarkers"
            :vertices="editVertices"
            :edit-color="editColor"
            :points="mode === 'zone' && form.kind !== 'surge' ? form.points : null"
            :tool="canManage ? tool : null"
            :focus="focus"
            @update:vertices="setVertices"
            @move-point="movePoint"
            @pick="onPick"
            @select="selectOnMap"
          />

          <!-- Drawing tools -->
          <div
            v-if="canManage && editVertices"
            class="absolute top-2 right-2 z-[1000] flex max-w-[calc(100%-4rem)] flex-wrap items-center gap-1 rounded-md bg-(--ui-bg)/95 p-1 shadow"
          >
            <UButton
              size="xs"
              icon="i-lucide-pen-tool"
              :color="tool === 'vertices' ? 'primary' : 'neutral'"
              :variant="tool === 'vertices' ? 'solid' : 'ghost'"
              :label="t('zones.map.draw')"
              @click="tool = 'vertices'"
            />
            <UButton
              v-if="mode === 'zone' && form.kind !== 'surge'"
              size="xs"
              icon="i-lucide-map-pin-plus"
              :color="tool === 'points' ? 'primary' : 'neutral'"
              :variant="tool === 'points' ? 'solid' : 'ghost'"
              :label="t('zones.map.addPoints')"
              @click="tool = 'points'"
            />
            <UButton
              size="xs"
              icon="i-lucide-undo-2"
              color="neutral"
              variant="ghost"
              :label="t('zones.map.undo')"
              :disabled="!history.length"
              @click="undo"
            />
            <UButton
              size="xs"
              icon="i-lucide-eraser"
              color="neutral"
              variant="ghost"
              :label="t('zones.map.clear')"
              :disabled="!vertices.length"
              @click="clearVertices"
            />
          </div>
          <p
            v-if="canManage && tool"
            class="pointer-events-none absolute top-14 right-2 z-[1000] max-w-72 rounded-md bg-(--ui-bg)/95 px-2 py-1 text-xs shadow"
          >
            {{ t(`zones.map.hint.${tool}`, { n: vertices.length }) }}
          </p>

          <div class="pointer-events-none absolute bottom-6 left-2 z-[1000] flex flex-wrap gap-x-3 gap-y-1 rounded-md bg-(--ui-bg)/90 px-2 py-1 text-xs shadow">
            <span class="flex items-center gap-1"><span
              class="size-2.5 rounded-sm border border-dashed"
              :style="{ borderColor: ZONE_COLORS.city }"
            />{{ t('zones.cityLegend') }}</span>
            <span
              v-for="kind in ZONE_KINDS"
              :key="kind"
              class="flex items-center gap-1"
            ><span
              class="size-2.5 rounded-sm"
              :style="{ background: ZONE_COLORS[kind] }"
            />{{ t(`zones.kinds.${kind}`) }}</span>
          </div>
        </div>

        <aside class="flex min-h-0 w-full flex-col gap-3 lg:w-[26rem]">
          <div class="min-h-0 flex-1 space-y-4 overflow-y-auto lg:max-h-[calc(100vh-14rem)]">
            <UAlert
              v-if="formError"
              color="error"
              variant="subtle"
              icon="i-lucide-circle-alert"
              :title="formError.title"
            >
              <template
                v-if="formError.lines.length"
                #description
              >
                <ul class="list-disc pl-4">
                  <li
                    v-for="line in formError.lines"
                    :key="line"
                  >
                    {{ line }}
                  </li>
                </ul>
              </template>
            </UAlert>

            <!-- Zone list and cities -->
            <template v-if="mode === 'list'">
              <section class="space-y-2">
                <h3 class="text-sm font-medium">
                  {{ t('zones.cities.title') }}
                </h3>
                <ul class="space-y-1">
                  <li
                    v-for="city in visibleCities"
                    :key="city.name"
                    class="flex items-center justify-between gap-2 rounded-md border border-(--ui-border) px-3 py-2 text-sm"
                  >
                    <span class="truncate font-medium">{{ city.name }}</span>
                    <div class="flex shrink-0 items-center gap-2">
                      <UBadge
                        :color="city.polygon?.length ? 'success' : 'neutral'"
                        variant="subtle"
                        size="sm"
                      >
                        {{ city.polygon?.length ? t('zones.cities.polygonN', { n: city.polygon.length }) : t('zones.cities.box') }}
                      </UBadge>
                      <UButton
                        size="xs"
                        color="neutral"
                        variant="ghost"
                        :icon="canManage ? 'i-lucide-pencil' : 'i-lucide-eye'"
                        :aria-label="t('zones.cities.edit', { city: city.name })"
                        @click="startCity(city)"
                      />
                    </div>
                  </li>
                </ul>
              </section>

              <section class="space-y-2">
                <h3 class="text-sm font-medium">
                  {{ t('zones.listTitle', { n: zones?.length ?? 0 }) }}
                </h3>
                <template v-if="status === 'pending' && !zones">
                  <USkeleton
                    v-for="n in 3"
                    :key="n"
                    class="h-16"
                  />
                </template>
                <p
                  v-else-if="!zones?.length"
                  class="p-4 text-center text-sm text-(--ui-text-muted)"
                >
                  {{ t('zones.empty') }}
                </p>
                <ul
                  v-else
                  class="space-y-2"
                >
                  <li
                    v-for="zone in zones"
                    :id="`zone-${zone.id}`"
                    :key="zone.id"
                  >
                    <div
                      role="button"
                      tabindex="0"
                      class="w-full cursor-pointer rounded-md border p-3 text-left text-sm transition hover:bg-(--ui-bg-elevated)"
                      :class="selectedZoneId === zone.id ? 'border-primary bg-primary/5' : 'border-(--ui-border)'"
                      @click="showZone(zone)"
                      @keydown.enter.self="showZone(zone)"
                    >
                      <div class="flex items-start justify-between gap-2">
                        <div class="min-w-0">
                          <p class="truncate font-medium">
                            {{ zone.name }}
                          </p>
                          <p class="text-xs text-(--ui-text-muted)">
                            {{ zone.city }}
                          </p>
                        </div>
                        <div class="flex shrink-0 items-center gap-1">
                          <UBadge
                            :color="KIND_COLORS[zone.kind]"
                            variant="subtle"
                            size="sm"
                          >
                            {{ t(`zones.kinds.${zone.kind}`) }}
                          </UBadge>
                          <UBadge
                            :color="STATUS_COLORS[zoneStatus(zone, now)]"
                            variant="subtle"
                            size="sm"
                          >
                            {{ t(`zones.statuses.${zoneStatus(zone, now)}`) }}
                          </UBadge>
                          <UDropdownMenu
                            v-if="canManage"
                            :items="zoneActions(zone)"
                          >
                            <UButton
                              size="xs"
                              color="neutral"
                              variant="ghost"
                              icon="i-lucide-ellipsis-vertical"
                              :aria-label="t('zones.actions')"
                              @click.stop
                            />
                          </UDropdownMenu>
                        </div>
                      </div>
                      <p class="mt-1 text-xs">
                        {{ rulesSummary(zone) }}
                      </p>
                      <p
                        v-if="zone.starts_at || zone.ends_at"
                        class="text-xs text-(--ui-text-muted)"
                      >
                        {{ t('zones.validity', { from: zone.starts_at ? formatDate(zone.starts_at, locale) : '—', to: zone.ends_at ? formatDate(zone.ends_at, locale) : '—' }) }}
                      </p>
                    </div>
                  </li>
                </ul>
              </section>
            </template>

            <!-- Create / edit zone -->
            <form
              v-else-if="mode === 'zone'"
              class="space-y-4"
              @submit.prevent="saveZone"
            >
              <div class="flex items-center justify-between gap-2">
                <h3 class="font-medium">
                  {{ editingZoneId ? t('zones.editTitle') : t('zones.new') }}
                </h3>
                <UButton
                  color="neutral"
                  variant="ghost"
                  size="sm"
                  icon="i-lucide-arrow-left"
                  :label="t('common.back')"
                  @click="backToList"
                />
              </div>
              <UFormField
                :label="t('zones.form.name')"
                required
              >
                <UInput
                  v-model="form.name"
                  :maxlength="ZONE_NAME_MAX"
                  :placeholder="t('zones.form.namePlaceholder')"
                  class="w-full"
                />
              </UFormField>
              <div class="grid gap-4 sm:grid-cols-2">
                <UFormField
                  :label="t('zones.kind')"
                  required
                >
                  <USelect
                    v-model="form.kind"
                    :items="formKindItems"
                    class="w-full"
                  />
                </UFormField>
                <UFormField
                  :label="t('zones.city')"
                  required
                >
                  <USelect
                    v-model="form.city"
                    :items="formCityItems"
                    class="w-full"
                  />
                </UFormField>
              </div>
              <p class="text-xs text-(--ui-text-muted)">
                {{ t(`zones.kindHelp.${form.kind}`) }}
              </p>
              <p class="text-sm">
                <UIcon
                  name="i-lucide-hexagon"
                  class="align-middle"
                />
                {{ t('zones.form.vertices', { n: vertices.length }) }}
              </p>

              <USwitch
                v-model="form.active"
                :label="t('zones.form.active')"
                :description="t('zones.form.activeHelp')"
              />
              <div>
                <div class="grid gap-4 sm:grid-cols-2">
                  <UFormField :label="t('zones.form.startsAt')">
                    <UInput
                      v-model="form.starts_at"
                      type="datetime-local"
                      class="w-full"
                    />
                  </UFormField>
                  <UFormField :label="t('zones.form.endsAt')">
                    <UInput
                      v-model="form.ends_at"
                      type="datetime-local"
                      :min="form.starts_at || undefined"
                      class="w-full"
                    />
                  </UFormField>
                </div>
                <p class="mt-1 text-xs text-(--ui-text-muted)">
                  {{ t('zones.form.validityHelp', { zone: timeZone }) }}
                </p>
              </div>

              <!-- Rules per kind -->
              <div class="space-y-4 rounded-md border border-(--ui-border) p-3">
                <h4 class="text-sm font-medium">
                  {{ t('zones.form.rules') }}
                </h4>
                <template v-if="form.kind === 'surge'">
                  <UFormField
                    :label="t('zones.form.multiplier')"
                    :help="t('zones.form.multiplierHelp')"
                  >
                    <UInputNumber
                      v-model="form.multiplier"
                      :min="SURGE_ZONE_MIN"
                      :max="SURGE_ZONE_MAX"
                      :step="0.05"
                      :format-options="multiplierFormat"
                    />
                  </UFormField>
                  <UFormField
                    :label="t('zones.form.days')"
                    :help="t('zones.form.daysHelp')"
                  >
                    <div
                      role="group"
                      :aria-label="t('zones.form.days')"
                      class="flex flex-wrap gap-1"
                    >
                      <UButton
                        v-for="day in weekdayItems"
                        :key="day.value"
                        size="xs"
                        :color="form.days.includes(day.value) ? 'primary' : 'neutral'"
                        :variant="form.days.includes(day.value) ? 'solid' : 'outline'"
                        :aria-pressed="form.days.includes(day.value)"
                        :label="day.label"
                        class="min-w-11 justify-center capitalize"
                        @click="toggleDay(day.value)"
                      />
                    </div>
                  </UFormField>
                  <div class="grid gap-4 sm:grid-cols-2">
                    <UFormField :label="t('zones.form.start')">
                      <UInput
                        v-model="form.start"
                        type="time"
                      />
                    </UFormField>
                    <UFormField :label="t('zones.form.end')">
                      <UInput
                        v-model="form.end"
                        type="time"
                      />
                    </UFormField>
                  </div>
                  <p class="text-xs text-(--ui-text-muted)">
                    {{ t('zones.form.hoursHelp') }}
                  </p>
                </template>

                <template v-else-if="form.kind === 'restricted'">
                  <div class="flex flex-wrap gap-4">
                    <UCheckbox
                      v-model="form.pickup"
                      :label="t('zones.form.noPickup')"
                    />
                    <UCheckbox
                      v-model="form.dropoff"
                      :label="t('zones.form.noDropoff')"
                    />
                  </div>
                  <ControlLocalizedFields
                    v-model="form.message"
                    :label="t('zones.form.message')"
                    :help="t('zones.form.messageHelp')"
                    textarea
                    :rows="2"
                  />
                </template>

                <div
                  v-if="form.kind !== 'surge'"
                  class="space-y-2"
                >
                  <div class="flex items-center justify-between gap-2">
                    <p class="text-sm font-medium">
                      {{ form.kind === 'pickup' ? t('zones.form.points') : t('zones.form.exits') }}
                    </p>
                    <UButton
                      size="xs"
                      icon="i-lucide-map-pin-plus"
                      :color="tool === 'points' ? 'primary' : 'neutral'"
                      :variant="tool === 'points' ? 'solid' : 'outline'"
                      :label="t('zones.map.addPoints')"
                      @click="tool = tool === 'points' ? 'vertices' : 'points'"
                    />
                  </div>
                  <p
                    v-if="!form.points.length"
                    class="text-xs text-(--ui-text-muted)"
                  >
                    {{ t('zones.form.noPoints') }}
                  </p>
                  <div
                    v-for="(point, index) in form.points"
                    :key="index"
                    class="flex items-center gap-2"
                  >
                    <UInput
                      v-model="point.name"
                      :maxlength="ZONE_NAME_MAX"
                      :aria-label="t('zones.form.pointName')"
                      size="sm"
                      class="flex-1"
                    />
                    <span class="shrink-0 text-xs text-(--ui-text-muted) tabular-nums">{{ point.lat.toFixed(5) }}, {{ point.lng.toFixed(5) }}</span>
                    <UButton
                      size="xs"
                      color="neutral"
                      variant="ghost"
                      icon="i-lucide-trash-2"
                      :aria-label="t('zones.form.removePoint')"
                      @click="removePoint(index)"
                    />
                  </div>
                </div>
              </div>

              <UAlert
                v-if="showIssues && issues.length"
                color="error"
                variant="subtle"
                icon="i-lucide-circle-alert"
                :title="t('zones.fixErrors')"
              >
                <template #description>
                  <ul class="list-disc pl-4">
                    <li
                      v-for="issue in issues"
                      :key="issue"
                    >
                      {{ t(`zones.errors.${issue}`, { max: ZONE_VERTICES_MAX, points: ZONE_POINTS_MAX }) }}
                    </li>
                  </ul>
                </template>
              </UAlert>

              <div class="flex flex-wrap justify-between gap-2">
                <UButton
                  v-if="editingZoneId"
                  color="error"
                  variant="ghost"
                  icon="i-lucide-trash-2"
                  :label="t('zones.delete')"
                  @click="deleting = zones?.find(z => z.id === editingZoneId) ?? null"
                />
                <div class="ml-auto flex gap-2">
                  <UButton
                    color="neutral"
                    variant="ghost"
                    :label="t('common.cancel')"
                    @click="backToList"
                  />
                  <UButton
                    type="submit"
                    :label="editingZoneId ? t('common.save') : t('zones.create')"
                    :loading="saving"
                  />
                </div>
              </div>
            </form>

            <!-- City polygon -->
            <section
              v-else-if="mode === 'city' && editingCity"
              class="space-y-4"
            >
              <div class="flex items-center justify-between gap-2">
                <h3 class="font-medium">
                  {{ editingCity.name }}
                </h3>
                <UButton
                  color="neutral"
                  variant="ghost"
                  size="sm"
                  icon="i-lucide-arrow-left"
                  :label="t('common.back')"
                  @click="backToList"
                />
              </div>
              <p class="text-sm text-(--ui-text-muted)">
                {{ t('zones.cities.help') }}
              </p>
              <UBadge
                :color="editingCity.polygon?.length ? 'success' : 'neutral'"
                variant="subtle"
              >
                {{ editingCity.polygon?.length ? t('zones.cities.polygonN', { n: editingCity.polygon.length }) : t('zones.cities.box') }}
              </UBadge>
              <template v-if="canManage">
                <UButton
                  v-if="!cityHasDraft"
                  icon="i-lucide-square-dashed"
                  :label="t('zones.cities.convert')"
                  block
                  @click="convertBox"
                />
                <template v-else>
                  <p class="text-sm">
                    {{ t('zones.form.vertices', { n: vertices.length }) }}
                  </p>
                  <UAlert
                    v-if="cityIssue && vertices.length"
                    color="warning"
                    variant="subtle"
                    icon="i-lucide-triangle-alert"
                    :title="t(`zones.errors.${cityIssue}`, { max: ZONE_VERTICES_MAX })"
                  />
                  <div class="flex flex-wrap gap-2">
                    <UButton
                      icon="i-lucide-save"
                      :label="t('zones.cities.save')"
                      :loading="savingCity"
                      :disabled="!!cityIssue"
                      @click="saveCity(vertices)"
                    />
                    <UButton
                      v-if="!editingCity.polygon?.length"
                      color="neutral"
                      variant="ghost"
                      :label="t('common.cancel')"
                      @click="cityHasDraft = false; startDrawing([]); tool = null"
                    />
                  </div>
                </template>
                <UButton
                  v-if="editingCity.polygon?.length"
                  icon="i-lucide-square"
                  color="neutral"
                  variant="outline"
                  :label="t('zones.cities.toBox')"
                  :loading="savingCity"
                  @click="saveCity(null)"
                />
              </template>
            </section>

            <!-- Demand simulation -->
            <section
              v-else-if="mode === 'simulate'"
              class="space-y-4"
            >
              <div class="flex items-center justify-between gap-2">
                <h3 class="font-medium">
                  {{ t('zones.simulate.title') }}
                </h3>
                <UButton
                  color="neutral"
                  variant="ghost"
                  size="sm"
                  icon="i-lucide-arrow-left"
                  :label="t('common.back')"
                  @click="backToList"
                />
              </div>
              <p class="text-sm text-(--ui-text-muted)">
                {{ t('zones.simulate.help') }}
              </p>
              <p class="text-sm">
                <template v-if="simPoint">
                  {{ t('zones.simulate.at', { lat: simPoint[0].toFixed(5), lng: simPoint[1].toFixed(5) }) }}
                </template>
                <span
                  v-else
                  class="text-(--ui-text-muted)"
                >{{ t('zones.simulate.pickPoint') }}</span>
              </p>
              <div class="grid gap-4 sm:grid-cols-2">
                <UFormField :label="t('zones.simulate.requests')">
                  <UInputNumber
                    v-model="simRequests"
                    :min="1"
                    :max="200"
                  />
                </UFormField>
                <UFormField :label="t('zones.simulate.unmatched')">
                  <UInputNumber
                    v-model="simUnmatched"
                    :min="0"
                    :max="200"
                  />
                </UFormField>
              </div>
              <UAlert
                v-if="simError"
                color="error"
                variant="subtle"
                icon="i-lucide-circle-alert"
                :title="simError"
              />
              <UButton
                icon="i-lucide-flame"
                :label="t('zones.simulate.run')"
                :loading="simulating"
                :disabled="!simPoint"
                @click="simulate"
              />
              <p
                v-if="simResult"
                class="text-sm"
              >
                {{ simResult.enabled ? t('zones.simulate.result', { n: simResult.cells.length }) : t('zones.simulate.disabled') }}
              </p>
            </section>
          </div>
        </aside>
      </div>

      <!-- Import -->
      <UModal
        v-model:open="importOpen"
        :title="t('zones.import.title')"
      >
        <template #body>
          <div class="space-y-4">
            <p class="text-sm text-(--ui-text-muted)">
              {{ t('zones.import.help') }}
            </p>
            <input
              ref="fileInput"
              type="file"
              accept=".geojson,.json,application/geo+json,application/json"
              class="hidden"
              @change="onFile"
            >
            <div class="flex items-center gap-3">
              <UButton
                icon="i-lucide-file-up"
                color="neutral"
                variant="outline"
                :label="t('zones.import.choose')"
                @click="fileInput?.click()"
              />
              <span class="truncate text-sm">{{ importFile?.name ?? t('zones.import.noFile') }}</span>
            </div>
            <UCheckbox
              v-model="importReplace"
              :label="t('zones.import.replace')"
              :description="t('zones.import.replaceHelp')"
            />
            <UAlert
              v-if="importError"
              color="error"
              variant="subtle"
              icon="i-lucide-circle-alert"
              :title="importError.title"
            >
              <template
                v-if="importError.lines.length"
                #description
              >
                <ul class="list-disc pl-4">
                  <li
                    v-for="line in importError.lines"
                    :key="line"
                  >
                    {{ line }}
                  </li>
                </ul>
              </template>
            </UAlert>
            <UAlert
              v-if="importResult"
              :color="importResult.skipped.length ? 'warning' : 'success'"
              variant="subtle"
              icon="i-lucide-circle-check"
              :title="t('zones.import.result', { cities: importResult.cities, created: importResult.created, updated: importResult.updated })"
            >
              <template
                v-if="importResult.skipped.length"
                #description
              >
                <p>{{ t('zones.import.skipped', { n: importResult.skipped.length }) }}</p>
                <ul class="list-disc pl-4">
                  <li
                    v-for="item in importResult.skipped"
                    :key="item.index"
                  >
                    {{ t('zones.import.feature', { n: item.index }) }}: {{ item.reason }}
                  </li>
                </ul>
              </template>
            </UAlert>
          </div>
        </template>
        <template #footer>
          <div class="flex w-full justify-end gap-2">
            <UButton
              color="neutral"
              variant="ghost"
              :label="importResult ? t('zones.import.close') : t('common.cancel')"
              @click="importOpen = false"
            />
            <UButton
              icon="i-lucide-file-up"
              :label="t('zones.import.run')"
              :loading="importing"
              :disabled="!importFile"
              @click="runImport"
            />
          </div>
        </template>
      </UModal>

      <!-- Delete -->
      <UModal
        v-model:open="deleteOpen"
        :title="t('zones.deleteTitle')"
      >
        <template #body>
          <UAlert
            v-if="deleting"
            color="warning"
            variant="subtle"
            icon="i-lucide-triangle-alert"
            :title="t('zones.deleteBody', { name: deleting.name })"
          />
        </template>
        <template #footer>
          <div class="flex w-full justify-end gap-2">
            <UButton
              color="neutral"
              variant="ghost"
              :label="t('common.cancel')"
              @click="deleting = null"
            />
            <UButton
              color="error"
              :label="t('zones.delete')"
              :loading="removing"
              @click="removeZone"
            />
          </div>
        </template>
      </UModal>
    </template>
  </UDashboardPanel>
</template>
