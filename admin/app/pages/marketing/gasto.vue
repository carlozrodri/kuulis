<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { MarketingSpend, MarketingSpendMonth, SpendConcept } from '~/types/api'
import { SPEND_CONCEPTS } from '~/types/api'

definePageMeta({ permission: 'marketing.view' })

const { t, locale } = useI18n()
const { request } = useApi()
const auth = useAuth()
const toast = useToast()
const apiError = useApiError()
const canManage = computed(() => auth.can('marketing.manage'))

const month = ref(caracasToday().slice(0, 7))
const { data, status, error, refresh } = await useAsyncData(
  'marketing-spend',
  () => request<MarketingSpendMonth>('/admin/marketing/spend', { query: { month: month.value } }),
  { watch: [month] },
)
const monthLabel = computed(() =>
  new Intl.DateTimeFormat(locale.value, { month: 'long', year: 'numeric', timeZone: 'UTC' }).format(new Date(`${month.value}-01T00:00:00Z`)),
)

const columns = computed<TableColumn<MarketingSpend>[]>(() => [
  { accessorKey: 'date', header: t('marketing.spend.date') },
  { accessorKey: 'tool', header: t('marketing.spend.tool') },
  { accessorKey: 'concept', header: t('marketing.spend.concept') },
  { accessorKey: 'amount_usd', header: t('marketing.spend.amount') },
  { accessorKey: 'notes', header: t('marketing.spend.notes') },
  ...(canManage.value ? [{ id: 'actions', header: '' }] : []),
])

// ---- Add ----------------------------------------------------------------------------------------
const open = ref(false)
const form = reactive({ date: caracasToday(), tool: '', concept: 'suscripcion' as SpendConcept, amount_usd: null as number | null, notes: '' })
const conceptItems = computed(() => SPEND_CONCEPTS.map(value => ({ label: t(`marketing.spend.concepts.${value}`), value })))
function start() {
  Object.assign(form, { date: caracasToday(), tool: '', concept: 'suscripcion', amount_usd: null, notes: '' })
  open.value = true
}
const valid = computed(() => isDay(form.date) && form.tool.trim() && form.amount_usd !== null && form.amount_usd >= 0)
const saving = ref(false)
async function save() {
  if (!valid.value) return
  saving.value = true
  try {
    await request('/admin/marketing/spend', {
      method: 'POST',
      body: { date: form.date, tool: form.tool.trim(), concept: form.concept, amount_usd: Number(form.amount_usd).toFixed(2), notes: form.notes.trim() || null },
    })
    open.value = false
    month.value = form.date.slice(0, 7)
    toast.add({ title: t('common.saved'), color: 'success' })
    await refresh()
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    saving.value = false
  }
}

const deleting = ref<MarketingSpend | null>(null)
const deleteOpen = computed({
  get: () => deleting.value !== null,
  set: (v) => {
    if (!v) deleting.value = null
  },
})
async function remove() {
  if (!deleting.value) return
  try {
    await request(`/admin/marketing/spend/${deleting.value.id}`, { method: 'DELETE' })
    deleting.value = null
    await refresh()
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
}
</script>

<template>
  <UDashboardPanel id="marketing-spend">
    <template #header>
      <UDashboardNavbar :title="t('nav.marketingSpend')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton
            v-if="canManage"
            icon="i-lucide-plus"
            :label="t('marketing.spend.new')"
            @click="start"
          />
        </template>
      </UDashboardNavbar>
      <UDashboardToolbar>
        <div class="flex items-center gap-1">
          <UButton
            icon="i-lucide-chevron-left"
            color="neutral"
            variant="ghost"
            size="sm"
            :aria-label="t('marketing.previousMonth')"
            @click="month = shiftMonth(month, -1)"
          />
          <span class="min-w-36 text-center text-sm font-medium capitalize">{{ monthLabel }}</span>
          <UButton
            icon="i-lucide-chevron-right"
            color="neutral"
            variant="ghost"
            size="sm"
            :aria-label="t('marketing.nextMonth')"
            @click="month = shiftMonth(month, 1)"
          />
        </div>
      </UDashboardToolbar>
    </template>

    <template #body>
      <UAlert
        v-if="error"
        color="error"
        variant="subtle"
        icon="i-lucide-circle-alert"
        :title="apiError(error)"
      />
      <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <UCard :ui="{ body: 'p-3 sm:p-4' }">
          <p class="text-xs text-(--ui-text-muted)">
            {{ t('marketing.spend.total') }}
          </p>
          <p class="text-2xl font-semibold tabular-nums">
            {{ formatMoney(data?.total ?? '0', locale) }}
          </p>
        </UCard>
        <UCard
          v-for="(amount, tool) in data?.by_tool ?? {}"
          :key="tool"
          :ui="{ body: 'p-3 sm:p-4' }"
        >
          <p class="truncate text-xs text-(--ui-text-muted)">
            {{ tool }}
          </p>
          <p class="text-xl font-semibold tabular-nums">
            {{ formatMoney(amount, locale) }}
          </p>
        </UCard>
      </div>

      <UTable
        :data="data?.items ?? []"
        :columns="columns"
        :loading="status === 'pending'"
        :empty="t('common.empty')"
      >
        <template #date-cell="{ row }">
          <span class="whitespace-nowrap">{{ formatDay(row.original.date, locale) }}</span>
        </template>
        <template #concept-cell="{ row }">
          {{ t(`marketing.spend.concepts.${row.original.concept}`) }}
        </template>
        <template #amount_usd-cell="{ row }">
          <span class="tabular-nums">{{ formatMoney(row.original.amount_usd, locale) }}</span>
        </template>
        <template #notes-cell="{ row }">
          <span class="text-sm text-(--ui-text-muted)">{{ row.original.notes || '—' }}</span>
        </template>
        <template #actions-cell="{ row }">
          <UButton
            size="xs"
            color="error"
            variant="ghost"
            icon="i-lucide-trash-2"
            :aria-label="t('marketing.spend.delete')"
            @click="deleting = row.original"
          />
        </template>
      </UTable>

      <UModal
        v-model:open="open"
        :title="t('marketing.spend.new')"
      >
        <template #body>
          <form
            id="spend-form"
            class="grid grid-cols-2 gap-3"
            @submit.prevent="save"
          >
            <UFormField
              :label="t('marketing.spend.date')"
              required
            >
              <UInput
                v-model="form.date"
                type="date"
                class="w-full"
              />
            </UFormField>
            <UFormField
              :label="t('marketing.spend.amount')"
              required
            >
              <UInput
                v-model.number="form.amount_usd"
                type="number"
                min="0"
                step="0.01"
                class="w-full"
              />
            </UFormField>
            <UFormField
              :label="t('marketing.spend.tool')"
              required
            >
              <UInput
                v-model="form.tool"
                :maxlength="40"
                placeholder="Higgsfield"
                class="w-full"
              />
            </UFormField>
            <UFormField :label="t('marketing.spend.concept')">
              <USelect
                v-model="form.concept"
                :items="conceptItems"
                class="w-full"
              />
            </UFormField>
            <UFormField
              :label="t('marketing.spend.notes')"
              class="col-span-2"
            >
              <UTextarea
                v-model="form.notes"
                :rows="2"
                :maxlength="1000"
                class="w-full"
              />
            </UFormField>
          </form>
        </template>
        <template #footer>
          <div class="flex w-full justify-end gap-2">
            <UButton
              color="neutral"
              variant="ghost"
              :label="t('common.cancel')"
              @click="open = false"
            />
            <UButton
              type="submit"
              form="spend-form"
              :label="t('common.save')"
              :loading="saving"
              :disabled="!valid"
            />
          </div>
        </template>
      </UModal>

      <UModal
        v-model:open="deleteOpen"
        :title="t('marketing.spend.deleteTitle')"
        :description="deleting ? `${deleting.tool} · ${formatMoney(deleting.amount_usd, locale)} · ${formatDay(deleting.date, locale)}` : ''"
      >
        <template #footer>
          <div class="flex w-full justify-end gap-2">
            <UButton
              color="neutral"
              variant="ghost"
              :label="t('common.cancel')"
              @click="deleting = null"
            />
            <UButton
              color="error"
              icon="i-lucide-trash-2"
              :label="t('marketing.spend.delete')"
              @click="remove"
            />
          </div>
        </template>
      </UModal>
    </template>
  </UDashboardPanel>
</template>
