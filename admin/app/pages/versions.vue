<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { AdminRelease, AppBuild, BuildUsage, ReleaseChannel } from '~/types/api'
import { RELEASE_CHANNELS } from '~/types/api'

definePageMeta({ permission: 'releases.view' })

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

// All releases at once: the table filters them, and the usage table needs every channel's newest.
const { data: releases, status: releasesStatus, error: releasesError, refresh: refreshReleases } = await useAsyncData(
  'versions-releases',
  () => request<AdminRelease[]>('/admin/app/releases'),
)
const { data: builds, status: buildsStatus, error: buildsError, refresh: refreshBuilds } = await useAsyncData(
  'versions-builds',
  () => request<AppBuild[]>('/admin/app/builds'),
)
const { data: usage, status: usageStatus, error: usageError } = await useAsyncData(
  'versions-usage',
  () => request<BuildUsage[]>('/admin/app/usage'),
)
const error = computed(() => releasesError.value ?? buildsError.value ?? usageError.value)

const latest = computed(() => latestByChannel(releases.value ?? []))
const isCurrent = (release: AdminRelease) => latest.value.get(`${release.platform}:${release.channel}`)?.id === release.id
const filteredReleases = computed(() =>
  (releases.value ?? []).filter(r => channel.value === 'all' || r.channel === channel.value),
)
const usageRows = computed(() => [...(usage.value ?? [])].sort((a, b) => b.build - a.build))

const releaseColumns = computed<TableColumn<AdminRelease>[]>(() => [
  { id: 'version', header: t('versions.version') },
  { accessorKey: 'channel', header: t('versions.channel') },
  { accessorKey: 'created_at', header: t('versions.published') },
  { accessorKey: 'size', header: t('versions.size') },
  { id: 'state', header: t('versions.state') },
  { accessorKey: 'notes', header: t('versions.notes') },
  ...(canManage.value ? [{ id: 'actions', header: '' }] : []),
])
const buildColumns = computed<TableColumn<AppBuild>[]>(() => [
  { id: 'version', header: t('versions.version') },
  { accessorKey: 'size', header: t('versions.size') },
  { accessorKey: 'sha256', header: 'SHA-256' },
  { accessorKey: 'published_channels', header: t('versions.publishedIn') },
  ...(canManage.value ? [{ id: 'actions', header: '' }] : []),
])
const usageColumns = computed<TableColumn<BuildUsage>[]>(() => [
  { accessorKey: 'build', header: t('versions.buildCol') },
  { accessorKey: 'platform', header: t('versions.platform') },
  { accessorKey: 'users', header: t('versions.users') },
])

async function copyHash(hash: string) {
  try {
    await navigator.clipboard.writeText(hash)
    toast.add({ title: t('versions.copied'), color: 'success' })
  }
  catch {
    toast.add({ title: t('errors.generic'), color: 'error' })
  }
}

// ---- Publish a build ---------------------------------------------------------------------------
const publishing = ref<AppBuild | null>(null)
const publishOpen = computed({
  get: () => publishing.value !== null,
  set: (v) => {
    if (!v) publishing.value = null
  },
})
// The API's default: production only in the production environment, qa everywhere else.
const defaultChannel: ReleaseChannel = config.public.appEnv === 'production' ? 'production' : 'qa'
const form = reactive<{ channel: ReleaseChannel, notes: string, is_mandatory: boolean }>({
  channel: defaultChannel,
  notes: '',
  is_mandatory: false,
})
const publishChannelItems = computed(() => RELEASE_CHANNELS.map(value => ({ label: t(`versions.channels.${value}`), value })))
function startPublish(build: AppBuild) {
  form.channel = defaultChannel
  form.notes = ''
  form.is_mandatory = false
  publishing.value = build
}
const saving = ref(false)
async function publish() {
  if (!publishing.value) return
  saving.value = true
  try {
    const release = await request<AdminRelease>('/admin/app/releases', {
      method: 'POST',
      body: {
        build_key: publishing.value.key,
        channel: form.channel,
        notes: form.notes.trim() || null,
        is_mandatory: form.is_mandatory,
      },
    })
    toast.add({
      title: t('versions.publishedToast', { version: release.version, channel: t(`versions.channels.${release.channel}`) }),
      color: 'success',
    })
    publishing.value = null
    await Promise.all([refreshReleases(), refreshBuilds()])
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    saving.value = false
  }
}

// ---- Change a release (mandatory, withdraw / restore, notes) ----------------------------------------
type Change = 'mandatory' | 'optional' | 'withdraw' | 'restore'
const confirming = ref<{ release: AdminRelease, change: Change } | null>(null)
const confirmOpen = computed({
  get: () => confirming.value !== null,
  set: (v) => {
    if (!v) confirming.value = null
  },
})
const CONFIRM_KEYS: Record<Change, string> = {
  mandatory: 'Mandatory',
  optional: 'Optional',
  withdraw: 'Withdraw',
  restore: 'Restore',
}
const confirmParams = computed(() => {
  const release = confirming.value?.release
  return release
    ? { version: release.version, build: release.build, channel: t(`versions.channels.${release.channel}`) }
    : {}
})
const updating = ref(false)
async function update(release: AdminRelease, body: { notes?: string | null, is_mandatory?: boolean, withdrawn?: boolean }) {
  updating.value = true
  try {
    await request<AdminRelease>(`/admin/app/releases/${release.id}`, { method: 'PATCH', body })
    toast.add({ title: t('versions.updated'), color: 'success' })
    await Promise.all([refreshReleases(), refreshBuilds()])
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
  const { release, change } = confirming.value
  const body = change === 'mandatory' || change === 'optional'
    ? { is_mandatory: change === 'mandatory' }
    : { withdrawn: change === 'withdraw' }
  if (await update(release, body)) confirming.value = null
}

const editing = ref<AdminRelease | null>(null)
const notesDraft = ref('')
const notesOpen = computed({
  get: () => editing.value !== null,
  set: (v) => {
    if (!v) editing.value = null
  },
})
function startNotes(release: AdminRelease) {
  notesDraft.value = release.notes ?? ''
  editing.value = release
}
async function saveNotes() {
  if (!editing.value) return
  if (await update(editing.value, { notes: notesDraft.value.trim() || null })) editing.value = null
}

function releaseActions(release: AdminRelease) {
  const ask = (change: Change) => () => {
    confirming.value = { release, change }
  }
  return [[
    release.is_mandatory
      ? { label: t('versions.unmarkMandatory'), icon: 'i-lucide-shield-off', onSelect: ask('optional') }
      : { label: t('versions.markMandatory'), icon: 'i-lucide-shield-alert', onSelect: ask('mandatory') },
    { label: t('versions.editNotes'), icon: 'i-lucide-pencil', onSelect: () => startNotes(release) },
  ], [
    release.withdrawn_at
      ? { label: t('versions.restore'), icon: 'i-lucide-undo-2', onSelect: ask('restore') }
      : { label: t('versions.withdraw'), icon: 'i-lucide-archive-x', color: 'error' as const, onSelect: ask('withdraw') },
  ]]
}
</script>

<template>
  <UDashboardPanel id="versions">
    <template #header>
      <UDashboardNavbar :title="t('nav.versions')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <p class="text-sm text-(--ui-text-muted)">
        {{ t('versions.help') }}
      </p>
      <UAlert
        v-if="error"
        color="error"
        variant="subtle"
        icon="i-lucide-circle-alert"
        :title="apiError(error)"
      />

      <!-- Published releases -->
      <section class="space-y-3">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <h2 class="font-semibold">
            {{ t('versions.releases') }}
          </h2>
          <USelect
            v-model="channel"
            :items="channelItems"
            class="w-44"
          />
        </div>
        <UTable
          :data="filteredReleases"
          :columns="releaseColumns"
          :loading="releasesStatus === 'pending'"
          :empty="t('common.empty')"
        >
          <template #version-cell="{ row }">
            <span class="block font-medium">{{ row.original.version }}</span>
            <span class="block text-xs text-(--ui-text-muted)">{{ t('versions.build', { build: row.original.build }) }}</span>
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
          <template #size-cell="{ row }">
            <span class="whitespace-nowrap tabular-nums">{{ formatMegabytes(row.original.size, locale) }}</span>
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
                v-else-if="isCurrent(row.original)"
                color="success"
                variant="subtle"
              >
                {{ t('versions.current') }}
              </UBadge>
              <UBadge
                v-else
                color="neutral"
                variant="outline"
              >
                {{ t('versions.active') }}
              </UBadge>
              <UBadge
                v-if="row.original.is_mandatory"
                color="warning"
                variant="subtle"
              >
                {{ t('versions.mandatory') }}
              </UBadge>
            </div>
          </template>
          <template #notes-cell="{ row }">
            <p class="max-w-xs whitespace-pre-line text-sm text-(--ui-text-muted)">
              {{ row.original.notes || '—' }}
            </p>
          </template>
          <template #actions-cell="{ row }">
            <div class="flex justify-end gap-1">
              <UButton
                v-if="row.original.download_url"
                :to="row.original.download_url"
                target="_blank"
                rel="noopener"
                size="xs"
                color="neutral"
                variant="ghost"
                icon="i-lucide-download"
                :aria-label="t('versions.download')"
              />
              <UDropdownMenu :items="releaseActions(row.original)">
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
      </section>

      <!-- Builds uploaded by the compiler -->
      <section class="space-y-3">
        <div>
          <h2 class="font-semibold">
            {{ t('versions.builds') }}
          </h2>
          <p class="text-sm text-(--ui-text-muted)">
            {{ t('versions.buildsHelp') }}
          </p>
        </div>
        <UTable
          :data="builds ?? []"
          :columns="buildColumns"
          :loading="buildsStatus === 'pending'"
          :empty="t('common.empty')"
        >
          <template #version-cell="{ row }">
            <span class="block font-medium">{{ row.original.version }} · {{ t('versions.build', { build: row.original.build }) }}</span>
            <span class="block text-xs text-(--ui-text-muted)">
              {{ row.original.file_name }}
              <template v-if="row.original.built_at"> · {{ t('versions.builtAt', { date: formatDate(row.original.built_at, locale) }) }}</template>
              <template v-if="row.original.commit"> · {{ t('versions.commit', { commit: row.original.commit.slice(0, 7) }) }}</template>
              <template v-if="row.original.profile"> · {{ row.original.profile }}</template>
            </span>
          </template>
          <template #size-cell="{ row }">
            <span class="whitespace-nowrap tabular-nums">{{ formatMegabytes(row.original.size, locale) }}</span>
          </template>
          <template #sha256-cell="{ row }">
            <div class="flex items-center gap-1">
              <code
                class="text-xs"
                :title="row.original.sha256"
              >{{ shortHash(row.original.sha256) }}</code>
              <UButton
                size="xs"
                color="neutral"
                variant="ghost"
                icon="i-lucide-copy"
                :aria-label="t('versions.copy')"
                @click="copyHash(row.original.sha256)"
              />
            </div>
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
      </section>

      <!-- JS over-the-air updates -->
      <VersionsOtaUpdates />

      <!-- Builds in use -->
      <section class="space-y-3">
        <div>
          <h2 class="font-semibold">
            {{ t('versions.usage') }}
          </h2>
          <p class="text-sm text-(--ui-text-muted)">
            {{ t('versions.usageHelp') }}
          </p>
        </div>
        <UTable
          :data="usageRows"
          :columns="usageColumns"
          :loading="usageStatus === 'pending'"
          :empty="t('common.empty')"
        >
          <template #build-cell="{ row }">
            <div class="flex flex-wrap items-center gap-2">
              <span class="font-medium tabular-nums">{{ row.original.build }}</span>
              <UBadge
                v-for="c in channelsOfferingBuild(latest, row.original.platform, row.original.build)"
                :key="c"
                :color="CHANNEL_COLORS[c]"
                variant="subtle"
                size="sm"
              >
                {{ t('versions.latestIn', { channel: t(`versions.channels.${c}`) }) }}
              </UBadge>
            </div>
          </template>
          <template #users-cell="{ row }">
            <span class="tabular-nums">{{ formatNumber(row.original.users, locale) }}</span>
          </template>
        </UTable>
      </section>

      <!-- Publish modal -->
      <UModal
        v-model:open="publishOpen"
        :title="publishing ? t('versions.publishTitle', { version: publishing.version, build: publishing.build }) : ''"
        :description="t('versions.publishHelp')"
      >
        <template #body>
          <form
            id="release-form"
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
              :label="t('versions.notes')"
              :help="t('versions.notesHelp')"
            >
              <UTextarea
                v-model="form.notes"
                class="w-full"
                :rows="4"
                :maxlength="2000"
              />
            </UFormField>
            <USwitch
              v-model="form.is_mandatory"
              :label="t('versions.mandatoryLabel')"
              :description="t('versions.mandatoryHelp')"
            />
            <UAlert
              v-if="publishing?.published_channels.includes(form.channel)"
              color="warning"
              variant="subtle"
              icon="i-lucide-triangle-alert"
              :title="t('errors.release_exists')"
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
              form="release-form"
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
        :title="confirming ? t(`versions.confirm${CONFIRM_KEYS[confirming.change]}Title`, confirmParams) : ''"
      >
        <template #body>
          <UAlert
            v-if="confirming"
            :color="confirming.change === 'mandatory' || confirming.change === 'withdraw' ? 'warning' : 'neutral'"
            variant="subtle"
            icon="i-lucide-triangle-alert"
            :title="t(`versions.confirm${CONFIRM_KEYS[confirming.change]}`, confirmParams)"
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
              :color="confirming?.change === 'withdraw' ? 'error' : 'primary'"
              :label="t('common.confirm')"
              :loading="updating"
              @click="applyChange"
            />
          </div>
        </template>
      </UModal>

      <!-- Edit notes -->
      <UModal
        v-model:open="notesOpen"
        :title="editing ? t('versions.notesTitle', { version: editing.version, build: editing.build }) : ''"
        :description="t('versions.notesHelp')"
      >
        <template #body>
          <form
            id="notes-form"
            @submit.prevent="saveNotes"
          >
            <UTextarea
              v-model="notesDraft"
              class="w-full"
              :rows="5"
              :maxlength="2000"
            />
          </form>
        </template>
        <template #footer>
          <div class="flex w-full justify-end gap-2">
            <UButton
              color="neutral"
              variant="ghost"
              :label="t('common.cancel')"
              @click="editing = null"
            />
            <UButton
              type="submit"
              form="notes-form"
              :label="t('common.save')"
              :loading="updating"
            />
          </div>
        </template>
      </UModal>
    </template>
  </UDashboardPanel>
</template>
