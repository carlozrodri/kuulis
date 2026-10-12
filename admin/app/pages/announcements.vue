<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { AdminAnnouncement } from '~/types/api'
import { ANNOUNCEMENT_STYLES, APP_MODES, APP_SCREENS } from '~/types/api'
import type { AnnouncementForm, AnnouncementStatus } from '~/utils/control'

definePageMeta({ permission: 'announcements.view' })

const { t, locale } = useI18n()
const { request } = useApi()
const apiError = useApiError()
const toast = useToast()
const auth = useAuth()
const canManage = computed(() => auth.can('announcements.manage'))

const { data: announcements, status, error, refresh } = await useAsyncData(
  'announcements',
  () => request<AdminAnnouncement[]>('/admin/announcements'),
)
const areas = await useServiceAreaNames()

// Status chips follow the clock: re-evaluate every minute.
const now = ref(new Date())
let timer: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  timer = setInterval(() => {
    now.value = new Date()
  }, 60_000)
})
onBeforeUnmount(() => clearInterval(timer))

const STATUS_COLORS: Record<AnnouncementStatus, 'info' | 'success' | 'neutral'> = {
  scheduled: 'info',
  active: 'success',
  ended: 'neutral',
}
const STYLE_COLORS = { info: 'info', warning: 'warning', promo: 'primary' } as const

const columns = computed<TableColumn<AdminAnnouncement>[]>(() => [
  { id: 'title', header: t('announcements.title') },
  { id: 'status', header: t('announcements.status') },
  { id: 'dates', header: t('announcements.when') },
  { id: 'audience', header: t('announcements.audienceCol') },
  { id: 'reach', header: t('announcements.reach') },
  ...(canManage.value ? [{ id: 'actions', header: '' }] : []),
])

const dismissRate = (a: AdminAnnouncement) => (a.seen ? formatPercent(a.dismissed / a.seen, locale.value) : '—')

// ---- Create / edit ----------------------------------------------------------------------------------

const editing = ref<{ id: string | null } | null>(null)
const formOpen = computed({
  get: () => editing.value !== null,
  set: (v) => {
    if (!v) editing.value = null
  },
})
const form = reactive<AnnouncementForm>(defaultAnnouncementForm())
const showIssues = ref(false)
const issues = computed(() => validateAnnouncement(form))

function startCreate() {
  Object.assign(form, defaultAnnouncementForm())
  showIssues.value = false
  editing.value = { id: null }
}
function startEdit(a: AdminAnnouncement) {
  Object.assign(form, announcementFormFrom(a))
  showIssues.value = false
  editing.value = { id: a.id }
}
function startCopy(a: AdminAnnouncement) {
  // Same texts and audience, new dates.
  const fresh = defaultAnnouncementForm()
  Object.assign(form, announcementFormFrom(a), { starts_at: fresh.starts_at, ends_at: fresh.ends_at })
  showIssues.value = false
  editing.value = { id: null }
}

const styleItems = computed(() => ANNOUNCEMENT_STYLES.map(s => ({ label: t(`announcements.styles.${s}`), value: s })))
const roleItems = computed(() => APP_MODES.map(r => ({ label: t(`control.modes.${r}`), value: r })))
const areaItems = computed(() => {
  const names = [...areas.value, ...form.areas.filter(a => !areas.value.includes(a))]
  return names.map(name => ({ label: name, value: name }))
})
const ctaKindItems = computed(() => [
  { label: t('announcements.ctaScreen'), value: 'screen' },
  { label: t('announcements.ctaUrl'), value: 'url' },
])
const screenItems = computed(() => APP_SCREENS.map(s => ({ label: t(`announcements.screens.${s}`), value: s })))
const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone

const saving = ref(false)
async function save() {
  if (!editing.value) return
  if (issues.value.length) {
    showIssues.value = true
    return
  }
  saving.value = true
  try {
    const id = editing.value.id
    await request<AdminAnnouncement>(id ? `/admin/announcements/${id}` : '/admin/announcements', {
      method: id ? 'PUT' : 'POST',
      body: announcementPayload(form),
    })
    toast.add({ title: t(id ? 'announcements.updated' : 'announcements.created'), color: 'success' })
    editing.value = null
    await refresh()
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    saving.value = false
  }
}

// ---- Delete -----------------------------------------------------------------------------------------

const deleting = ref<AdminAnnouncement | null>(null)
const deleteOpen = computed({
  get: () => deleting.value !== null,
  set: (v) => {
    if (!v) deleting.value = null
  },
})
const removing = ref(false)
async function remove() {
  if (!deleting.value) return
  removing.value = true
  try {
    await request(`/admin/announcements/${deleting.value.id}`, { method: 'DELETE' })
    toast.add({ title: t('announcements.deleted'), color: 'success' })
    deleting.value = null
    await refresh()
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    removing.value = false
  }
}

function rowActions(a: AdminAnnouncement) {
  return [[
    { label: t('announcements.edit'), icon: 'i-lucide-pencil', onSelect: () => startEdit(a) },
    { label: t('announcements.copy'), icon: 'i-lucide-copy', onSelect: () => startCopy(a) },
  ], [
    { label: t('announcements.delete'), icon: 'i-lucide-trash-2', color: 'error' as const, onSelect: () => { deleting.value = a } },
  ]]
}
</script>

<template>
  <UDashboardPanel id="announcements">
    <template #header>
      <UDashboardNavbar :title="t('nav.announcements')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton
            v-if="canManage"
            icon="i-lucide-plus"
            :label="t('announcements.new')"
            @click="startCreate"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <p class="text-sm text-(--ui-text-muted)">
        {{ t('announcements.help') }}
      </p>
      <UAlert
        v-if="error"
        color="error"
        variant="subtle"
        icon="i-lucide-circle-alert"
        :title="apiError(error)"
      />

      <UTable
        :data="announcements ?? []"
        :columns="columns"
        :loading="status === 'pending'"
        :empty="t('announcements.empty')"
      >
        <template #title-cell="{ row }">
          <div class="flex max-w-sm items-start gap-2">
            <UBadge
              :color="STYLE_COLORS[row.original.style]"
              variant="subtle"
              size="sm"
              class="shrink-0"
            >
              {{ t(`announcements.styles.${row.original.style}`) }}
            </UBadge>
            <div class="min-w-0">
              <span class="block font-medium break-words whitespace-normal">{{ row.original.title.es }}</span>
              <span
                v-if="row.original.body.es"
                class="line-clamp-2 block text-xs whitespace-normal text-(--ui-text-muted)"
              >{{ row.original.body.es }}</span>
            </div>
          </div>
        </template>
        <template #status-cell="{ row }">
          <UBadge
            :color="STATUS_COLORS[announcementStatus(row.original, now)]"
            variant="subtle"
          >
            {{ t(`announcements.statuses.${announcementStatus(row.original, now)}`) }}
          </UBadge>
        </template>
        <template #dates-cell="{ row }">
          <span class="block whitespace-nowrap text-sm">{{ formatDate(row.original.starts_at, locale) }}</span>
          <span class="block whitespace-nowrap text-xs text-(--ui-text-muted)">{{ t('announcements.until', { date: formatDate(row.original.ends_at, locale) }) }}</span>
        </template>
        <template #audience-cell="{ row }">
          <span class="text-sm">{{ audienceSummary(row.original.target, t, locale) }}</span>
        </template>
        <template #reach-cell="{ row }">
          <span class="block whitespace-nowrap text-sm tabular-nums">{{ t('announcements.seen', { n: formatNumber(row.original.seen, locale) }) }}</span>
          <span
            v-if="row.original.dismissible"
            class="block whitespace-nowrap text-xs text-(--ui-text-muted) tabular-nums"
          >{{ t('announcements.dismissed', { n: formatNumber(row.original.dismissed, locale), rate: dismissRate(row.original) }) }}</span>
          <span
            v-else
            class="block text-xs text-(--ui-text-muted)"
          >{{ t('announcements.notDismissible') }}</span>
        </template>
        <template #actions-cell="{ row }">
          <div class="flex justify-end">
            <UDropdownMenu :items="rowActions(row.original)">
              <UButton
                size="xs"
                color="neutral"
                variant="ghost"
                icon="i-lucide-ellipsis-vertical"
                :aria-label="t('announcements.actions')"
              />
            </UDropdownMenu>
          </div>
        </template>
      </UTable>

      <!-- Create / edit -->
      <UModal
        v-model:open="formOpen"
        :title="editing?.id ? t('announcements.editTitle') : t('announcements.new')"
        :ui="{ content: 'sm:max-w-4xl' }"
      >
        <template #body>
          <form
            id="announcement-form"
            class="grid gap-6 lg:grid-cols-[1fr_20rem]"
            @submit.prevent="save"
          >
            <div class="space-y-5">
              <ControlLocalizedFields
                v-model="form.title"
                :label="t('announcements.title')"
                required
                :maxlength="LOCALIZED_MAX"
              />
              <ControlLocalizedFields
                v-model="form.body"
                :label="t('announcements.body')"
                textarea
              />
              <UFormField :label="t('announcements.style')">
                <URadioGroup
                  v-model="form.style"
                  :items="styleItems"
                  orientation="horizontal"
                />
              </UFormField>

              <div class="grid gap-4 sm:grid-cols-2">
                <UFormField
                  :label="t('announcements.roles')"
                  :help="t('announcements.emptyMeansAll')"
                >
                  <UCheckboxGroup
                    v-model="form.roles"
                    :items="roleItems"
                    orientation="horizontal"
                  />
                </UFormField>
                <UFormField
                  :label="t('announcements.cities')"
                  :help="areaItems.length ? t('announcements.emptyMeansAll') : t('flags.rules.noAreas')"
                >
                  <UCheckboxGroup
                    v-model="form.areas"
                    :items="areaItems"
                    orientation="horizontal"
                  />
                </UFormField>
              </div>

              <div>
                <div class="grid gap-4 sm:grid-cols-2">
                  <UFormField
                    :label="t('announcements.startsAt')"
                    required
                  >
                    <UInput
                      v-model="form.starts_at"
                      type="datetime-local"
                      class="w-full"
                    />
                  </UFormField>
                  <UFormField
                    :label="t('announcements.endsAt')"
                    required
                  >
                    <UInput
                      v-model="form.ends_at"
                      type="datetime-local"
                      :min="form.starts_at || undefined"
                      class="w-full"
                    />
                  </UFormField>
                </div>
                <p class="mt-1 text-xs text-(--ui-text-muted)">
                  {{ t('announcements.timeZone', { zone: timeZone }) }}
                </p>
              </div>

              <USwitch
                v-model="form.dismissible"
                :label="t('announcements.dismissible')"
                :description="t('announcements.dismissibleHelp')"
              />

              <div class="space-y-4 rounded-md border border-(--ui-border) p-4">
                <USwitch
                  v-model="form.hasCta"
                  :label="t('announcements.cta')"
                  :description="t('announcements.ctaHelp')"
                />
                <template v-if="form.hasCta">
                  <ControlLocalizedFields
                    v-model="form.ctaLabel"
                    :label="t('announcements.ctaLabel')"
                    required
                    :maxlength="40"
                  />
                  <UFormField :label="t('announcements.ctaOpens')">
                    <URadioGroup
                      v-model="form.ctaKind"
                      :items="ctaKindItems"
                      orientation="horizontal"
                    />
                  </UFormField>
                  <UFormField
                    v-if="form.ctaKind === 'screen'"
                    :label="t('announcements.ctaScreen')"
                  >
                    <USelect
                      v-model="form.ctaScreen"
                      :items="screenItems"
                      class="w-64"
                    />
                  </UFormField>
                  <UFormField
                    v-else
                    :label="t('announcements.ctaUrl')"
                    :help="t('announcements.ctaUrlHelp')"
                  >
                    <UInput
                      v-model="form.ctaUrl"
                      type="url"
                      :maxlength="CTA_URL_MAX"
                      placeholder="https://"
                      class="w-full"
                    />
                  </UFormField>
                </template>
              </div>

              <UAlert
                v-if="showIssues && issues.length"
                color="error"
                variant="subtle"
                icon="i-lucide-circle-alert"
                :title="t('announcements.fixErrors')"
              >
                <template #description>
                  <ul class="list-disc pl-4">
                    <li
                      v-for="issue in issues"
                      :key="issue"
                    >
                      {{ t(`announcements.errors.${issue}`) }}
                    </li>
                  </ul>
                </template>
              </UAlert>
            </div>

            <div class="space-y-3">
              <ControlAnnouncementPreview :form="form" />
              <p class="text-xs text-(--ui-text-muted)">
                {{ t('announcements.audienceLine', { audience: audienceSummary({ roles: form.roles, areas: form.areas }, t, locale) }) }}
              </p>
            </div>
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
              form="announcement-form"
              :label="editing?.id ? t('common.save') : t('announcements.create')"
              :loading="saving"
            />
          </div>
        </template>
      </UModal>

      <!-- Delete -->
      <UModal
        v-model:open="deleteOpen"
        :title="t('announcements.deleteTitle')"
      >
        <template #body>
          <UAlert
            v-if="deleting"
            color="warning"
            variant="subtle"
            icon="i-lucide-triangle-alert"
            :title="t('announcements.deleteBody', { title: deleting.title.es })"
          />
        </template>
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
              :label="t('announcements.delete')"
              :loading="removing"
              @click="remove"
            />
          </div>
        </template>
      </UModal>
    </template>
  </UDashboardPanel>
</template>
