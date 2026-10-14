<script setup lang="ts">
import type { HoldRead, RiskUser, SignalDetail } from '~/types/api'
import type { MapLine, MapMarker } from '~/utils/geo'

/**
 * One anti-fraud alert (doc 16): why it was raised in plain words, the accounts involved, the money held
 * for it and the ride on a map. With risk.manage: dismiss or confirm it, release or void the money, ban.
 */
const props = defineProps<{ signalId: string }>()
const emit = defineEmits<{ changed: [] }>()

const { t, te, locale } = useI18n()
const { request } = useApi()
const auth = useAuth()
const toast = useToast()
const apiError = useApiError()

const canManage = computed(() => auth.can('risk.manage'))
const label = (key: string, fallback: string) => (te(key) ? t(key) : fallback)

// Not awaited: it mounts inside a slideover, after the page has rendered.
const { data: signal, error, refresh } = useAsyncData(
  `risk-signal-${props.signalId}`,
  () => request<SignalDetail>(`/admin/risk/signals/${props.signalId}`),
  { watch: [() => props.signalId] },
)

const evidence = computed(() => (signal.value ? riskEvidenceLines(signal.value, locale.value) : []))

// ---- Map ------------------------------------------------------------------------------------

const ride = computed(() => signal.value?.ride ?? null)
const trackPoints = computed(() => trackLine(ride.value?.track))
const mapMarkers = computed<MapMarker[]>(() => {
  const r = ride.value
  if (!r) return []
  return [
    { id: 'pickup', lat: r.pickup[0], lng: r.pickup[1], color: MAP_COLORS.pickup, label: t('rides.pickup') },
    { id: 'dropoff', lat: r.dropoff[0], lng: r.dropoff[1], color: MAP_COLORS.dropoff, label: t('rides.dropoff') },
  ]
})
const mapLines = computed<MapLine[]>(() => {
  const r = ride.value
  if (!r) return []
  // The planned trip as a straight dashed hint; the real path on top.
  const lines: MapLine[] = [{ id: 'route', points: [r.pickup, r.dropoff], color: MAP_COLORS.route, dashed: true }]
  if (trackPoints.value.length > 1) lines.push({ id: 'track', points: trackPoints.value, color: MAP_COLORS.track })
  return lines
})

// ---- Review ---------------------------------------------------------------------------------

const reviewOpen = ref(false)
const reviewAction = ref<'dismiss' | 'confirm'>('dismiss')
const note = ref('')
const busy = ref(false)

function startReview(action: 'dismiss' | 'confirm') {
  reviewAction.value = action
  note.value = ''
  reviewOpen.value = true
}

async function review() {
  busy.value = true
  try {
    const body = note.value.trim() ? { note: note.value.trim() } : {}
    signal.value = await request<SignalDetail>(`/admin/risk/signals/${props.signalId}/${reviewAction.value}`, { method: 'POST', body })
    toast.add({ title: t(`risk.review.${reviewAction.value}Done`), color: 'success' })
    reviewOpen.value = false
    emit('changed')
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    busy.value = false
  }
}

function holdChanged(hold: HoldRead) {
  if (signal.value) signal.value = { ...signal.value, holds: signal.value.holds.map(h => (h.id === hold.id ? hold : h)) }
  emit('changed')
}

const banTarget = ref<RiskUser | null>(null)
const banOpen = ref(false)
function startBan(user: RiskUser) {
  banTarget.value = user
  banOpen.value = true
}
async function banned() {
  await refresh()
  emit('changed')
}
</script>

<template>
  <div>
    <UAlert
      v-if="error"
      color="error"
      variant="subtle"
      icon="i-lucide-circle-alert"
      :title="apiError(error)"
    />
    <USkeleton
      v-else-if="!signal"
      class="h-64"
    />
    <div
      v-else
      class="space-y-6"
    >
      <div class="space-y-2">
        <div class="flex flex-wrap items-center gap-2">
          <UIcon
            :name="riskKindIcon(signal.kind)"
            class="size-5"
          />
          <h3 class="font-semibold">
            {{ label(riskKindKey(signal.kind), signal.kind) }}
          </h3>
          <UBadge
            :color="signalStatusColor(signal.status)"
            variant="subtle"
          >
            {{ label(`risk.statuses.${signal.status}`, signal.status) }}
          </UBadge>
          <UBadge
            :color="riskScoreColor(signal.score)"
            variant="solid"
            class="tabular-nums"
          >
            {{ t('risk.points', { n: signal.score }) }}
          </UBadge>
        </div>
        <p class="text-sm text-(--ui-text-muted)">
          {{ formatDate(signal.created_at, locale) }}
        </p>
        <div class="flex flex-wrap gap-1">
          <UBadge
            v-for="reason in signal.reasons"
            :key="reason"
            color="neutral"
            variant="outline"
            size="sm"
          >
            {{ label(riskReasonKey(reason), reason) }}
          </UBadge>
        </div>
        <ul
          v-if="evidence.length"
          class="list-disc space-y-1 pl-5 text-sm"
        >
          <li
            v-for="line in evidence"
            :key="line.key"
          >
            {{ t(line.key, line.params) }}
          </li>
        </ul>
        <p
          v-if="signal.reviewed_at"
          class="text-sm text-(--ui-text-muted)"
        >
          {{ t('risk.reviewedBy', { name: signal.reviewed_by_name || '—', date: formatDate(signal.reviewed_at, locale) }) }}
          <template v-if="signal.review_note">
            · {{ signal.review_note }}
          </template>
        </p>
        <div
          v-if="canManage"
          class="flex flex-wrap gap-2 pt-1"
        >
          <UButton
            v-if="signal.status !== 'dismissed'"
            color="neutral"
            variant="outline"
            icon="i-lucide-x"
            :label="t('risk.review.dismiss')"
            @click="startReview('dismiss')"
          />
          <UButton
            v-if="signal.status !== 'confirmed'"
            color="error"
            variant="soft"
            icon="i-lucide-check"
            :label="t('risk.review.confirm')"
            @click="startReview('confirm')"
          />
        </div>
      </div>

      <section class="space-y-2">
        <h4 class="text-sm font-medium">
          {{ t('risk.accounts') }}
        </h4>
        <ul class="divide-y divide-(--ui-border) text-sm">
          <li
            v-for="account in signal.accounts"
            :key="account.id"
            class="flex items-center justify-between gap-2 py-2"
          >
            <RiskUserCell
              :user="account"
              score
            />
            <UButton
              v-if="canManage"
              size="xs"
              color="error"
              variant="ghost"
              icon="i-lucide-ban"
              :label="t('risk.ban.button')"
              @click="startBan(account)"
            />
          </li>
        </ul>
      </section>

      <section
        v-if="signal.holds.length"
        class="space-y-2"
      >
        <h4 class="text-sm font-medium">
          {{ t('risk.heldForAlert') }}
        </h4>
        <RiskHoldList
          :holds="signal.holds"
          @changed="holdChanged"
        />
      </section>

      <section
        v-if="ride"
        class="space-y-2"
      >
        <div class="flex items-center justify-between gap-2">
          <h4 class="text-sm font-medium">
            {{ t('risk.ride') }}
          </h4>
          <NuxtLink
            :to="`/rides/${ride.id}`"
            class="text-sm text-primary hover:underline"
          >
            {{ t('live.openRide') }}
          </NuxtLink>
        </div>
        <div class="h-64">
          <MapView
            :markers="mapMarkers"
            :lines="mapLines"
          />
        </div>
        <p class="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-(--ui-text-muted)">
          <span class="flex items-center gap-2">
            <span
              class="inline-block h-1 w-6 rounded"
              :style="{ background: MAP_COLORS.track }"
            />{{ trackPoints.length > 1 ? t('rides.safety.track', { n: trackPoints.length }) : t('risk.noTrack') }}
          </span>
          <span>{{ t('risk.estimate', { distance: formatDistance(ride.distance_m, locale), duration: formatDuration(ride.duration_s) }) }}</span>
          <span v-if="Number(ride.discount) > 0">{{ t('risk.discount', { amount: formatMoney(ride.discount, locale) }) }}</span>
        </p>
      </section>
    </div>

    <UModal
      v-model:open="reviewOpen"
      :title="t(`risk.review.${reviewAction}Title`)"
      :description="t(`risk.review.${reviewAction}Help`)"
    >
      <template #body>
        <UFormField
          :label="t('risk.note')"
          :help="t('risk.noteHelp')"
        >
          <UTextarea
            v-model="note"
            class="w-full"
            :rows="3"
            :maxlength="RISK_NOTE_MAX"
          />
        </UFormField>
      </template>
      <template #footer>
        <div class="flex w-full justify-end gap-2">
          <UButton
            color="neutral"
            variant="ghost"
            :label="t('common.cancel')"
            @click="reviewOpen = false"
          />
          <UButton
            :color="reviewAction === 'confirm' ? 'error' : 'primary'"
            :label="t(`risk.review.${reviewAction}`)"
            :loading="busy"
            @click="review"
          />
        </div>
      </template>
    </UModal>

    <RiskBanModal
      v-if="banTarget"
      v-model:open="banOpen"
      :user-id="banTarget.id"
      :name="banTarget.name"
      @banned="banned"
    />
  </div>
</template>
