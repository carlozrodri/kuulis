<script setup lang="ts">
import type * as Leaflet from 'leaflet'
import 'leaflet/dist/leaflet.css'
import type { MapLine, MapMarker, MapRectangle } from '~/utils/geo'

const props = withDefaults(defineProps<{
  markers?: MapMarker[]
  lines?: MapLine[]
  rectangles?: MapRectangle[]
  /** 'always': refit whenever the data changes; 'once': only on the first non-empty data (live views). */
  fit?: 'always' | 'once'
  selected?: string | null
}>(), {
  markers: () => [],
  lines: () => [],
  rectangles: () => [],
  fit: 'always',
  selected: null,
})

const emit = defineEmits<{ select: [id: string] }>()

const config = useRuntimeConfig()
const el = ref<HTMLElement | null>(null)

let L: typeof Leaflet | null = null
let map: Leaflet.Map | null = null
let layer: Leaflet.FeatureGroup | null = null
let observer: ResizeObserver | null = null
let fitted = false
const markerLayers = new Map<string, Leaflet.CircleMarker>()

function tooltipContent(text: string): HTMLElement {
  const span = document.createElement('span')
  span.textContent = text
  return span
}

function render() {
  if (!L || !map || !layer) return
  layer.clearLayers()
  markerLayers.clear()

  for (const rect of props.rectangles) {
    L.rectangle(rect.bounds, { color: rect.color, weight: 2, fillOpacity: 0.05, dashArray: '6 6', interactive: false }).addTo(layer)
  }
  for (const line of props.lines) {
    if (line.points.length < 2) continue
    L.polyline(line.points, { color: line.color, weight: 4, opacity: 0.8, dashArray: line.dashed ? '6 8' : undefined }).addTo(layer)
  }
  for (const m of props.markers) {
    if (!Number.isFinite(m.lat) || !Number.isFinite(m.lng)) continue
    const marker = L.circleMarker([m.lat, m.lng], {
      radius: m.radius ?? 8,
      color: m.hollow ? m.color : '#ffffff',
      weight: m.hollow ? 3 : 2,
      fillColor: m.color,
      fillOpacity: m.hollow ? 0.15 : 0.95,
    })
    if (m.label) marker.bindTooltip(tooltipContent(m.label), { direction: 'top', offset: [0, -6] })
    marker.on('click', () => emit('select', m.id))
    marker.addTo(layer)
    markerLayers.set(m.id, marker)
  }

  if (props.fit === 'always' || !fitted) fitToData()
}

function fitToData() {
  if (!map || !layer) return
  const bounds = layer.getBounds()
  if (!bounds.isValid()) {
    if (props.fit === 'always') map.setView(CARACAS_CENTER, 12)
    return
  }
  fitted = true
  // A single point has zero-area bounds: keep a sensible street-level zoom.
  map.fitBounds(bounds, { padding: [32, 32], maxZoom: 16 })
}

function focusSelected() {
  if (!map || !props.selected) return
  const marker = markerLayers.get(props.selected)
  if (!marker) return
  map.flyTo(marker.getLatLng(), Math.max(map.getZoom(), 15), { duration: 0.5 })
  marker.openTooltip()
}

onMounted(async () => {
  // Imported lazily: Leaflet touches `window` at import time.
  L = (await import('leaflet')).default
  if (!el.value) return
  map = L.map(el.value, { center: CARACAS_CENTER, zoom: 12, zoomControl: true })
  L.tileLayer(config.public.mapTileUrl, {
    maxZoom: 19,
    attribution: config.public.mapTileAttribution,
  }).addTo(map)
  layer = L.featureGroup().addTo(map)
  render()
  focusSelected()
  observer = new ResizeObserver(() => map?.invalidateSize())
  observer.observe(el.value)
})

onBeforeUnmount(() => {
  observer?.disconnect()
  map?.remove()
  map = null
  layer = null
})

watch(() => [props.markers, props.lines, props.rectangles], render, { deep: true })
watch(() => props.selected, focusSelected)

defineExpose({ fitToData })
</script>

<template>
  <div
    ref="el"
    class="kuulis-map z-0 size-full min-h-64 overflow-hidden rounded-md"
  />
</template>

<style>
/* Keep Leaflet panes under Nuxt UI overlays (modals, slideovers, toasts). */
.kuulis-map {
  isolation: isolate;
}
</style>
