<script setup lang="ts">
// A worked example of the monthly fee (docs/website-redesign/03 §6.3), computed with the real tiers from
// GET /public/site the way the API charges it (feeFor), so it can never disagree with the table next to it.
import type { FeeTier } from '~/utils/types'

const props = defineProps<{ tiers: FeeTier[], earnings?: number }>()
const { t } = useI18n()
const earned = computed(() => props.earnings ?? 250)
const fee = computed(() => feeFor(props.tiers, earned.value))
</script>

<template>
  <p class="example">
    {{ fee === 0
      ? t('drivers.fees.exampleFree', { earned: usd(earned) })
      : t('drivers.fees.example', { earned: usd(earned), fee: usd(fee), rest: usd(earned - fee) }) }}
  </p>
</template>

<style scoped>
.example {
  margin: 0;
  padding: var(--space-4) var(--space-5);
  border-radius: var(--radius-md);
  background: var(--surface-alt);
  color: var(--text);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
</style>
