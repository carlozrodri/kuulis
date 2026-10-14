<script setup lang="ts">
import type { FeeSchedule, Simulation } from '~/types/api'
import type { ScheduleIssue, TierForm } from '~/utils/wallet'

/**
 * Tier simulator (doc 17): a billed month with the current tiers and with proposed ones, tier by tier, and
 * whether the current tiers reproduce what was actually billed. Nothing is saved.
 */
const { t, locale } = useI18n()
const { request } = useApi()
const toast = useToast()
const apiError = useApiError()

const thisMonth = caracasMonth()
const month = ref(addMonths(thisMonth, -1))
const monthItems = computed(() => monthsBack(addMonths(thisMonth, -1), 24).map(m => ({ label: formatMonth(m, locale.value), value: m })))

const { data: schedules, error: schedulesError } = useAsyncData(
  'fee-schedules-simulator',
  () => request<FeeSchedule[]>('/admin/subscriptions/schedules'),
)
/** The schedule in force for the chosen month: the most recent one that started on or before it. */
const baseSchedule = computed(() =>
  [...(schedules.value ?? [])]
    .sort((a, b) => b.effective_month.localeCompare(a.effective_month))
    .find(s => s.effective_month <= month.value) ?? null,
)

const tiers = ref<TierForm[]>([])
function reset() {
  const base = baseSchedule.value
  tiers.value = base ? tiersToForm([...base.tiers].sort((a, b) => Number(a.above) - Number(b.above))) : defaultTiers()
}
watch(baseSchedule, reset, { immediate: true })

function addTier() {
  const last = tiers.value.at(-1)
  tiers.value.push({ above: (last?.above ?? -100) + 100, fee: (last?.fee ?? 0) + 5 })
}
function removeTier(index: number) {
  tiers.value.splice(index, 1)
}
const issues = computed<ScheduleIssue[]>(() => validateTiers(tiers.value))

const result = ref<Simulation | null>(null)
const running = ref(false)
async function run() {
  if (issues.value.length) return
  running.value = true
  try {
    result.value = await request<Simulation>('/admin/subscriptions/simulate', {
      method: 'POST',
      body: { month: month.value, tiers: tiersToPayload(tiers.value) },
    })
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    running.value = false
  }
}
watch(month, () => (result.value = null))

const rows = computed(() => (result.value ? simulationRows(result.value) : []))
const usdt = (value: string | number | null | undefined, signed = false) => formatUsdt(value, locale.value, signed)
const differenceClass = computed(() => {
  const n = Number(result.value?.difference ?? 0)
  return n > 0 ? 'text-success' : n < 0 ? 'text-error' : ''
})
const moneyFormat = { minimumFractionDigits: 2, maximumFractionDigits: 2 }
</script>

<template>
  <div class="space-y-6">
    <UAlert
      color="neutral"
      variant="subtle"
      icon="i-lucide-calculator"
      :title="t('subscriptions.simulator.title')"
      :description="t('subscriptions.simulator.help')"
    />
    <UAlert
      v-if="schedulesError"
      color="warning"
      variant="subtle"
      icon="i-lucide-triangle-alert"
      :title="t('subscriptions.simulator.loadError')"
    />

    <div class="grid gap-6 xl:grid-cols-2">
      <UCard>
        <template #header>
          <h3 class="font-semibold">
            {{ t('subscriptions.simulator.proposed') }}
          </h3>
          <p class="text-sm text-(--ui-text-muted)">
            {{ t('subscriptions.simulator.proposedHelp') }}
          </p>
        </template>
        <form
          class="space-y-4"
          @submit.prevent="run"
        >
          <UFormField :label="t('subscriptions.simulator.month')">
            <USelect
              v-model="month"
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
            <div class="flex flex-wrap gap-2">
              <UButton
                v-if="tiers.length < TIERS_MAX"
                icon="i-lucide-plus"
                color="neutral"
                variant="outline"
                size="sm"
                :label="t('subscriptions.schedules.addTier')"
                @click="addTier"
              />
              <UButton
                icon="i-lucide-rotate-ccw"
                color="neutral"
                variant="ghost"
                size="sm"
                :label="t('subscriptions.simulator.reset')"
                @click="reset"
              />
            </div>
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
                  {{ t(`subscriptions.schedules.errors.${issue.key}`, { ...issue.params }) }}
                </li>
              </ul>
            </template>
          </UAlert>

          <UButton
            type="submit"
            icon="i-lucide-play"
            :label="t('subscriptions.simulator.run')"
            :loading="running"
            :disabled="issues.length > 0"
          />
        </form>
      </UCard>

      <UCard v-if="result">
        <template #header>
          <h3 class="font-semibold capitalize">
            {{ t('subscriptions.simulator.result', { month: formatMonth(result.month, locale) }) }}
          </h3>
        </template>
        <div class="space-y-4">
          <UAlert
            :color="result.matches ? 'success' : 'warning'"
            variant="subtle"
            :icon="result.matches ? 'i-lucide-badge-check' : 'i-lucide-triangle-alert'"
            :title="result.matches ? t('subscriptions.simulator.matches') : t('subscriptions.simulator.noMatch', { billed: usdt(result.billed) })"
          />

          <dl class="grid grid-cols-2 gap-3 rounded-md bg-(--ui-bg-elevated) p-3 text-sm sm:grid-cols-3">
            <div>
              <dt class="text-(--ui-text-muted)">
                {{ t('subscriptions.simulator.billed') }}
              </dt>
              <dd class="tabular-nums">
                {{ usdt(result.billed) }}
              </dd>
            </div>
            <div>
              <dt class="text-(--ui-text-muted)">
                {{ t('subscriptions.simulator.drivers') }}
              </dt>
              <dd class="tabular-nums">
                {{ formatNumber(result.drivers, locale) }}
              </dd>
            </div>
            <div>
              <dt class="text-(--ui-text-muted)">
                {{ t('subscriptions.simulator.referralFree') }}
              </dt>
              <dd class="tabular-nums">
                {{ formatNumber(result.referral_free, locale) }}
              </dd>
            </div>
            <div>
              <dt class="text-(--ui-text-muted)">
                {{ t('subscriptions.simulator.currentTotal') }}
              </dt>
              <dd class="font-medium tabular-nums">
                {{ usdt(result.current_total) }}
              </dd>
            </div>
            <div>
              <dt class="text-(--ui-text-muted)">
                {{ t('subscriptions.simulator.proposedTotal') }}
              </dt>
              <dd class="font-medium tabular-nums">
                {{ usdt(result.proposed_total) }}
              </dd>
            </div>
            <div>
              <dt class="text-(--ui-text-muted)">
                {{ t('subscriptions.simulator.difference') }}
              </dt>
              <dd
                class="font-semibold tabular-nums"
                :class="differenceClass"
              >
                {{ usdt(result.difference, true) }}
              </dd>
            </div>
          </dl>

          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="text-left text-(--ui-text-muted)">
                  <th
                    rowspan="2"
                    class="py-1.5 align-bottom font-medium"
                  >
                    {{ t('subscriptions.simulator.tier') }}
                  </th>
                  <th
                    colspan="3"
                    class="border-l border-(--ui-border) px-2 py-1 text-center font-medium"
                  >
                    {{ t('subscriptions.simulator.current') }}
                  </th>
                  <th
                    colspan="3"
                    class="border-l border-(--ui-border) px-2 py-1 text-center font-medium"
                  >
                    {{ t('subscriptions.simulator.proposedCol') }}
                  </th>
                </tr>
                <tr class="border-b border-(--ui-border) text-right text-xs text-(--ui-text-muted)">
                  <th class="border-l border-(--ui-border) px-2 py-1 font-medium">
                    {{ t('subscriptions.simulator.fee') }}
                  </th>
                  <th class="px-2 py-1 font-medium">
                    {{ t('subscriptions.simulator.count') }}
                  </th>
                  <th class="px-2 py-1 font-medium">
                    {{ t('subscriptions.simulator.total') }}
                  </th>
                  <th class="border-l border-(--ui-border) px-2 py-1 font-medium">
                    {{ t('subscriptions.simulator.fee') }}
                  </th>
                  <th class="px-2 py-1 font-medium">
                    {{ t('subscriptions.simulator.count') }}
                  </th>
                  <th class="px-2 py-1 font-medium">
                    {{ t('subscriptions.simulator.total') }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="row in rows"
                  :key="row.above"
                  class="border-b border-(--ui-border) text-right tabular-nums last:border-b-0"
                >
                  <td class="py-1.5 text-left">
                    {{ formatUsdt(row.above, locale).replace(' USDT', '') }}
                  </td>
                  <template v-if="row.current">
                    <td class="border-l border-(--ui-border) px-2 py-1.5">
                      {{ usdt(row.current.fee) }}
                    </td>
                    <td class="px-2 py-1.5">
                      {{ formatNumber(row.current.drivers, locale) }}
                    </td>
                    <td class="px-2 py-1.5">
                      {{ usdt(row.current.total) }}
                    </td>
                  </template>
                  <td
                    v-else
                    colspan="3"
                    class="border-l border-(--ui-border) px-2 py-1.5 text-center text-(--ui-text-muted)"
                  >
                    {{ t('subscriptions.simulator.noTier') }}
                  </td>
                  <template v-if="row.proposed">
                    <td class="border-l border-(--ui-border) px-2 py-1.5">
                      {{ usdt(row.proposed.fee) }}
                    </td>
                    <td class="px-2 py-1.5">
                      {{ formatNumber(row.proposed.drivers, locale) }}
                    </td>
                    <td class="px-2 py-1.5">
                      {{ usdt(row.proposed.total) }}
                    </td>
                  </template>
                  <td
                    v-else
                    colspan="3"
                    class="border-l border-(--ui-border) px-2 py-1.5 text-center text-(--ui-text-muted)"
                  >
                    {{ t('subscriptions.simulator.noTier') }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </UCard>
    </div>
  </div>
</template>
