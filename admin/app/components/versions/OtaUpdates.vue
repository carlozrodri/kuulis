<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { AdminUpdate, ReleaseChannel, UpdateCandidate, UpdateUsage } from '~/types/api'
import { RELEASE_CHANNELS } from '~/types/api'

const { t, locale } = useI18n()
const { request } = useApi()
const apiError = useApiError()
const toast = useToast()
const auth = useAuth()
const config = useRuntimeConfig()
const canManage = computed(() => auth.can('releases.manage'))

const channel = ref<'all' | ReleaseChannel>('all')
const channelItems = computed(() => [
  { label: t('versions.allChannels'), value: 'all' },
  ...RELEASE_CHANNELS.map(value => ({ label: t(`versions.channels.${value}`), value })),
])
const QUICK_PERCENTS = [10, 50, 100]

// All updates at once: the table filters them, and the usage table needs every channel's current one.
const { data: updates, status: updatesStatus, error: updatesError, refresh: refreshUpdates } = await useAsyncData(
  'versions-ota-updates',
  () => request<AdminUpdate[]>('/admin/app/updates'),
)
const { data: candidates, status: candidatesStatus, error: candidatesError, refresh: refreshCandidates } = await useAsyncData(
  'versions-ota-candidates',
  () => request<UpdateCandidate[]>('/admin/app/update-candidates'),
)
const { data: usage, status: usageStatus, error: usageError } = await useAsyncData(
  'versions-ota-usage',
  () => request<UpdateUsage[]>('/admin/app/update-usage'),
)
const error = computed(() => updatesError.value ?? candidatesError.value ?? usageError.value)

const current = computed(() => currentUpdates(updates.value ?? []))
const filteredUpdates = computed(() =>
  (updates.value ?? []).filter(u => channel.value === 'all' || u.channel === channel.value),
)
const usageRows = computed(() => [...(usage.value ?? [])].sort((a, b) => b.users - a.users))

async function refreshAll() {
  await Promise.all([refreshUpdates(), refreshCandidates()])
}

const updateColumns = computed<TableColumn<AdminUpdate>[]>(() => [
  { accessorKey: 'id', header: t('versions.ota.update') },
  { accessorKey: 'channel', header: t('versions.channel') },
  { accessorKey: 'created_at', header: t('versions.published') },
  { accessorKey: 'message', header: t('versions.ota.commitMessage') },
  { accessorKey: 'runtime_version', header: t('versions.ota.runtime') },
  { accessorKey: 'rollout_percent', header: t('versions.ota.rollout') },
  { id: 'state', header: t('versions.state') },
  ...(canManage.value ? [{ id: 'actions', header: '' }] : []),
])
const candidateColumns = computed<TableColumn<UpdateCandidate>[]>(() => [
  { accessorKey: 'built_at', header: t('versions.ota.exported') },
  { accessorKey: 'message', header: t('versions.ota.commitMessage') },
  { accessorKey: 'runtime_version', header: t('versions.ota.runtime') },
  { accessorKey: 'bundle_size', header: t('versions.ota.bundleSize') },
  { accessorKey: 'asset_count', header: t('versions.ota.files') },
  { accessorKey: 'published_channels', header: t('versions.publishedIn') },
  ...(canManage.value ? [{ id: 'actions', header: '' }] : []),
])
const usageColumns = computed<TableColumn<UpdateUsage>[]>(() => [
  { accessorKey: 'update_id', header: t('versions.ota.update') },
  { accessorKey: 'users', header: t('versions.users') },
])

function rolloutLabel(percent: number) {
  const state = rolloutState(percent)
  if (state === 'paused') return t('versions.ota.paused')
  if (state === 'full') return t('versions.ota.full')
  return t('versions.ota.percent', { percent })
}

// ---- Publish a candidate -----------------------------------------------------------------------
const publishing = ref<UpdateCandidate | null>(null)
const publishOpen = computed({
  get: () => publishing.value !== null,
  set: (v) => {
    if (!v) publishing.value = null
  },
})
// The API's default: production only in the production environment, qa everywhere else.
const defaultChannel: ReleaseChannel = config.public.appEnv === 'production' ? 'production' : 'qa'
const form = reactive<{ channel: ReleaseChannel, rollout_percent: number, message: string }>({
  channel: defaultChannel,
  rollout_percent: 100,
  message: '',
})
const publishChannelItems = computed(() => RELEASE_CHANNELS.map(value => ({ label: t(`versions.channels.${value}`), value })))
function startPublish(candidate: UpdateCandidate) {
  form.channel = defaultChannel
  form.rollout_percent = 100
  form.message = candidate.message ?? ''
  publishing.value = candidate
}
const saving = ref(false)
async function publish() {
  if (!publishing.value) return
  saving.value = true
  try {
    const update = await request<AdminUpdate>('/admin/app/updates', {
      method: 'POST',
      body: {
        candidate_key: publishing.value.key,
        channel: form.channel,
        rollout_percent: clampPercent(form.rollout_percent) ?? 100,
        message: form.message.trim() || null,
      },
    })
    toast.add({
      title: t('versions.ota.publishedToast', { channel: t(`versions.channels.${update.channel}`) }),
      color: 'success',
    })
    publishing.value = null
    await refreshAll()
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    saving.value = false
  }
}

// ---- Change an update (pause, widen, revert) ---------------------------------------------------
type Change = 'pause' | 'full' | 'revert'
const confirming = ref<{ update: AdminUpdate, change: Change } | null>(null)
const confirmOpen = computed({
  get: () => confirming.value !== null,
  set: (v) => {
    if (!v) confirming.value = null
  },
})
const CONFIRM_KEYS: Record<Change, string> = { pause: 'Pause', full: 'Full', revert: 'Revert' }
const confirmParams = computed(() => {
  const update = confirming.value?.update
  return update ? { id: shortId(update.id), channel: t(`versions.channels.${update.channel}`) } : {}
})
const updating = ref(false)
async function patch(update: AdminUpdate, body: { rollout_percent?: number, message?: string | null }) {
  updating.value = true
  try {
    await request<AdminUpdate>(`/admin/app/updates/${update.id}`, { method: 'PATCH', body })
    toast.add({ title: t('versions.ota.updated'), color: 'success' })
    await refreshAll()
    return true
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
    return false
  }
  finally {
    updating.value = false
  }
}
async function revert(update: AdminUpdate) {
  updating.value = true
  try {
    await request<AdminUpdate>(`/admin/app/updates/${update.id}/revert`, { method: 'POST' })
    toast.add({ title: t('versions.ota.reverted'), color: 'success' })
    await refreshAll()
    return true
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
    return false
  }
  finally {
    updating.value = false
  }
}
async function applyChange() {
  if (!confirming.value) return
  const { update, change } = confirming.value
  const ok = change === 'revert'
    ? await revert(update)
    : await patch(update, { rollout_percent: change === 'pause' ? 0 : 100 })
  if (ok) confirming.value = null
}

// ---- Percentage and message --------------------------------------------------------------------
const editingPercent = ref<AdminUpdate | null>(null)
const percentDraft = ref(100)
const percentOpen = computed({
  get: () => editingPercent.value !== null,
  set: (v) => {
    if (!v) editingPercent.value = null
  },
})
function startPercent(update: AdminUpdate) {
  percentDraft.value = update.rollout_percent
  editingPercent.value = update
}
async function savePercent() {
  if (!editingPercent.value) return
  const percent = clampPercent(percentDraft.value)
  if (percent === null) return
  if (await patch(editingPercent.value, { rollout_percent: percent })) editingPercent.value = null
}

const editingMessage = ref<AdminUpdate | null>(null)
const messageDraft = ref('')
const messageOpen = computed({
  get: () => editingMessage.value !== null,
  set: (v) => {
    if (!v) editingMessage.value = null
  },
})
function startMessage(update: AdminUpdate) {
  messageDraft.value = update.message ?? ''
  editingMessage.value = update
}
async function saveMessage() {
  if (!editingMessage.value) return
  if (await patch(editingMessage.value, { message: messageDraft.value.trim() || null })) editingMessage.value = null
}

function updateActions(update: AdminUpdate) {
  const ask = (change: Change) => () => {
    confirming.value = { update, change }
  }
  return [[
    ...(update.rollout_percent > 0 ? [{ label: t('versions.ota.pause'), icon: 'i-lucide-pause', onSelect: ask('pause') }] : []),
    ...(update.rollout_percent < 100 ? [{ label: t('versions.ota.widen'), icon: 'i-lucide-maximize-2', onSelect: ask('full') }] : []),
    { label: t('versions.ota.changePercent'), icon: 'i-lucide-percent', onSelect: () => startPercent(update) },
    { label: t('versions.ota.editMessage'), icon: 'i-lucide-pencil', onSelect: () => startMessage(update) },
  ], [
    { label: t('versions.ota.revert'), icon: 'i-lucide-undo-2', color: 'error' as const, onSelect: ask('revert') },
  ]]
}
</script>

<template>
  <section class="space-y-6">
    <div>
      <h2 class="text-lg font-semibold">
        {{ t('versions.ota.title') }}
      </h2>
      <p class="text-sm text-(--ui-text-muted)">
        {{ t('versions.ota.help') }}
      </p>
    </div>
    <UAlert
      v-if="error"
      color="error"
      variant="subtle"
      icon="i-lucide-circle-alert"
      :title="apiError(error)"
    />

    <!-- Published updates -->
    <div class="space-y-3">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <h3 class="font-semibold">
          {{ t('versions.ota.updates') }}
        </h3>
        <USelect
          v-model="channel"
          :items="channelItems"
          class="w-44"
        />
      </div>
      <UTable
        :data="filteredUpdates"
        :columns="updateColumns"
        :loading="updatesStatus === 'pending'"
        :empty="t('common.empty')"
      >
        <template #id-cell="{ row }">
          <code
            class="text-xs"
            :title="row.original.id"
          >{{ shortId(row.original.id) }}</code>
        </template>
        <template #channel-cell="{ row }">
          <UBadge
            :color="CHANNEL_COLORS[row.original.channel]"
            variant="subtle"
          >
            {{ t(`versions.channels.${row.original.channel}`) }}
          </UBadge>
        </template>
        <template #created_at-cell="{ row }">
          <span class="block whitespace-nowrap">{{ formatDate(row.original.created_at, locale) }}</span>
          <span
            v-if="row.original.published_by_email"
            class="block text-xs text-(--ui-text-muted)"
          >{{ t('versions.by', { email: row.original.published_by_email }) }}</span>
        </template>
        <template #message-cell="{ row }">
          <code
            v-if="row.original.commit"
            class="block text-xs"
            :title="row.original.commit"
          >{{ row.original.commit.slice(0, 7) }}</code>
          <p class="max-w-xs whitespace-pre-line text-sm text-(--ui-text-muted)">
            {{ row.original.message || '—' }}
          </p>
        </template>
        <template #runtime_version-cell="{ row }">
          <code
            class="text-xs"
            :title="row.original.runtime_version"
          >{{ shortId(row.original.runtime_version) }}</code>
        </template>
        <template #rollout_percent-cell="{ row }">
          <span
            v-if="row.original.kind === 'rollback'"
            class="text-sm text-(--ui-text-muted)"
          >—</span>
          <UBadge
            v-else
            :color="rolloutState(row.original.rollout_percent) === 'paused' ? 'warning' : rolloutState(row.original.rollout_percent) === 'full' ? 'success' : 'info'"
            variant="subtle"
            class="whitespace-nowrap tabular-nums"
          >
            {{ rolloutLabel(row.original.rollout_percent) }}
          </UBadge>
        </template>
        <template #state-cell="{ row }">
          <div class="flex flex-wrap gap-1">
            <UBadge
              v-if="row.original.withdrawn_at"
              color="neutral"
              variant="subtle"
            >
              {{ t('versions.withdrawn', { date: formatDate(row.original.withdrawn_at, locale) }) }}
            </UBadge>
            <UBadge
              v-else-if="isCurrentUpdate(current, row.original)"
              color="success"
              variant="subtle"
            >
              {{ t('versions.ota.current') }}
            </UBadge>
            <UBadge
              v-else
              color="neutral"
              variant="outline"
            >
              {{ t('versions.active') }}
            </UBadge>
            <UBadge
              v-if="row.original.kind === 'rollback'"
              color="warning"
              variant="subtle"
            >
              {{ t('versions.ota.rollbackKind') }}
            </UBadge>
            <UBadge
              v-if="row.original.reverted_from_id"
              color="neutral"
              variant="outline"
              :title="row.original.reverted_from_id"
            >
              {{ t('versions.ota.revertOf', { id: shortId(row.original.reverted_from_id) }) }}
            </UBadge>
          </div>
        </template>
        <template #actions-cell="{ row }">
          <div class="flex justify-end">
            <UDropdownMenu
              v-if="!row.original.withdrawn_at && row.original.kind !== 'rollback'"
              :items="updateActions(row.original)"
            >
              <UButton
                size="xs"
                color="neutral"
                variant="ghost"
                icon="i-lucide-ellipsis-vertical"
                :aria-label="t('versions.actions')"
              />
            </UDropdownMenu>
          </div>
        </template>
      </UTable>
    </div>

    <!-- Exports uploaded by the compiler -->
    <div class="space-y-3">
      <div>
        <h3 class="font-semibold">
          {{ t('versions.ota.candidates') }}
        </h3>
        <p class="text-sm text-(--ui-text-muted)">
          {{ t('versions.ota.candidatesHelp') }}
        </p>
      </div>
      <UTable
        :data="candidates ?? []"
        :columns="candidateColumns"
        :loading="candidatesStatus === 'pending'"
        :empty="t('common.empty')"
      >
        <template #built_at-cell="{ row }">
          <span class="whitespace-nowrap">{{ row.original.built_at ? formatDate(row.original.built_at, locale) : '—' }}</span>
        </template>
        <template #message-cell="{ row }">
          <code
            v-if="row.original.commit"
            class="block text-xs"
            :title="row.original.commit"
          >{{ row.original.commit.slice(0, 7) }}</code>
          <p class="max-w-xs whitespace-pre-line text-sm text-(--ui-text-muted)">
            {{ row.original.message || '—' }}
          </p>
        </template>
        <template #runtime_version-cell="{ row }">
          <code
            class="text-xs"
            :title="row.original.runtime_version"
          >{{ shortId(row.original.runtime_version) }}</code>
        </template>
        <template #bundle_size-cell="{ row }">
          <span class="whitespace-nowrap tabular-nums">{{ formatMegabytes(row.original.bundle_size, locale) }}</span>
        </template>
        <template #asset_count-cell="{ row }">
          <span class="tabular-nums">{{ formatNumber(row.original.asset_count, locale) }}</span>
        </template>
        <template #published_channels-cell="{ row }">
          <div
            v-if="row.original.published_channels.length"
            class="flex flex-wrap gap-1"
          >
            <UBadge
              v-for="c in row.original.published_channels"
              :key="c"
              :color="CHANNEL_COLORS[c] ?? 'neutral'"
              variant="subtle"
            >
              {{ t(`versions.channels.${c}`) }}
            </UBadge>
          </div>
          <span
            v-else
            class="text-sm text-(--ui-text-muted)"
          >{{ t('versions.notPublished') }}</span>
        </template>
        <template #actions-cell="{ row }">
          <div class="flex justify-end">
            <UButton
              size="xs"
              icon="i-lucide-upload"
              :label="t('versions.publish')"
              :disabled="row.original.published_channels.length === RELEASE_CHANNELS.length"
              @click="startPublish(row.original)"
            />
          </div>
        </template>
      </UTable>
    </div>

    <!-- Updates in use -->
    <div class="space-y-3">
      <div>
        <h3 class="font-semibold">
          {{ t('versions.ota.usage') }}
        </h3>
        <p class="text-sm text-(--ui-text-muted)">
          {{ t('versions.ota.usageHelp') }}
        </p>
      </div>
      <UTable
        :data="usageRows"
        :columns="usageColumns"
        :loading="usageStatus === 'pending'"
        :empty="t('common.empty')"
      >
        <template #update_id-cell="{ row }">
          <div class="flex flex-wrap items-center gap-2">
            <span
              v-if="row.original.update_id === EMBEDDED_UPDATE"
              class="font-medium"
            >{{ t('versions.ota.embedded') }}</span>
            <code
              v-else
              class="text-xs"
              :title="row.original.update_id"
            >{{ shortId(row.original.update_id) }}</code>
            <UBadge
              v-for="c in channelsServingUpdate(current, row.original.update_id)"
              :key="c"
              :color="CHANNEL_COLORS[c]"
              variant="subtle"
              size="sm"
            >
              {{ t('versions.ota.servingIn', { channel: t(`versions.channels.${c}`) }) }}
            </UBadge>
          </div>
        </template>
        <template #users-cell="{ row }">
          <span class="tabular-nums">{{ formatNumber(row.original.users, locale) }}</span>
        </template>
      </UTable>
    </div>

    <!-- Publish modal -->
    <UModal
      v-model:open="publishOpen"
      :title="t('versions.ota.publishTitle')"
      :description="t('versions.ota.publishHelp')"
    >
      <template #body>
        <form
          id="update-form"
          class="space-y-4"
          @submit.prevent="publish"
        >
          <UFormField
            :label="t('versions.channel')"
            :help="t('versions.channelHelp')"
          >
            <USelect
              v-model="form.channel"
              :items="publishChannelItems"
              class="w-full"
            />
          </UFormField>
          <UFormField
            :label="t('versions.ota.rolloutLabel')"
            :help="t('versions.ota.rolloutHelp')"
          >
            <div class="flex flex-wrap items-center gap-2">
              <UInputNumber
                v-model="form.rollout_percent"
                :min="0"
                :max="100"
                :step="1"
                class="w-32"
              />
              <UButton
                v-for="p in QUICK_PERCENTS"
                :key="p"
                size="xs"
                :color="form.rollout_percent === p ? 'primary' : 'neutral'"
                :variant="form.rollout_percent === p ? 'solid' : 'outline'"
                :label="t('versions.ota.percent', { percent: p })"
                @click="form.rollout_percent = p"
              />
            </div>
          </UFormField>
          <UFormField
            :label="t('versions.ota.message')"
            :help="t('versions.ota.messageHelp')"
          >
            <UTextarea
              v-model="form.message"
              class="w-full"
              :rows="3"
              :maxlength="500"
            />
          </UFormField>
          <UAlert
            v-if="publishing?.published_channels.includes(form.channel)"
            color="warning"
            variant="subtle"
            icon="i-lucide-triangle-alert"
            :title="t('errors.update_exists')"
          />
        </form>
      </template>
      <template #footer>
        <div class="flex w-full justify-end gap-2">
          <UButton
            color="neutral"
            variant="ghost"
            :label="t('common.cancel')"
            @click="publishing = null"
          />
          <UButton
            type="submit"
            form="update-form"
            icon="i-lucide-upload"
            :label="t('versions.publish')"
            :loading="saving"
            :disabled="!!publishing?.published_channels.includes(form.channel)"
          />
        </div>
      </template>
    </UModal>

    <!-- Confirm a change -->
    <UModal
      v-model:open="confirmOpen"
      :title="confirming ? t(`versions.ota.confirm${CONFIRM_KEYS[confirming.change]}Title`, confirmParams) : ''"
    >
      <template #body>
        <UAlert
          v-if="confirming"
          :color="confirming.change === 'revert' ? 'error' : 'warning'"
          variant="subtle"
          icon="i-lucide-triangle-alert"
          :title="t(`versions.ota.confirm${CONFIRM_KEYS[confirming.change]}`, confirmParams)"
        />
      </template>
      <template #footer>
        <div class="flex w-full justify-end gap-2">
          <UButton
            color="neutral"
            variant="ghost"
            :label="t('common.cancel')"
            @click="confirming = null"
          />
          <UButton
            :color="confirming?.change === 'revert' ? 'error' : 'primary'"
            :label="t('common.confirm')"
            :loading="updating"
            @click="applyChange"
          />
        </div>
      </template>
    </UModal>

    <!-- Change the percentage -->
    <UModal
      v-model:open="percentOpen"
      :title="editingPercent ? t('versions.ota.percentTitle', { id: shortId(editingPercent.id) }) : ''"
      :description="t('versions.ota.rolloutHelp')"
    >
      <template #body>
        <form
          id="percent-form"
          class="flex flex-wrap items-center gap-2"
          @submit.prevent="savePercent"
        >
          <UInputNumber
            v-model="percentDraft"
            :min="0"
            :max="100"
            :step="1"
            class="w-32"
          />
          <UButton
            v-for="p in QUICK_PERCENTS"
            :key="p"
            size="xs"
            :color="percentDraft === p ? 'primary' : 'neutral'"
            :variant="percentDraft === p ? 'solid' : 'outline'"
            :label="t('versions.ota.percent', { percent: p })"
            @click="percentDraft = p"
          />
        </form>
      </template>
      <template #footer>
        <div class="flex w-full justify-end gap-2">
          <UButton
            color="neutral"
            variant="ghost"
            :label="t('common.cancel')"
            @click="editingPercent = null"
          />
          <UButton
            type="submit"
            form="percent-form"
            :label="t('common.save')"
            :loading="updating"
          />
        </div>
      </template>
    </UModal>

    <!-- Edit the message -->
    <UModal
      v-model:open="messageOpen"
      :title="editingMessage ? t('versions.ota.messageTitle', { id: shortId(editingMessage.id) }) : ''"
      :description="t('versions.ota.messageHelp')"
    >
      <template #body>
        <form
          id="message-form"
          @submit.prevent="saveMessage"
        >
          <UTextarea
            v-model="messageDraft"
            class="w-full"
            :rows="4"
            :maxlength="500"
          />
        </form>
      </template>
      <template #footer>
        <div class="flex w-full justify-end gap-2">
          <UButton
            color="neutral"
            variant="ghost"
            :label="t('common.cancel')"
            @click="editingMessage = null"
          />
          <UButton
            type="submit"
            form="message-form"
            :label="t('common.save')"
            :loading="updating"
          />
        </div>
      </template>
    </UModal>
  </section>
</template>
