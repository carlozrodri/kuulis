<script setup lang="ts">
import type { MarketingAsset, MarketingContent, MarketingVariant } from '~/types/api'

const props = defineProps<{
  contentId: string
  variant: MarketingVariant
  assets: MarketingAsset[]
  editable: boolean
  canManage: boolean
}>()
const emit = defineEmits<{ updated: [content: MarketingContent] }>()

const { t, locale } = useI18n()
const { request } = useApi()
const toast = useToast()
const apiError = useApiError()

const base = computed(() => `/admin/marketing/contents/${props.contentId}/variants/${props.variant.id}`)

function fromVariant(v: MarketingVariant) {
  return {
    account: v.account ?? '',
    hook_index: v.hook_index,
    title: v.title ?? '',
    caption: v.caption,
    hashtags: formatHashtags(v.hashtags),
    checklist: v.checklist.join('\n'),
    ai_label: v.ai_label,
    asset_id: v.asset_id ?? '',
    cover_asset_id: v.cover_asset_id ?? '',
    scheduled_at: toCaracasInput(v.scheduled_at),
  }
}
const form = reactive(fromVariant(props.variant))
watch(() => props.variant, v => Object.assign(form, fromVariant(v)))

const NONE = '__none__'
const assetItems = computed(() => [
  { label: t('marketing.variant.noFile'), value: NONE },
  ...usableAssets(props.assets, 'file').map(a => ({ label: `${a.filename} · ${t(`marketing.assetRoles.${a.role}`)}`, value: a.id })),
])
const coverItems = computed(() => [
  { label: t('marketing.variant.noCover'), value: NONE },
  ...usableAssets(props.assets, 'cover').map(a => ({ label: a.filename, value: a.id })),
])
const assetModel = computed({
  get: () => form.asset_id || NONE,
  set: (v: string) => (form.asset_id = v === NONE ? '' : v),
})
const coverModel = computed({
  get: () => form.cover_asset_id || NONE,
  set: (v: string) => (form.cover_asset_id = v === NONE ? '' : v),
})
const file = computed(() => props.assets.find(a => a.id === props.variant.asset_id))
const cover = computed(() => props.assets.find(a => a.id === props.variant.cover_asset_id))
const missing = computed(() => variantMissing(props.variant, props.assets))

const saving = ref(false)
async function save() {
  saving.value = true
  try {
    const content = await request<MarketingContent>(base.value, {
      method: 'PATCH',
      body: {
        account: form.account.trim() || null,
        hook_index: Number(form.hook_index) || 0,
        title: form.title.trim() || null,
        caption: form.caption,
        hashtags: parseHashtags(form.hashtags),
        checklist: form.checklist.split('\n').map(s => s.trim()).filter(Boolean),
        ai_label: form.ai_label,
        asset_id: form.asset_id || null,
        cover_asset_id: form.cover_asset_id || null,
        scheduled_at: fromCaracasInput(form.scheduled_at),
      },
    })
    toast.add({ title: t('common.saved'), color: 'success' })
    emit('updated', content)
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    saving.value = false
  }
}

const confirmDelete = ref(false)
async function remove() {
  try {
    const content = await request<MarketingContent>(base.value, { method: 'DELETE' })
    confirmDelete.value = false
    emit('updated', content)
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
}

async function copy(text: string) {
  try {
    await navigator.clipboard.writeText(text)
    toast.add({ title: t('marketing.copiedLink'), color: 'success' })
  }
  catch {
    toast.add({ title: t('errors.generic'), color: 'error' })
  }
}

// ---- Manual metrics ---------------------------------------------------------------------------
const metricOpen = ref(false)
const metricForm = reactive(emptyMetricForm())
const metricTakenAt = ref('')
const savingMetric = ref(false)
function startMetric() {
  Object.assign(metricForm, emptyMetricForm())
  metricTakenAt.value = ''
  metricOpen.value = true
}
async function saveMetric() {
  const publication = props.variant.publication
  if (!publication) return
  savingMetric.value = true
  try {
    await request(`/admin/marketing/publications/${publication.id}/metrics`, {
      method: 'POST',
      body: { ...metricBody(metricForm), taken_at: fromCaracasInput(metricTakenAt.value) },
    })
    metricOpen.value = false
    toast.add({ title: t('marketing.metrics.saved'), color: 'success' })
    emit('updated', await request<MarketingContent>(`/admin/marketing/contents/${props.contentId}`))
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    savingMetric.value = false
  }
}
</script>

<template>
  <UCard :ui="{ body: 'space-y-4' }">
    <template #header>
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div class="flex items-center gap-2">
          <UIcon
            :name="platformIcon[props.variant.platform]"
            class="size-5"
          />
          <h3 class="font-semibold">
            {{ platformLabel[props.variant.platform] }}
          </h3>
          <UBadge
            v-if="props.variant.publication"
            color="success"
            variant="subtle"
          >
            {{ t('marketing.variant.publishedAt', { date: formatCaracasDateTime(props.variant.publication.published_at, locale) }) }}
          </UBadge>
          <UBadge
            v-else-if="props.variant.scheduled_at"
            color="neutral"
            variant="outline"
          >
            {{ formatCaracasDateTime(props.variant.scheduled_at, locale) }}
          </UBadge>
        </div>
        <UButton
          v-if="props.editable"
          size="xs"
          color="error"
          variant="ghost"
          icon="i-lucide-trash-2"
          :aria-label="t('marketing.variant.delete')"
          @click="confirmDelete = true"
        />
      </div>
    </template>

    <UAlert
      v-if="missing.length && !props.variant.publication"
      color="warning"
      variant="subtle"
      icon="i-lucide-triangle-alert"
      :title="t('marketing.variant.missing', { fields: missing.map(m => t(`marketing.variant.missingFields.${m}`)).join(', ') })"
    />

    <div class="grid gap-4 md:grid-cols-[10rem_1fr]">
      <div class="space-y-2">
        <video
          v-if="file?.kind === 'video' && file.download_url"
          :src="file.download_url"
          :poster="cover?.download_url ?? undefined"
          controls
          preload="metadata"
          class="aspect-[9/16] w-full rounded-md bg-black object-contain"
        />
        <img
          v-else-if="(file?.kind === 'imagen' ? file : cover)?.download_url"
          :src="(file?.kind === 'imagen' ? file : cover)!.download_url!"
          :alt="props.variant.platform"
          class="w-full rounded-md object-cover"
        >
        <div
          v-else
          class="flex aspect-[9/16] w-full items-center justify-center rounded-md border border-dashed border-(--ui-border) text-xs text-(--ui-text-muted)"
        >
          {{ t('marketing.variant.noFile') }}
        </div>
      </div>

      <form
        class="space-y-3"
        @submit.prevent="save"
      >
        <div class="grid gap-3 sm:grid-cols-2">
          <UFormField :label="t('marketing.variant.scheduledAt')">
            <UInput
              v-model="form.scheduled_at"
              type="datetime-local"
              :disabled="!props.editable"
              class="w-full"
            />
          </UFormField>
          <UFormField :label="t('marketing.variant.account')">
            <UInput
              v-model="form.account"
              placeholder="@kuulis"
              :maxlength="60"
              :disabled="!props.editable"
              class="w-full"
            />
          </UFormField>
          <UFormField :label="t('marketing.variant.file')">
            <USelect
              v-model="assetModel"
              :items="assetItems"
              :disabled="!props.editable"
              class="w-full"
            />
          </UFormField>
          <UFormField :label="t('marketing.variant.cover')">
            <USelect
              v-model="coverModel"
              :items="coverItems"
              :disabled="!props.editable"
              class="w-full"
            />
          </UFormField>
        </div>
        <UFormField
          v-if="props.variant.platform === 'youtube' || props.variant.platform === 'instagram'"
          :label="t('marketing.variant.title')"
          :help="t('marketing.variant.titleHelp')"
        >
          <UInput
            v-model="form.title"
            :maxlength="100"
            :disabled="!props.editable"
            class="w-full"
          />
        </UFormField>
        <UFormField
          :label="t('marketing.variant.caption')"
          :hint="`${form.caption.length} / ${CAPTION_MAX}`"
        >
          <UTextarea
            v-model="form.caption"
            :rows="4"
            :maxlength="CAPTION_MAX"
            :disabled="!props.editable"
            class="w-full"
          />
        </UFormField>
        <UFormField
          :label="t('marketing.variant.hashtags')"
          :help="t('marketing.variant.hashtagsHelp')"
        >
          <UInput
            v-model="form.hashtags"
            placeholder="#Caracas #motorizados"
            :disabled="!props.editable"
            class="w-full"
          />
        </UFormField>
        <UFormField
          :label="t('marketing.variant.checklist')"
          :help="t('marketing.variant.checklistHelp')"
        >
          <UTextarea
            v-model="form.checklist"
            :rows="2"
            :disabled="!props.editable"
            class="w-full"
          />
        </UFormField>
        <div class="flex flex-wrap items-center gap-4">
          <USwitch
            v-model="form.ai_label"
            :label="t('marketing.variant.aiLabel')"
            :disabled="!props.editable"
          />
          <UFormField
            :label="t('marketing.variant.hook')"
            class="w-28"
          >
            <UInput
              v-model.number="form.hook_index"
              type="number"
              min="0"
              max="20"
              :disabled="!props.editable"
            />
          </UFormField>
        </div>
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div class="flex min-w-0 items-center gap-1 text-xs text-(--ui-text-muted)">
            <UIcon
              name="i-lucide-link"
              class="size-3.5 shrink-0"
            />
            <span class="truncate">{{ props.variant.utm_url }}</span>
            <UButton
              size="xs"
              color="neutral"
              variant="ghost"
              icon="i-lucide-copy"
              :aria-label="t('marketing.copyLink')"
              @click="copy(props.variant.utm_url)"
            />
          </div>
          <UButton
            v-if="props.editable"
            type="submit"
            icon="i-lucide-save"
            :label="t('common.save')"
            :loading="saving"
          />
        </div>
      </form>
    </div>

    <!-- Publication and its numbers -->
    <div
      v-if="props.variant.publication"
      class="space-y-2 border-t border-(--ui-border) pt-4"
    >
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div class="text-sm">
          <span class="font-medium">{{ t('marketing.metrics.title') }}</span>
          <a
            v-if="props.variant.publication.url"
            :href="props.variant.publication.url"
            target="_blank"
            rel="noopener"
            class="ml-2 inline-flex items-center gap-1 text-(--ui-primary)"
          >
            {{ t('marketing.metrics.openPost') }}
            <UIcon
              name="i-lucide-external-link"
              class="size-3.5"
            />
          </a>
        </div>
        <UButton
          v-if="props.canManage"
          size="xs"
          icon="i-lucide-plus"
          :label="t('marketing.metrics.add')"
          @click="startMetric"
        />
      </div>
      <p
        v-if="!props.variant.publication.metrics.length"
        class="text-sm text-(--ui-text-muted)"
      >
        {{ t('marketing.metrics.none') }}
      </p>
      <div
        v-else
        class="overflow-x-auto"
      >
        <table class="w-full text-sm tabular-nums">
          <thead class="text-xs text-(--ui-text-muted)">
            <tr>
              <th class="py-1 pr-3 text-left font-medium">
                {{ t('marketing.metrics.age') }}
              </th>
              <th
                v-for="key in METRIC_FIELDS"
                :key="key"
                class="py-1 pr-3 text-right font-medium whitespace-nowrap"
              >
                {{ t(`marketing.metrics.fields.${key}`) }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="m in props.variant.publication.metrics"
              :key="m.id"
              class="border-t border-(--ui-border)"
            >
              <td class="py-1 pr-3 whitespace-nowrap">
                {{ t('marketing.metrics.hours', { n: m.age_h }) }}
              </td>
              <td
                v-for="key in METRIC_FIELDS"
                :key="key"
                class="py-1 pr-3 text-right"
              >
                {{ key === 'completion_rate' ? formatPercent(m[key], locale) : formatNumber(m[key], locale, key === 'avg_watch_s' ? 1 : 0) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <UModal
      v-model:open="metricOpen"
      :title="t('marketing.metrics.add')"
      :description="t('marketing.metrics.addHelp')"
    >
      <template #body>
        <form
          id="metric-form"
          class="grid grid-cols-2 gap-3"
          @submit.prevent="saveMetric"
        >
          <UFormField
            :label="t('marketing.metrics.takenAt')"
            :help="t('marketing.metrics.takenAtHelp')"
            class="col-span-2"
          >
            <UInput
              v-model="metricTakenAt"
              type="datetime-local"
              class="w-full"
            />
          </UFormField>
          <UFormField
            v-for="key in METRIC_FIELDS"
            :key="key"
            :label="t(`marketing.metrics.fields.${key}`)"
          >
            <UInput
              v-model.number="metricForm[key]"
              type="number"
              min="0"
              :step="key === 'avg_watch_s' || key === 'completion_rate' ? '0.1' : '1'"
              :max="key === 'completion_rate' ? 100 : undefined"
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
            @click="metricOpen = false"
          />
          <UButton
            type="submit"
            form="metric-form"
            :label="t('common.save')"
            :loading="savingMetric"
          />
        </div>
      </template>
    </UModal>

    <UModal
      v-model:open="confirmDelete"
      :title="t('marketing.variant.deleteTitle', { platform: platformLabel[props.variant.platform] })"
    >
      <template #footer>
        <div class="flex w-full justify-end gap-2">
          <UButton
            color="neutral"
            variant="ghost"
            :label="t('common.cancel')"
            @click="confirmDelete = false"
          />
          <UButton
            color="error"
            icon="i-lucide-trash-2"
            :label="t('marketing.variant.delete')"
            @click="remove"
          />
        </div>
      </template>
    </UModal>
  </UCard>
</template>
