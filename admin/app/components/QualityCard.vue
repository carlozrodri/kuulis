<script setup lang="ts">
/**
 * Quality of a person (doc 15): live rates per role, the last 8 weeks and the automatic pauses, which
 * someone with quality.manage can lift early. `role` limits it to one role (the driver page); without it
 * the passenger block shows, plus the driver one when the person drives.
 */
import type { QualityDetail, QualityPause, QualityRole, QualityStats } from '~/types/api'

const props = defineProps<{ userId: string, role?: QualityRole }>()

const { t, locale } = useI18n()
const { request } = useApi()
const auth = useAuth()
const toast = useToast()
const apiError = useApiError()

const canView = computed(() => auth.can('quality.view'))
const canManage = computed(() => auth.can('quality.manage'))

const { data, error, refresh } = await useAsyncData(
  `quality-${props.userId}`,
  () => (canView.value ? request<QualityDetail>(`/admin/quality/users/${props.userId}`) : Promise.resolve(null)),
  { watch: [() => props.userId] },
)

const roles = computed<QualityRole[]>(() => {
  if (props.role) return [props.role]
  return data.value?.driver ? ['passenger', 'driver'] : ['passenger']
})
const blocks = computed(() => {
  const d = data.value
  if (!d) return []
  return roles.value.flatMap((role) => {
    const stats: QualityStats | null = role === 'driver' ? d.driver : d.passenger
    return stats ? [{ role, stats }] : []
  })
})

// ---- 8-week trend ---------------------------------------------------------------------------

const weekTicks = computed(() => (data.value?.weeks ?? []).map(w => formatShortDay(w.week, locale.value)))
const weekLabels = computed(() => (data.value?.weeks ?? []).map(w => t('quality.card.weekOf', { day: formatDay(w.week, locale.value) })))
// Weeks with nothing to divide by stay empty (NaN draws no bar).
const rate = (value: number | null) => value ?? Number.NaN
function trendSeries(role: QualityRole) {
  const weeks = data.value?.weeks ?? []
  if (role === 'driver') {
    return [
      { key: 'acceptance', label: t('quality.acceptanceRate'), values: weeks.map(w => rate(w.acceptance_rate)), color: 'var(--chart-1)' },
      { key: 'cancel', label: t('quality.cancelRate'), values: weeks.map(w => rate(w.driver_cancel_rate)), color: 'var(--chart-3)' },
    ]
  }
  return [{ key: 'cancel', label: t('quality.cancelRate'), values: weeks.map(w => rate(w.passenger_cancel_rate)), color: 'var(--chart-3)' }]
}
const percentFormat = (value: number) => formatPercent(value, locale.value)

// ---- Pauses ---------------------------------------------------------------------------------

const pauses = computed(() => (data.value?.pauses ?? []).filter(p => roles.value.includes(p.role)))

const lifting = ref<string | null>(null)
async function lift(pause: QualityPause) {
  if (!confirm(t('quality.card.liftConfirm'))) return
  lifting.value = pause.id
  try {
    await request(`/admin/quality/pauses/${pause.id}/lift`, { method: 'POST' })
    toast.add({ title: t('quality.card.liftDone'), color: 'success' })
    await refresh()
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    lifting.value = null
  }
}
</script>

<template>
  <UCard v-if="canView">
    <template #header>
      <div class="flex flex-wrap items-center justify-between gap-2">
        <h2 class="font-semibold">
          {{ t('quality.card.title') }}
        </h2>
        <span
          v-if="data"
          class="text-xs text-(--ui-text-muted)"
        >{{ t('quality.card.window', { n: data.window_days }) }}</span>
      </div>
    </template>

    <UAlert
      v-if="error"
      color="error"
      variant="subtle"
      icon="i-lucide-circle-alert"
      :title="apiError(error)"
    />
    <USkeleton
      v-else-if="!data"
      class="h-40"
    />

    <div
      v-else
      class="space-y-6"
    >
      <p
        v-if="role === 'driver' && !data.driver"
        class="text-sm text-(--ui-text-muted)"
      >
        {{ t('quality.card.notDriver') }}
      </p>

      <section
        v-for="block in blocks"
        :key="block.role"
        class="space-y-3"
      >
        <div class="flex flex-wrap items-center gap-2">
          <h3
            v-if="!role"
            class="text-sm font-medium"
          >
            {{ t(`quality.asRole.${block.role}`) }}
          </h3>
          <UBadge
            :color="qualityBadge(block.stats.level).color"
            :variant="qualityBadge(block.stats.level).variant"
          >
            {{ t(`quality.levels.${block.stats.level}`) }}
          </UBadge>
          <UBadge
            v-for="reason in block.stats.reasons"
            :key="reason"
            color="neutral"
            variant="outline"
            size="sm"
          >
            {{ t(`quality.reasons.${reason}`) }}
          </UBadge>
        </div>

        <dl class="grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
          <div>
            <dt class="text-(--ui-text-muted)">
              {{ t('quality.cancelRate') }}
            </dt>
            <dd class="text-lg font-semibold tabular-nums">
              {{ formatPercent(block.stats.cancel_rate, locale) }}
            </dd>
            <dd class="text-xs text-(--ui-text-muted)">
              {{ t('quality.cancelsOf', { n: block.stats.cancels, total: block.role === 'driver' ? block.stats.accepted : block.stats.rides }) }}
            </dd>
          </div>
          <div v-if="block.role === 'driver'">
            <dt class="text-(--ui-text-muted)">
              {{ t('quality.acceptanceRate') }}
            </dt>
            <dd class="text-lg font-semibold tabular-nums">
              {{ formatPercent(block.stats.acceptance_rate, locale) }}
            </dd>
            <dd class="text-xs text-(--ui-text-muted)">
              {{ t('quality.acceptedOf', { n: block.stats.accepted, total: block.stats.offers }) }}
            </dd>
          </div>
          <div v-else>
            <dt class="text-(--ui-text-muted)">
              {{ t('quality.noShows') }}
            </dt>
            <dd class="text-lg font-semibold tabular-nums">
              {{ formatNumber(block.stats.no_shows, locale) }}
            </dd>
          </div>
          <div>
            <dt class="text-(--ui-text-muted)">
              {{ t('quality.rating') }}
            </dt>
            <dd class="text-lg font-semibold tabular-nums">
              {{ block.stats.rating_avg !== null ? `★ ${formatRating(block.stats.rating_avg)}` : '—' }}
            </dd>
            <dd class="text-xs text-(--ui-text-muted)">
              {{ t('quality.ratingCount', block.stats.rating_count) }}
            </dd>
          </div>
          <div>
            <dt class="text-(--ui-text-muted)">
              {{ t('quality.completed') }}
            </dt>
            <dd class="text-lg font-semibold tabular-nums">
              {{ formatNumber(block.stats.completed, locale) }}
            </dd>
          </div>
        </dl>

        <div v-if="data.weeks.length">
          <p class="mb-1 text-xs text-(--ui-text-muted)">
            {{ t('quality.card.trend') }}
          </p>
          <SimpleChart
            :title="`${t('quality.card.trend')} · ${t(`quality.asRole.${block.role}`)}`"
            :labels="weekLabels"
            :ticks="weekTicks"
            :series="trendSeries(block.role)"
            :format="percentFormat"
            :height="160"
          />
        </div>
      </section>

      <section class="space-y-2">
        <h3 class="text-sm font-medium">
          {{ t('quality.card.pauses') }}
        </h3>
        <p
          v-if="!pauses.length"
          class="text-sm text-(--ui-text-muted)"
        >
          {{ t('quality.card.noPauses') }}
        </p>
        <ul
          v-else
          class="divide-y divide-(--ui-border) text-sm"
        >
          <li
            v-for="pause in pauses"
            :key="pause.id"
            class="flex flex-wrap items-center justify-between gap-2 py-2"
          >
            <div>
              <p class="font-medium">
                {{ t(`quality.pauseReasons.${pause.reason}`) }}
                <span
                  v-if="!role"
                  class="font-normal text-(--ui-text-muted)"
                >· {{ t(`quality.sides.${pause.role}`) }}</span>
              </p>
              <p class="text-xs text-(--ui-text-muted)">
                {{ formatDate(pause.created_at, locale) }} ·
                <template v-if="pause.lifted_at">
                  {{ t('quality.card.liftedAt', { date: formatDate(pause.lifted_at, locale) }) }}
                </template>
                <template v-else-if="isPauseActive(pause)">
                  {{ t('quality.card.until', { date: formatDate(pause.until, locale) }) }}
                </template>
                <template v-else>
                  {{ t('quality.card.ended', { date: formatDate(pause.until, locale) }) }}
                </template>
              </p>
            </div>
            <div
              v-if="isPauseActive(pause)"
              class="flex items-center gap-2"
            >
              <UBadge
                color="warning"
                variant="subtle"
                icon="i-lucide-pause"
              >
                {{ t('quality.card.active') }}
              </UBadge>
              <UButton
                v-if="canManage"
                size="xs"
                color="neutral"
                variant="outline"
                icon="i-lucide-play"
                :loading="lifting === pause.id"
                :label="t('quality.card.lift')"
                @click="lift(pause)"
              />
            </div>
          </li>
        </ul>
      </section>
    </div>
  </UCard>
</template>
