<script setup lang="ts">
import type * as Leaflet from 'leaflet'
import 'leaflet/dist/leaflet.css'
import type { Coord, ZonePoint } from '~/types/api'
import type { MapMarker, MapPolygon, MapRectangle } from '~/utils/geo'

/**
 * Doc 21: the zones map and its polygon editor. Shows cities and zones, and edits one polygon
 * (`vertices`) and its points: a click on the map adds a vertex where it bends the outline least,
 * vertices drag to move and a click on one removes it. With the `points` or `pick` tool a click on
 * the map emits `pick` instead (the page adds a pickup point or picks the simulation spot).
 */
const props = withDefaults(defineProps<{
  polygons?: MapPolygon[]
  rectangles?: MapRectangle[]
  markers?: MapMarker[]
  /** Polygon being edited; null when not editing. */
  vertices?: Coord[] | null
  editColor?: string
  /** Points of the zone being edited (draggable with the points tool). */
  points?: ZonePoint[] | null
  tool?: 'vertices' | 'points' | 'pick' | null
  /** The map fits these coordinates whenever they change (selecting a city or zone). */
  focus?: Coord[] | null
}>(), {
  polygons: () => [],
  rectangles: () => [],
  markers: () => [],
  vertices: null,
  editColor: '#2563eb',
  points: null,
  tool: null,
  focus: null,
})

const emit = defineEmits<{
  'update:vertices': [value: Coord[]]
  'move-point': [index: number, value: Coord]
  'pick': [value: Coord]
  'select': [id: string]
}>()

const { t } = useI18n()
const config = useRuntimeConfig()
const el = ref<HTMLElement | null>(null)

let L: typeof Leaflet | null = null
let map: Leaflet.Map | null = null
let shapes: Leaflet.FeatureGroup | null = null
let editing: Leaflet.FeatureGroup | null = null
let observer: ResizeObserver | null = null
let fitted = false

function tooltipContent(text: string): HTMLElement {
  const span = document.createElement('span')
  span.textContent = text
  return span
}

const selectable = () => !props.tool

function renderShapes() {
  if (!L || !map || !shapes) return
  shapes.clearLayers()
  for (const rect of props.rectangles) {
    const shape = L.rectangle(rect.bounds, {
      color: rect.color,
      weight: rect.solid ? 1 : 2,
      fillOpacity: rect.fillOpacity ?? 0.05,
      dashArray: rect.solid ? undefined : '6 6',
      interactive: !!rect.label,
    })
    if (rect.label) shape.bindTooltip(tooltipContent(rect.label), { direction: 'top', sticky: true })
    shape.on('click', () => selectable() && emit('select', rect.id))
    shape.addTo(shapes)
  }
  for (const poly of props.polygons) {
    if (poly.points.length < 3) continue
    const shape = L.polygon(poly.points, {
      color: poly.color,
      weight: poly.weight ?? 2,
      fillOpacity: poly.fillOpacity ?? 0.15,
      dashArray: poly.dashed ? '6 6' : undefined,
      interactive: !!poly.label,
    })
    if (poly.label) shape.bindTooltip(tooltipContent(poly.label), { direction: 'top', sticky: true })
    shape.on('click', () => selectable() && emit('select', poly.id))
    shape.addTo(shapes)
  }
  for (const m of props.markers) {
    if (!Number.isFinite(m.lat) || !Number.isFinite(m.lng)) continue
    const marker = L.circleMarker([m.lat, m.lng], {
      radius: m.radius ?? 6,
      color: m.hollow ? m.color : '#ffffff',
      weight: m.hollow ? 3 : 2,
      fillColor: m.color,
      fillOpacity: m.hollow ? 0.15 : 0.95,
    })
    if (m.label) marker.bindTooltip(tooltipContent(m.label), { direction: 'top', offset: [0, -6] })
    marker.on('click', () => selectable() && emit('select', m.id))
    marker.addTo(shapes)
  }
  if (!fitted) fitTo(null)
}

function renderEditing() {
  if (!L || !map || !editing) return
  editing.clearLayers()
  const vertices = props.vertices
  if (vertices) {
    const outline = vertices.length >= 3
      ? L.polygon(vertices, { color: props.editColor, weight: 3, fillOpacity: 0.2, interactive: false })
      : L.polyline(vertices, { color: props.editColor, weight: 3, dashArray: '4 6', interactive: false })
    outline.addTo(editing)
    const editable = props.tool === 'vertices'
    vertices.forEach((vertex, index) => {
      const marker = L!.marker(vertex, {
        draggable: editable,
        keyboard: false,
        title: editable ? t('zones.map.vertexHint') : '',
        icon: L!.divIcon({ className: 'zone-vertex', iconSize: [14, 14] }),
      })
      marker.on('drag', () => {
        // Redraw the outline while dragging; the page gets the new polygon on dragend.
        const moved = vertices.map((v, i) => (i === index ? [marker.getLatLng().lat, marker.getLatLng().lng] : v) as Coord)
        outline.setLatLngs(moved)
      })
      marker.on('dragend', () => {
        const { lat, lng } = marker.getLatLng()
        emit('update:vertices', vertices.map((v, i) => (i === index ? [round(lat), round(lng)] : v)))
      })
      marker.on('click', (event: Leaflet.LeafletMouseEvent) => {
        L!.DomEvent.stopPropagation(event)
        if (editable) emit('update:vertices', vertices.filter((_, i) => i !== index))
      })
      marker.addTo(editing!)
    })
  }
  for (const [index, point] of (props.points ?? []).entries()) {
    const marker = L.marker([point.lat, point.lng], {
      draggable: props.tool === 'points',
      keyboard: false,
      icon: L.divIcon({ className: 'zone-point', iconSize: [16, 16] }),
    })
    marker.bindTooltip(tooltipContent(point.name || t('zones.form.pointN', { n: index + 1 })), { direction: 'top', offset: [0, -8] })
    marker.on('dragend', () => {
      const { lat, lng } = marker.getLatLng()
      emit('move-point', index, [round(lat), round(lng)])
    })
    marker.on('click', (event: Leaflet.LeafletMouseEvent) => L!.DomEvent.stopPropagation(event))
    marker.addTo(editing)
  }
}

/** Six decimals (~10 cm) are plenty and keep the GeoJSON readable. */
const round = (value: number) => Math.round(value * 1e6) / 1e6

function onMapClick(event: Leaflet.LeafletMouseEvent) {
  const point: Coord = [round(event.latlng.lat), round(event.latlng.lng)]
  if (props.tool === 'vertices' && props.vertices) emit('update:vertices', insertVertex(props.vertices, point))
  else if (props.tool) emit('pick', point)
}

function applyTool() {
  if (!map) return
  map.getContainer().style.cursor = props.tool ? 'crosshair' : ''
  // A double click would add two vertices and zoom in.
  if (props.tool) map.doubleClickZoom.disable()
  else map.doubleClickZoom.enable()
}

function fitTo(coords: Coord[] | null) {
  if (!L || !map) return
  let bounds: Leaflet.LatLngBounds
  if (coords?.length) bounds = L.latLngBounds(coords)
  else {
    bounds = shapes?.getBounds() ?? L.latLngBounds([])
    if (editing?.getLayers().length) bounds.extend(editing.getBounds())
  }
  if (!bounds.isValid()) return
  fitted = true
  map.fitBounds(bounds, { padding: [32, 32], maxZoom: 16 })
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
  shapes = L.featureGroup().addTo(map)
  editing = L.featureGroup().addTo(map)
  map.on('click', onMapClick)
  renderEditing()
  renderShapes()
  if (props.focus?.length) fitTo(props.focus)
  applyTool()
  observer = new ResizeObserver(() => map?.invalidateSize())
  observer.observe(el.value)
})

onBeforeUnmount(() => {
  observer?.disconnect()
  map?.remove()
  map = null
  shapes = null
  editing = null
})

watch(() => [props.polygons, props.rectangles, props.markers], renderShapes, { deep: true })
watch(() => [props.vertices, props.points, props.tool, props.editColor], renderEditing, { deep: true })
watch(() => props.tool, applyTool)
watch(() => JSON.stringify(props.focus), () => fitTo(props.focus))

defineExpose({ fitTo })
</script>

<template>
  <div
    ref="el"
    class="kuulis-map z-0 size-full min-h-64 overflow-hidden rounded-md"
  />
</template>

<style>
.kuulis-map {
  isolation: isolate;
}
.zone-vertex {
  border: 2px solid #2563eb;
  border-radius: 9999px;
  background: #ffffff;
  box-shadow: 0 1px 3px rgb(0 0 0 / 0.4);
}
.zone-vertex.leaflet-marker-draggable {
  cursor: move;
}
.zone-point {
  border: 3px solid #ffffff;
  border-radius: 9999px;
  background: #7c3aed;
  box-shadow: 0 1px 3px rgb(0 0 0 / 0.5);
}
</style>
