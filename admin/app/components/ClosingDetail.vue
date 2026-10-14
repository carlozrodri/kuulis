<script setup lang="ts">
import type { Closing } from '~/types/api'

/** One closed month (doc 17): frozen totals, the Binance Pay statement with its differences, and reconciliation. */
const props = defineProps<{ closing: Closing }>()
const emit = defineEmits<{ changed: [closing: Closing] }>()

const { t, locale } = useI18n()
const { request } = useApi()
const auth = useAuth()
const toast = useToast()
const apiError = useApiError()

const canClose = computed(() => auth.can('finance.close'))
const monthLabel = computed(() => formatMonth(props.closing.month, locale.value))
const who = (person: { name: string | null, email: string | null } | null) => person?.name || person?.email || '—'
const usdt = (value: string | number | null | undefined) => formatUsdt(value, locale.value)
const differences = computed(() => props.closing.differences)
const topUpsLink = (id: string | null | undefined) => (id ? { path: '/top-ups', query: { q: id } } : null)

// ---- Statement upload / download ----------------------------------------------------------------

const fileInput = ref<HTMLInputElement | null>(null)
const uploading = ref(false)
async function onFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  const csv = await file.text()
  const problem = !csv.trim() ? 'empty' : csv.length > STATEMENT_MAX_CHARS ? 'tooLarge' : null
  if (problem) {
    toast.add({ title: t(`closings.statement.${problem}`), color: 'error' })
    return
  }
  uploading.value = true
  try {
    const updated = await request<Closing>(`/admin/finance/closings/${props.closing.month}/statement`, {
      method: 'POST',
      body: { csv, filename: file.name.slice(0, 120) },
    })
    toast.add({ title: t('closings.statement.done'), color: 'success' })
    emit('changed', updated)
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    uploading.value = false
  }
}

const downloading = ref(false)
async function downloadStatement() {
  downloading.value = true
  try {
    const { url } = await request<{ url: string }>(`/admin/finance/closings/${props.closing.month}/statement`)
    window.open(url, '_blank', 'noopener')
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    downloading.value = false
  }
}

// ---- Reconcile ------------------------------------------------------------------------------------

const note = ref('')
const state = computed(() => reconcileState(props.closing, note.value))
const reconciling = ref(false)
async function reconcile() {
  if (state.value !== 'ready') return
  reconciling.value = true
  try {
    const text = note.value.trim()
    const updated = await request<Closing>(`/admin/finance/closings/${props.closing.month}/reconcile`, {
      method: 'POST',
      body: text ? { note: text } : {},
    })
    toast.add({ title: t('closings.reconcile.done', { month: monthLabel.value }), color: 'success' })
    note.value = ''
    emit('changed', updated)
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    reconciling.value = false
  }
}
</script>

<template>
  <div class="space-y-6">
    <UAlert
      v-if="!closing.hash_ok"
      color="error"
      variant="solid"
      icon="i-lucide-shield-alert"
      :title="t('closings.tampered')"
    />

    <div class="space-y-1 text-sm">
      <p class="text-(--ui-text-muted)">
        {{ t('closings.detail.closedBy', { by: who(closing.closed_by), at: formatDate(closing.closed_at, locale) }) }}
      </p>
      <p class="break-all">
        <span class="text-(--ui-text-muted)">{{ t('closings.detail.hash') }}:</span>
        <span
          class="font-mono text-xs"
          :class="closing.hash_ok ? '' : 'text-error'"
        >{{ closing.hash }}</span>
      </p>
      <p class="break-all">
        <span class="text-(--ui-text-muted)">{{ t('closings.detail.previousHash') }}:</span>
        <span class="font-mono text-xs">{{ closing.previous_hash ?? t('closings.detail.first') }}</span>
      </p>
    </div>

    <ClosingTotals :totals="closing.totals" />

    <!-- Binance Pay statement -->
    <section class="space-y-3 border-t border-(--ui-border) pt-4">
      <div class="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 class="font-semibold">
            {{ t('closings.statement.title') }}
          </h3>
          <p class="text-sm text-(--ui-text-muted)">
            {{ closing.statement_uploaded_at ? t('closings.statement.uploaded', { at: formatDate(closing.statement_uploaded_at, locale) }) : t('closings.statement.help') }}
          </p>
        </div>
        <div class="flex flex-wrap gap-2">
          <UButton
            v-if="closing.has_statement_file"
            icon="i-lucide-file-down"
            color="neutral"
            variant="outline"
            size="sm"
            :label="t('closings.statement.download')"
            :loading="downloading"
            @click="downloadStatement"
          />
          <template v-if="canClose && !closing.reconciled_at">
            <input
              ref="fileInput"
              type="file"
              accept=".csv,text/csv"
              class="hidden"
              @change="onFile"
            >
            <UButton
              icon="i-lucide-file-up"
              size="sm"
              :variant="closing.differences ? 'outline' : 'solid'"
              :color="closing.differences ? 'neutral' : 'primary'"
              :label="closing.differences ? t('closings.statement.replace') : t('closings.statement.upload')"
              :loading="uploading"
              @click="fileInput?.click()"
            />
          </template>
        </div>
      </div>

      <template v-if="differences">
        <dl class="grid grid-cols-3 gap-3 rounded-md bg-(--ui-bg-elevated) p-3 text-sm">
          <div>
            <dt class="text-(--ui-text-muted)">
              {{ t('closings.statement.statementRows') }}
            </dt>
            <dd class="tabular-nums">
              {{ formatNumber(differences.statement_rows, locale) }} · {{ usdt(differences.statement_total) }}
            </dd>
          </div>
          <div>
            <dt class="text-(--ui-text-muted)">
              {{ t('closings.statement.kuulisRows') }}
            </dt>
            <dd class="tabular-nums">
              {{ formatNumber(differences.kuulis_rows, locale) }} · {{ usdt(differences.kuulis_total) }}
            </dd>
          </div>
          <div>
            <dt class="text-(--ui-text-muted)">
              {{ t('closings.statement.matched') }}
            </dt>
            <dd class="tabular-nums">
              {{ formatNumber(differences.matched, locale) }}
            </dd>
          </div>
        </dl>

        <UAlert
          v-if="!differenceCount(differences)"
          color="success"
          variant="subtle"
          icon="i-lucide-badge-check"
          :title="t('closings.differences.none')"
        />

        <div
          v-if="differences.missing_in_kuulis.length"
          class="space-y-1"
        >
          <h4 class="text-sm font-medium text-warning">
            {{ t('closings.differences.missingInKuulis', { n: differences.missing_in_kuulis.length }) }}
          </h4>
          <p class="text-xs text-(--ui-text-muted)">
            {{ t('closings.differences.missingInKuulisHelp') }}
          </p>
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-(--ui-border) text-left text-(--ui-text-muted)">
                <th class="py-1.5 font-medium">
                  {{ t('closings.differences.id') }}
                </th>
                <th class="py-1.5 font-medium">
                  {{ t('closings.differences.at') }}
                </th>
                <th class="py-1.5 text-right font-medium">
                  {{ t('closings.differences.amount') }}
                </th>
                <th />
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in differences.missing_in_kuulis"
                :key="row.id"
                class="border-b border-(--ui-border) last:border-b-0"
              >
                <td class="py-1.5 font-mono text-xs break-all">
                  {{ row.id }}
                </td>
                <td class="py-1.5 whitespace-nowrap">
                  {{ row.at ? formatDate(row.at, locale) : '—' }}
                </td>
                <td class="py-1.5 text-right tabular-nums">
                  {{ usdt(row.amount) }}
                </td>
                <td class="py-1.5 text-right">
                  <UButton
                    :to="topUpsLink(row.id) ?? undefined"
                    size="xs"
                    color="neutral"
                    variant="ghost"
                    icon="i-lucide-search"
                    :aria-label="t('closings.differences.find')"
                  />
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div
          v-if="differences.missing_in_binance.length"
          class="space-y-1"
        >
          <h4 class="text-sm font-medium text-warning">
            {{ t('closings.differences.missingInBinance', { n: differences.missing_in_binance.length }) }}
          </h4>
          <p class="text-xs text-(--ui-text-muted)">
            {{ t('closings.differences.missingInBinanceHelp') }}
          </p>
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-(--ui-border) text-left text-(--ui-text-muted)">
                <th class="py-1.5 font-medium">
                  {{ t('closings.differences.id') }}
                </th>
                <th class="py-1.5 font-medium">
                  {{ t('closings.differences.status') }}
                </th>
                <th class="py-1.5 text-right font-medium">
                  {{ t('closings.differences.amount') }}
                </th>
                <th />
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in differences.missing_in_binance"
                :key="row.top_up_id"
                class="border-b border-(--ui-border) last:border-b-0"
              >
                <td class="py-1.5">
                  <span class="font-mono text-xs break-all">{{ row.id ?? '—' }}</span>
                  <p class="text-xs text-(--ui-text-muted)">
                    {{ t(`closings.differences.reasons.${row.reason}`, row.reason) }}
                  </p>
                </td>
                <td class="py-1.5">
                  <UBadge
                    :color="topUpStatusColor[row.status] ?? 'neutral'"
                    variant="subtle"
                    size="sm"
                  >
                    {{ t(`topUps.statuses.${row.status}`, row.status) }}
                  </UBadge>
                </td>
                <td class="py-1.5 text-right tabular-nums">
                  {{ usdt(row.amount) }}
                </td>
                <td class="py-1.5 text-right">
                  <UButton
                    v-if="row.id"
                    :to="topUpsLink(row.id) ?? undefined"
                    size="xs"
                    color="neutral"
                    variant="ghost"
                    icon="i-lucide-search"
                    :aria-label="t('closings.differences.find')"
                  />
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div
          v-if="differences.amount_mismatch.length"
          class="space-y-1"
        >
          <h4 class="text-sm font-medium text-warning">
            {{ t('closings.differences.amountMismatch', { n: differences.amount_mismatch.length }) }}
          </h4>
          <p class="text-xs text-(--ui-text-muted)">
            {{ t('closings.differences.amountMismatchHelp') }}
          </p>
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-(--ui-border) text-left text-(--ui-text-muted)">
                <th class="py-1.5 font-medium">
                  {{ t('closings.differences.id') }}
                </th>
                <th class="py-1.5 text-right font-medium">
                  {{ t('closings.differences.kuulisAmount') }}
                </th>
                <th class="py-1.5 text-right font-medium">
                  {{ t('closings.differences.binanceAmount') }}
                </th>
                <th />
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in differences.amount_mismatch"
                :key="row.top_up_id"
                class="border-b border-(--ui-border) last:border-b-0"
              >
                <td class="py-1.5 font-mono text-xs break-all">
                  {{ row.id ?? '—' }}
                </td>
                <td class="py-1.5 text-right tabular-nums">
                  {{ usdt(row.amount) }}
                </td>
                <td class="py-1.5 text-right font-medium tabular-nums text-error">
                  {{ usdt(row.binance_amount) }}
                </td>
                <td class="py-1.5 text-right">
                  <UButton
                    v-if="row.id"
                    :to="topUpsLink(row.id) ?? undefined"
                    size="xs"
                    color="neutral"
                    variant="ghost"
                    icon="i-lucide-search"
                    :aria-label="t('closings.differences.find')"
                  />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p
          v-if="[differences.missing_in_kuulis, differences.missing_in_binance, differences.amount_mismatch].some(list => list.length >= 500)"
          class="text-xs text-(--ui-text-muted)"
        >
          {{ t('closings.differences.limited') }}
        </p>
      </template>
      <p
        v-else-if="!canClose"
        class="text-sm text-(--ui-text-muted)"
      >
        {{ t('closings.statement.none') }}
      </p>
    </section>

    <!-- Reconciliation -->
    <section class="space-y-3 border-t border-(--ui-border) pt-4">
      <div>
        <h3 class="font-semibold">
          {{ t('closings.reconcile.title') }}
        </h3>
        <p class="text-sm text-(--ui-text-muted)">
          {{ t('closings.reconcile.help') }}
        </p>
      </div>
      <UAlert
        v-if="closing.reconciled_at"
        color="success"
        variant="subtle"
        icon="i-lucide-badge-check"
        :title="t('closings.reconcile.by', { by: who(closing.reconciled_by), at: formatDate(closing.reconciled_at, locale) })"
        :description="closing.reconcile_note ?? undefined"
      />
      <form
        v-else-if="canClose"
        class="space-y-3"
        @submit.prevent="reconcile"
      >
        <p
          v-if="state === 'needsStatement'"
          class="text-sm text-warning"
        >
          {{ t('closings.reconcile.needsStatement') }}
        </p>
        <UFormField
          :label="t('closings.reconcile.note')"
          :help="t('closings.reconcile.noteHelp')"
          :required="closing.has_differences"
        >
          <UTextarea
            v-model="note"
            class="w-full"
            :rows="3"
            :maxlength="RECONCILE_NOTE_MAX"
            :disabled="!closing.differences"
          />
        </UFormField>
        <UButton
          type="submit"
          icon="i-lucide-badge-check"
          :label="t('closings.reconcile.submit')"
          :disabled="state !== 'ready'"
          :loading="reconciling"
        />
      </form>
    </section>
  </div>
</template>
