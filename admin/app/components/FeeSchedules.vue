<script setup lang="ts">
import type { FeeSchedule, FeeTier } from '~/types/api'
import type { ScheduleIssue, TierForm } from '~/utils/wallet'

/** "Tramos" of the monthly fee: current schedule, scheduled changes and the admin form for a new one. */
const { t, locale } = useI18n()
const { request } = useApi()
const auth = useAuth()
const toast = useToast()
const apiError = useApiError()

const { data: schedules, status, error, refresh } = useAsyncData(
  'fee-schedules',
  () => request<FeeSchedule[]>('/admin/subscriptions/schedules'),
)

const thisMonth = caracasMonth()
const sorted = computed(() => [...(schedules.value ?? [])].sort((a, b) => b.effective_month.localeCompare(a.effective_month)))
/** The schedule in force: flagged by the API, else the most recent with effective_month ≤ this month. */
const current = computed(() => sorted.value.find(s => s.current) ?? sorted.value.find(s => s.effective_month <= thisMonth) ?? null)
const upcoming = computed(() => sorted.value.filter(s => s.effective_month > thisMonth).reverse())
const past = computed(() => sorted.value.filter(s => s.effective_month <= thisMonth && s !== current.value))
const scheduleKey = (s: FeeSchedule) => s.id ?? `default-${s.effective_month}`

const money = (value: string | number) => formatUsdt(value, locale.value).replace(' USDT', '')

interface TierRow { range: string, fee: string }
function tierRows(tiers: FeeTier[]): TierRow[] {
  const list = [...tiers].sort((a, b) => Number(a.above) - Number(b.above))
  const rows: TierRow[] = [{ range: t('subscriptions.schedules.noEarnings'), fee: money(0) }]
  list.forEach((tier, i) => {
    const next = list[i + 1]
    const from = sumAmounts([tier.above, 0.01])
    rows.push({
      range: next
        ? t('subscriptions.schedules.between', { from: money(from), to: money(next.above) })
        : t('subscriptions.schedules.over', { from: money(tier.above) }),
      fee: money(tier.fee),
    })
  })
  return rows
}

function creator(schedule: FeeSchedule): string {
  const by = schedule.created_by
  if (!by) return t('subscriptions.schedules.system')
  return by.name || by.email || by.id.slice(0, 8)
}

function provenance(schedule: FeeSchedule): string {
  if (!schedule.created_at) return t('subscriptions.schedules.builtIn')
  return t('subscriptions.schedules.createdBy', { by: creator(schedule), at: formatDate(schedule.created_at, locale.value) })
}

// ---- New schedule (admin) --------------------------------------------------------------------

const formOpen = ref(false)
const effectiveMonth = ref(addMonths(thisMonth, 1))
const tiers = ref<TierForm[]>([])
const monthItems = computed(() => monthsAhead(addMonths(thisMonth, 1), 24).map(m => ({ label: formatMonth(m, locale.value), value: m })))

function startForm() {
  const base = upcoming.value.at(-1) ?? current.value
  tiers.value = base ? tiersToForm([...base.tiers].sort((a, b) => Number(a.above) - Number(b.above))) : defaultTiers()
  // The first free month after the last scheduled change.
  const last = upcoming.value.at(-1)?.effective_month
  effectiveMonth.value = last ? addMonths(last, 1) : addMonths(thisMonth, 1)
  formOpen.value = true
}

function addTier() {
  const last = tiers.value.at(-1)
  tiers.value.push({ above: (last?.above ?? -100) + 100, fee: (last?.fee ?? 0) + 5 })
}
function removeTier(index: number) {
  tiers.value.splice(index, 1)
}

/** The API keeps one schedule per month (409 schedule_exists), so a taken month is rejected up front. */
const replaces = computed(() => upcoming.value.find(s => s.effective_month === effectiveMonth.value) ?? null)
const issues = computed<ScheduleIssue[]>(() => [
  ...validateSchedule(effectiveMonth.value, tiers.value, thisMonth),
  ...(replaces.value ? [{ key: 'monthTaken' }] : []),
])

const simulate = ref<number | null>(250)
const simulatedFee = computed(() => feeFor(simulate.value ?? 0, tiers.value))

const saving = ref(false)
async function save() {
  if (issues.value.length) return
  saving.value = true
  try {
    await request<FeeSchedule>('/admin/subscriptions/schedules', {
      method: 'POST',
      body: { effective_month: effectiveMonth.value, tiers: tiersToPayload(tiers.value) },
    })
    toast.add({ title: t('subscriptions.schedules.saved', { month: formatMonth(effectiveMonth.value, locale.value) }), color: 'success' })
    formOpen.value = false
    await refresh()
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    saving.value = false
  }
}

const moneyFormat = { minimumFractionDigits: 2, maximumFractionDigits: 2 }
</script>

<template>
  <div class="space-y-6">
    <UAlert
      color="neutral"
      variant="subtle"
      icon="i-lucide-info"
      :title="t('subscriptions.schedules.howTitle')"
      :description="t('subscriptions.schedules.how')"
    />
    <UAlert
      v-if="error && !schedules"
      color="error"
      variant="subtle"
      icon="i-lucide-circle-alert"
      :title="apiError(error)"
    />
    <USkeleton
      v-else-if="status === 'pending' && !schedules"
      class="h-64 max-w-xl"
    />

    <div
      v-if="schedules"
      class="grid gap-6 xl:grid-cols-2"
    >
      <UCard>
        <template #header>
          <div class="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h3 class="font-semibold">
                {{ t('subscriptions.schedules.current') }}
              </h3>
              <p
                v-if="current"
                class="text-sm text-(--ui-text-muted)"
              >
                {{ t('subscriptions.schedules.since', { month: formatMonth(current.effective_month, locale) }) }} · {{ provenance(current) }}
              </p>
            </div>
            <UButton
              v-if="auth.isAdmin.value && !formOpen"
              icon="i-lucide-plus"
              size="sm"
              :label="t('subscriptions.schedules.new')"
              @click="startForm"
            />
          </div>
        </template>
        <p
          v-if="!current"
          class="text-sm text-(--ui-text-muted)"
        >
          {{ t('subscriptions.schedules.none') }}
        </p>
        <table
          v-else
          class="w-full text-sm"
        >
          <thead>
            <tr class="border-b border-(--ui-border) text-left text-(--ui-text-muted)">
              <th class="py-2 font-medium">
                {{ t('subscriptions.schedules.earnings') }}
              </th>
              <th class="py-2 text-right font-medium">
                {{ t('subscriptions.schedules.fee') }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(row, i) in tierRows(current.tiers)"
              :key="i"
              class="border-b border-(--ui-border) last:border-b-0"
            >
              <td class="py-2 tabular-nums">
                {{ row.range }}
              </td>
              <td class="py-2 text-right font-medium tabular-nums">
                {{ row.fee }}
              </td>
            </tr>
          </tbody>
        </table>
      </UCard>

      <div class="space-y-6">
        <UCard
          v-for="schedule in upcoming"
          :key="scheduleKey(schedule)"
        >
          <template #header>
            <div class="flex items-center gap-2">
              <h3 class="font-semibold capitalize">
                {{ formatMonth(schedule.effective_month, locale) }}
              </h3>
              <UBadge
                color="info"
                variant="subtle"
                size="sm"
              >
                {{ t('subscriptions.schedules.scheduled') }}
              </UBadge>
            </div>
            <p class="text-sm text-(--ui-text-muted)">
              {{ provenance(schedule) }}
            </p>
          </template>
          <table class="w-full text-sm">
            <tbody>
              <tr
                v-for="(row, i) in tierRows(schedule.tiers)"
                :key="i"
                class="border-b border-(--ui-border) last:border-b-0"
              >
                <td class="py-1.5 tabular-nums">
                  {{ row.range }}
                </td>
                <td class="py-1.5 text-right font-medium tabular-nums">
                  {{ row.fee }}
                </td>
              </tr>
            </tbody>
          </table>
        </UCard>
        <p
          v-if="!upcoming.length"
          class="text-sm text-(--ui-text-muted)"
        >
          {{ t('subscriptions.schedules.noUpcoming') }}
        </p>

        <details
          v-if="past.length"
          class="rounded-md border border-(--ui-border) p-3 text-sm"
        >
          <summary class="cursor-pointer font-medium">
            {{ t('subscriptions.schedules.history', { n: past.length }) }}
          </summary>
          <ul class="mt-3 space-y-3">
            <li
              v-for="schedule in past"
              :key="scheduleKey(schedule)"
            >
              <p class="font-medium capitalize">
                {{ formatMonth(schedule.effective_month, locale) }}
              </p>
              <p class="text-(--ui-text-muted)">
                {{ tierRows(schedule.tiers).slice(1).map(r => `${r.range}: ${r.fee}`).join(' · ') }}
              </p>
            </li>
          </ul>
        </details>
      </div>
    </div>

    <UCard v-if="formOpen && auth.isAdmin.value">
      <template #header>
        <h3 class="font-semibold">
          {{ t('subscriptions.schedules.new') }}
        </h3>
        <p class="text-sm text-(--ui-text-muted)">
          {{ t('subscriptions.schedules.newHelp') }}
        </p>
      </template>
      <form
        class="space-y-6"
        @submit.prevent="save"
      >
        <UFormField
          :label="t('subscriptions.schedules.effectiveMonth')"
          :help="t('subscriptions.schedules.effectiveMonthHelp')"
          required
        >
          <USelect
            v-model="effectiveMonth"
            :items="monthItems"
            class="w-60 capitalize"
          />
        </UFormField>

        <div class="space-y-2">
          <div class="grid grid-cols-[1fr_1fr_auto] gap-3 text-sm font-medium text-(--ui-text-muted)">
            <span>{{ t('subscriptions.schedules.above') }}</span>
            <span>{{ t('subscriptions.schedules.fee') }}</span>
            <span class="w-8" />
          </div>
          <div
            v-for="(tier, index) in tiers"
            :key="index"
            class="grid grid-cols-[1fr_1fr_auto] items-center gap-3"
          >
            <UInputNumber
              v-model="tier.above"
              :min="0"
              :max="TIER_ABOVE_MAX"
              :step="50"
              :format-options="moneyFormat"
              :disabled="index === 0"
              :aria-label="`${t('subscriptions.schedules.above')} ${index + 1}`"
            />
            <UInputNumber
              v-model="tier.fee"
              :min="0"
              :max="FEE_MAX"
              :step="1"
              :format-options="moneyFormat"
              :aria-label="`${t('subscriptions.schedules.fee')} ${index + 1}`"
            />
            <UButton
              icon="i-lucide-trash-2"
              color="neutral"
              variant="ghost"
              size="sm"
              :disabled="index === 0"
              :aria-label="t('subscriptions.schedules.removeTier')"
              @click="removeTier(index)"
            />
          </div>
          <UButton
            v-if="tiers.length < TIERS_MAX"
            icon="i-lucide-plus"
            color="neutral"
            variant="outline"
            size="sm"
            :label="t('subscriptions.schedules.addTier')"
            @click="addTier"
          />
        </div>

        <div class="flex flex-wrap items-end gap-3 rounded-md bg-(--ui-bg-elevated) p-3 text-sm">
          <UFormField :label="t('subscriptions.schedules.simulate')">
            <UInputNumber
              v-model="simulate"
              :min="0"
              :step="10"
              :format-options="moneyFormat"
            />
          </UFormField>
          <p class="pb-2">
            {{ t('subscriptions.schedules.simulated', { fee: formatUsdt(simulatedFee, locale) }) }}
          </p>
        </div>

        <UAlert
          v-if="issues.length"
          color="error"
          variant="subtle"
          icon="i-lucide-circle-alert"
          :title="t('settings.fixErrors')"
        >
          <template #description>
            <ul class="list-disc pl-4">
              <li
                v-for="issue in issues"
                :key="issue.key + JSON.stringify(issue.params ?? {})"
              >
                {{ t(`subscriptions.schedules.errors.${issue.key}`, { ...issue.params, month: issue.params?.month ? formatMonth(String(issue.params.month), locale) : '' }) }}
              </li>
            </ul>
          </template>
        </UAlert>

        <div class="flex gap-2">
          <UButton
            type="submit"
            :label="t('subscriptions.schedules.save')"
            :loading="saving"
            :disabled="issues.length > 0"
          />
          <UButton
            color="neutral"
            variant="ghost"
            :label="t('common.cancel')"
            @click="formOpen = false"
          />
        </div>
      </form>
    </UCard>
  </div>
</template>
