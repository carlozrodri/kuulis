<script setup lang="ts">
/**
 * Small responsive SVG chart (grouped bars or lines) with one y-axis, a hover/focus tooltip per category, a
 * legend for two or more series and a screen-reader table with the same numbers. Hand-rolled to avoid a chart
 * dependency for three charts; colours come from CSS variables so it follows light/dark mode.
 */
export interface ChartSeries {
  key: string
  label: string
  values: number[]
  /** CSS colour, e.g. "var(--chart-1)". */
  color: string
}

const props = withDefaults(defineProps<{
  /** Full label per category (tooltip and table). */
  labels: string[]
  /** Short axis label per category; defaults to `labels`. */
  ticks?: string[]
  series: ChartSeries[]
  kind?: 'bar' | 'line'
  /** Accessible name of the chart. */
  title: string
  height?: number
  format?: (value: number) => string
  /** Compact format for the y-axis ticks. */
  axisFormat?: (value: number) => string
}>(), {
  kind: 'bar',
  height: 240,
  ticks: undefined,
  format: (value: number) => String(value),
  axisFormat: undefined,
})

const { t } = useI18n()

// ---- Size ------------------------------------------------------------------------------------

const root = ref<HTMLElement | null>(null)
const width = ref(600)
let observer: ResizeObserver | undefined
onMounted(() => {
  if (!root.value) return
  width.value = root.value.clientWidth || 600
  observer = new ResizeObserver((entries) => {
    const w = entries[0]?.contentRect.width
    if (w) width.value = w
  })
  observer.observe(root.value)
})
onBeforeUnmount(() => observer?.disconnect())

const pad = { top: 12, right: 8, bottom: 26, left: 48 }
const plotW = computed(() => Math.max(40, width.value - pad.left - pad.right))
const plotH = computed(() => Math.max(40, props.height - pad.top - pad.bottom))
const count = computed(() => props.labels.length)
const step = computed(() => (count.value ? plotW.value / count.value : plotW.value))

// ---- Scale -----------------------------------------------------------------------------------

/** 1, 2, 2.5, 5 × 10^n above the data so the gridlines land on round numbers. */
function niceMax(value: number): number {
  if (!(value > 0)) return 1
  const exp = 10 ** Math.floor(Math.log10(value))
  const f = value / exp
  const nice = f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10
  return nice * exp
}
const maxValue = computed(() => niceMax(Math.max(0, ...props.series.flatMap(s => s.values.filter(Number.isFinite)))))
const y = (value: number) => pad.top + plotH.value - (Math.max(0, value) / maxValue.value) * plotH.value
const gridValues = computed(() => [0, 0.25, 0.5, 0.75, 1].map(f => f * maxValue.value))
const axisLabel = (value: number) => (props.axisFormat ?? props.format)(value)

const tickLabels = computed(() => props.ticks ?? props.labels)
/** Show every n-th tick so labels (≈ 44 px) never collide. */
const tickEvery = computed(() => Math.max(1, Math.ceil(44 / Math.max(1, step.value))))

// ---- Marks -----------------------------------------------------------------------------------

const barGap = 2
const groupWidth = computed(() => Math.max(2, step.value * 0.72))
const barWidth = computed(() => Math.max(1, (groupWidth.value - barGap * (props.series.length - 1)) / Math.max(1, props.series.length)))

interface Bar { key: string, x: number, y: number, w: number, h: number, color: string, path: string }
/** Bars with 4px rounded tops anchored to the baseline. */
const bars = computed<Bar[]>(() => {
  if (props.kind !== 'bar') return []
  const base = pad.top + plotH.value
  const out: Bar[] = []
  props.labels.forEach((_, i) => {
    const groupX = pad.left + i * step.value + (step.value - groupWidth.value) / 2
    props.series.forEach((s, j) => {
      const value = s.values[i] ?? 0
      if (!(value > 0)) return
      const x = groupX + j * (barWidth.value + barGap)
      const top = y(value)
      const h = base - top
      const w = barWidth.value
      const r = Math.min(4, w / 2, h)
      const path = `M${x},${base} V${top + r} Q${x},${top} ${x + r},${top} H${x + w - r} Q${x + w},${top} ${x + w},${top + r} V${base} Z`
      out.push({ key: `${s.key}-${i}`, x, y: top, w, h, color: s.color, path })
    })
  })
  return out
})

const cx = (i: number) => pad.left + i * step.value + step.value / 2
const lines = computed(() => {
  if (props.kind !== 'line') return []
  return props.series.map(s => ({
    key: s.key,
    color: s.color,
    points: props.labels.map((_, i) => `${cx(i)},${y(s.values[i] ?? 0)}`).join(' '),
  }))
})

// ---- Hover -----------------------------------------------------------------------------------

const active = ref<number | null>(null)
const tooltipStyle = computed(() => {
  if (active.value === null) return {}
  const x = cx(active.value)
  const flip = x > width.value * 0.6
  return {
    left: `${flip ? x - 12 : x + 12}px`,
    top: `${pad.top}px`,
    transform: flip ? 'translateX(-100%)' : 'none',
  }
})

function onKey(event: KeyboardEvent, index: number) {
  if (event.key === 'ArrowRight' && index < count.value - 1) focusColumn(index + 1)
  if (event.key === 'ArrowLeft' && index > 0) focusColumn(index - 1)
}
function focusColumn(index: number) {
  const el = root.value?.querySelector<SVGRectElement>(`[data-col="${index}"]`)
  el?.focus()
}
</script>

<template>
  <div class="space-y-2">
    <ul
      v-if="series.length > 1"
      class="flex flex-wrap gap-x-4 gap-y-1 text-xs text-(--ui-text-muted)"
    >
      <li
        v-for="s in series"
        :key="s.key"
        class="flex items-center gap-1.5"
      >
        <span
          class="inline-block size-2.5 rounded-sm"
          :style="{ background: s.color }"
          aria-hidden="true"
        />
        {{ s.label }}
      </li>
    </ul>

    <div
      ref="root"
      class="relative w-full"
      :style="{ height: `${height}px` }"
    >
      <p
        v-if="!count"
        class="flex h-full items-center justify-center text-sm text-(--ui-text-muted)"
      >
        {{ t('charts.noData') }}
      </p>
      <svg
        v-else
        :width="width"
        :height="height"
        role="img"
        :aria-label="title"
        class="block overflow-visible"
        @mouseleave="active = null"
      >
        <!-- Grid & y-axis -->
        <g aria-hidden="true">
          <g
            v-for="value in gridValues"
            :key="value"
          >
            <line
              :x1="pad.left"
              :x2="pad.left + plotW"
              :y1="y(value)"
              :y2="y(value)"
              class="stroke-(--ui-border)"
              :stroke-dasharray="value === 0 ? undefined : '2 3'"
            />
            <text
              :x="pad.left - 6"
              :y="y(value)"
              text-anchor="end"
              dominant-baseline="middle"
              class="fill-(--ui-text-muted) text-[10px] tabular-nums"
            >{{ axisLabel(value) }}</text>
          </g>
          <template
            v-for="(tick, i) in tickLabels"
            :key="`tick-${i}`"
          >
            <text
              v-if="i % tickEvery === 0"
              :x="cx(i)"
              :y="height - 8"
              text-anchor="middle"
              class="fill-(--ui-text-muted) text-[10px]"
            >{{ tick }}</text>
          </template>
        </g>

        <!-- Hover column highlight -->
        <rect
          v-if="active !== null"
          :x="pad.left + active * step"
          :y="pad.top"
          :width="step"
          :height="plotH"
          class="fill-(--ui-bg-accented)"
          opacity="0.5"
          aria-hidden="true"
        />

        <!-- Marks -->
        <g aria-hidden="true">
          <path
            v-for="bar in bars"
            :key="bar.key"
            :d="bar.path"
            :style="{ fill: bar.color }"
          />
          <template
            v-for="line in lines"
            :key="line.key"
          >
            <polyline
              :points="line.points"
              fill="none"
              stroke-width="2"
              stroke-linejoin="round"
              stroke-linecap="round"
              :style="{ stroke: line.color }"
            />
          </template>
          <template v-if="kind === 'line' && active !== null">
            <circle
              v-for="s in series"
              :key="`dot-${s.key}`"
              :cx="cx(active)"
              :cy="y(s.values[active] ?? 0)"
              r="4"
              stroke-width="2"
              class="stroke-(--ui-bg)"
              :style="{ fill: s.color }"
            />
          </template>
        </g>

        <!-- Hit targets: one per category, wider than the marks, focusable with arrow-key navigation -->
        <rect
          v-for="(label, i) in labels"
          :key="`hit-${i}`"
          :data-col="i"
          :x="pad.left + i * step"
          :y="pad.top"
          :width="step"
          :height="plotH + pad.bottom"
          fill="transparent"
          tabindex="0"
          class="outline-none focus-visible:stroke-(--ui-primary)"
          :aria-label="`${label}: ${series.map(s => `${s.label} ${format(s.values[i] ?? 0)}`).join(', ')}`"
          @mouseenter="active = i"
          @focus="active = i"
          @blur="active = null"
          @keydown="onKey($event, i)"
        />
      </svg>

      <div
        v-if="active !== null"
        class="pointer-events-none absolute z-10 min-w-36 rounded-md border border-(--ui-border) bg-(--ui-bg) px-3 py-2 text-xs shadow-lg"
        :style="tooltipStyle"
        aria-hidden="true"
      >
        <p class="mb-1 font-medium text-(--ui-text-highlighted)">
          {{ labels[active] }}
        </p>
        <p
          v-for="s in series"
          :key="s.key"
          class="flex items-center justify-between gap-3"
        >
          <span class="flex items-center gap-1.5 text-(--ui-text-muted)">
            <span
              class="inline-block size-2 rounded-sm"
              :style="{ background: s.color }"
            />
            {{ s.label }}
          </span>
          <span class="font-medium tabular-nums">{{ format(s.values[active] ?? 0) }}</span>
        </p>
      </div>
    </div>

    <table class="sr-only">
      <caption>{{ title }}</caption>
      <thead>
        <tr>
          <th scope="col">
            {{ t('charts.category') }}
          </th>
          <th
            v-for="s in series"
            :key="s.key"
            scope="col"
          >
            {{ s.label }}
          </th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="(label, i) in labels"
          :key="`row-${i}`"
        >
          <th scope="row">
            {{ label }}
          </th>
          <td
            v-for="s in series"
            :key="s.key"
          >
            {{ format(s.values[i] ?? 0) }}
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
