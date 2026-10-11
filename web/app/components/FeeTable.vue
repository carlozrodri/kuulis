<script setup lang="ts">
import type { FeeTier } from '~/utils/types'

const props = defineProps<{ tiers: FeeTier[] }>()
const { t } = useI18n()

/** "$0 – $100 → $0", one row per tier, the last one open-ended. */
const rows = computed(() => {
  const sorted = [...props.tiers].sort((a, b) => Number(a.above) - Number(b.above))
  return sorted.map((tier, index) => {
    const next = sorted[index + 1]
    const from = Number(tier.above)
    const range = next
      ? t('fees.range', { from: usd(from), to: usd(Number(next.above)) })
      : t('fees.over', { from: usd(from) })
    return { range, fee: Number(tier.fee) }
  })
})
</script>

<template>
  <table class="fees">
    <thead>
      <tr>
        <th>{{ t('fees.earned') }}</th>
        <th>{{ t('fees.pay') }}</th>
      </tr>
    </thead>
    <tbody>
      <tr
        v-for="row in rows"
        :key="row.range"
      >
        <td>{{ row.range }}</td>
        <td :class="{ free: row.fee === 0 }">
          {{ row.fee === 0 ? t('fees.nothing') : usd(row.fee) }}
        </td>
      </tr>
    </tbody>
  </table>
</template>

<style scoped>
.fees {
  width: 100%;
  border-collapse: collapse;
}

th {
  text-align: left;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--muted);
  padding: 0 0 10px;
}

td {
  padding: 12px 0;
  border-top: 1px solid var(--border);
  font-weight: 600;
}

td:last-child,
th:last-child {
  text-align: right;
}

.free {
  color: var(--primary);
  font-weight: 800;
}
</style>
