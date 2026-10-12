<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { AppStatus, AppStatusRead, AreaPause } from '~/types/api'
import type { MaintenanceForm, PauseForm } from '~/utils/control'

definePageMeta({ permission: 'app_status.view' })

const { t, locale } = useI18n()
const { request } = useApi()
const apiError = useApiError()
const toast = useToast()
const auth = useAuth()
const canManage = computed(() => auth.can('app_status.manage'))

const { data: status, status: loadStatus, error } = await useAsyncData('app-status', () => request<AppStatusRead>('/admin/app/status'))

const areas = computed(() => status.value?.areas ?? [])
const saved = computed(() => status.value?.maintenance ?? null)
const pauses = computed(() => status.value?.area_pauses ?? [])
const maintenanceOn = computed(() => !!saved.value?.enabled)

// ---- Maintenance ------------------------------------------------------------------------------------

const form = reactive<MaintenanceForm>(maintenanceFormFrom(null))
function loadForm() {
  Object.assign(form, maintenanceFormFrom(saved.value))
}
watch(saved, loadForm, { immediate: true })

const areaItems = computed(() => {
  const names = [...areas.value, ...form.areas.filter(a => !areas.value.includes(a))]
  return names.map(name => ({ label: name, value: name }))
})
const scopeItems = computed(() => [
  { label: t('appStatus.scopeAll'), value: 'all' },
  { label: t('appStatus.scopeAreas'), value: 'areas', disabled: !areaItems.value.length },
])
const maintenanceIssues = computed(() => validateMaintenance(form))
const maintenanceDirty = computed(() =>
  JSON.stringify(maintenancePayload(form, true, areas.value))
  !== JSON.stringify(maintenancePayload(maintenanceFormFrom(saved.value), true, areas.value)),
)
const savedWhere = computed(() =>
  saved.value?.areas.length ? listOf(saved.value.areas, locale.value) : t('appStatus.everywhere'),
)
const localMessage = (m: { es: string, en: string }) => (locale.value === 'en' && m.en ? m.en : m.es)

// ---- Confirmation (every change asks first) -------------------------------------------------------

type Action = 'maintenanceOn' | 'maintenanceUpdate' | 'maintenanceOff' | 'pauseAdd' | 'pauseUpdate' | 'pauseRemove'
const confirming = ref<{ action: Action, body: AppStatus, params: Record<string, string> } | null>(null)
const confirmOpen = computed({
  get: () => confirming.value !== null,
  set: (v) => {
    if (!v) confirming.value = null
  },
})
const DANGER: Action[] = ['maintenanceOn', 'pauseAdd']

/** The other section keeps what is saved: unsaved edits there are never sent along. */
function askMaintenance(action: 'maintenanceOn' | 'maintenanceUpdate' | 'maintenanceOff') {
  if (!saved.value) return
  if (action !== 'maintenanceOff' && maintenanceIssues.value.length) {
    toast.add({ title: t('appStatus.fixErrors'), color: 'error' })
    return
  }
  const maintenance = action === 'maintenanceOff'
    ? { ...saved.value, enabled: false }
    : maintenancePayload(form, true, areas.value)
  const where = maintenance.areas.length ? listOf(maintenance.areas, locale.value) : t('appStatus.everywhere')
  confirming.value = { action, body: { maintenance, area_pauses: pauses.value }, params: { where } }
}

const applying = ref(false)
async function apply() {
  if (!confirming.value) return
  applying.value = true
  try {
    status.value = await request<AppStatusRead>('/admin/app/status', { method: 'PUT', body: confirming.value.body })
    toast.add({ title: t(`appStatus.done.${confirming.value.action}`, confirming.value.params), color: 'success' })
    confirming.value = null
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    applying.value = false
  }
}

// ---- City pauses ------------------------------------------------------------------------------------

const pauseColumns = computed<TableColumn<AreaPause>[]>(() => [
  { accessorKey: 'area', header: t('appStatus.city') },
  { accessorKey: 'message', header: t('appStatus.message') },
  { accessorKey: 'eta', header: t('appStatus.eta') },
  ...(canManage.value ? [{ id: 'actions', header: '' }] : []),
])

const editingPause = ref<{ previous: string | null } | null>(null)
const pauseOpen = computed({
  get: () => editingPause.value !== null,
  set: (v) => {
    if (!v) editingPause.value = null
  },
})
const pauseForm = reactive<PauseForm>(pauseFormFrom(null))
const pauseShowIssues = ref(false)
const pausedAreas = computed(() => pauses.value.map(p => p.area))
const freeAreas = computed(() => areas.value.filter(a => !pausedAreas.value.includes(a)))
const pauseAreaItems = computed(() => {
  const previous = editingPause.value?.previous
  const names = previous ? [previous, ...freeAreas.value.filter(a => a !== previous)] : freeAreas.value
  return names.map(name => ({ label: name, value: name }))
})
const pauseIssues = computed(() =>
  validatePause(pauseForm, pausedAreas.value.filter(a => a !== editingPause.value?.previous)),
)

function startPause(pause: AreaPause | null) {
  Object.assign(pauseForm, pauseFormFrom(pause, freeAreas.value[0] ?? ''))
  pauseShowIssues.value = false
  editingPause.value = { previous: pause?.area ?? null }
}
function askPause() {
  if (!editingPause.value || !saved.value) return
  if (pauseIssues.value.length) {
    pauseShowIssues.value = true
    return
  }
  const previous = editingPause.value.previous
  const pause = pausePayload(pauseForm)
  confirming.value = {
    action: previous ? 'pauseUpdate' : 'pauseAdd',
    body: { maintenance: saved.value, area_pauses: upsertPause(pauses.value, pause, previous) },
    params: { area: pause.area },
  }
  editingPause.value = null
}
function askRemovePause(pause: AreaPause) {
  if (!saved.value) return
  confirming.value = {
    action: 'pauseRemove',
    body: { maintenance: saved.value, area_pauses: pauses.value.filter(p => p.area !== pause.area) },
    params: { area: pause.area },
  }
}
</script>

<template>
  <UDashboardPanel id="app-status">
    <template #header>
      <UDashboardNavbar :title="t('nav.appStatus')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <p class="max-w-3xl text-sm text-(--ui-text-muted)">
        {{ t('appStatus.help') }}
      </p>
      <UAlert
        v-if="error && !status"
        color="error"
        variant="subtle"
        icon="i-lucide-circle-alert"
        :title="apiError(error)"
      />
      <USkeleton
        v-else-if="loadStatus === 'pending' && !status"
        class="h-96 max-w-3xl"
      />

      <div
        v-if="status && saved"
        class="grid max-w-3xl gap-6"
      >
        <UAlert
          v-if="!canManage"
          color="neutral"
          variant="subtle"
          icon="i-lucide-lock"
          :title="t('appStatus.readOnly')"
        />

        <!-- What the app is doing right now -->
        <UAlert
          v-if="maintenanceOn"
          color="error"
          variant="solid"
          icon="i-lucide-construction"
          :title="t('appStatus.onTitle', { where: savedWhere })"
          :ui="{ title: 'text-base font-semibold' }"
        >
          <template #description>
            <p>{{ t('appStatus.onBody') }}</p>
            <p
              v-if="saved.message.es"
              class="mt-2 italic"
            >
              «{{ localMessage(saved.message) }}»
            </p>
            <p
              v-if="saved.eta"
              class="mt-1"
            >
              {{ t('appStatus.etaLine', { date: formatDate(saved.eta, locale) }) }}
            </p>
          </template>
        </UAlert>
        <UAlert
          v-else-if="pauses.length"
          color="warning"
          variant="subtle"
          icon="i-lucide-cloud-rain"
          :title="t('appStatus.pausedTitle', { areas: listOf(pausedAreas, locale) })"
        />
        <UAlert
          v-else
          color="success"
          variant="subtle"
          icon="i-lucide-circle-check"
          :title="t('appStatus.allGood')"
        />

        <!-- Maintenance -->
        <UCard>
          <template #header>
            <div class="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h2 class="font-semibold">
                  {{ t('appStatus.maintenance') }}
                </h2>
                <p class="text-sm text-(--ui-text-muted)">
                  {{ t('appStatus.maintenanceHelp') }}
                </p>
              </div>
              <UBadge
                :color="maintenanceOn ? 'error' : 'neutral'"
                :variant="maintenanceOn ? 'solid' : 'subtle'"
                size="lg"
              >
                {{ maintenanceOn ? t('appStatus.on') : t('appStatus.off') }}
              </UBadge>
            </div>
          </template>

          <div class="space-y-5">
            <UFormField :label="t('appStatus.scope')">
              <URadioGroup
                v-model="form.scope"
                :items="scopeItems"
                orientation="horizontal"
                :disabled="!canManage"
              />
            </UFormField>
            <UFormField
              v-if="form.scope === 'areas'"
              :label="t('appStatus.cities')"
            >
              <UCheckboxGroup
                v-model="form.areas"
                :items="areaItems"
                orientation="horizontal"
                :disabled="!canManage"
              />
            </UFormField>
            <ControlLocalizedFields
              v-model="form.message"
              :label="t('appStatus.message')"
              :help="t('appStatus.messageHelp')"
              textarea
              required
              :disabled="!canManage"
            />
            <UFormField
              :label="t('appStatus.eta')"
              :help="t('appStatus.etaHelp')"
            >
              <UInput
                v-model="form.eta"
                type="datetime-local"
                class="w-64"
                :disabled="!canManage"
              />
            </UFormField>

            <UAlert
              v-if="canManage && maintenanceIssues.length && (maintenanceDirty || !maintenanceOn)"
              color="neutral"
              variant="subtle"
              icon="i-lucide-info"
              :title="t('appStatus.fixErrors')"
            >
              <template #description>
                <ul class="list-disc pl-4">
                  <li
                    v-for="issue in maintenanceIssues"
                    :key="issue"
                  >
                    {{ t(`appStatus.errors.${issue}`) }}
                  </li>
                </ul>
              </template>
            </UAlert>

            <div
              v-if="canManage"
              class="flex flex-wrap gap-2"
            >
              <template v-if="!maintenanceOn">
                <UButton
                  color="error"
                  icon="i-lucide-power"
                  :label="t('appStatus.turnOn')"
                  :disabled="maintenanceIssues.length > 0"
                  @click="askMaintenance('maintenanceOn')"
                />
              </template>
              <template v-else>
                <UButton
                  icon="i-lucide-save"
                  :label="t('appStatus.saveChanges')"
                  :disabled="!maintenanceDirty || maintenanceIssues.length > 0"
                  @click="askMaintenance('maintenanceUpdate')"
                />
                <UButton
                  color="success"
                  icon="i-lucide-power-off"
                  :label="t('appStatus.turnOff')"
                  @click="askMaintenance('maintenanceOff')"
                />
              </template>
              <UButton
                color="neutral"
                variant="ghost"
                :label="t('common.discard')"
                :disabled="!maintenanceDirty"
                @click="loadForm"
              />
            </div>
          </div>
        </UCard>

        <!-- City pauses -->
        <UCard>
          <template #header>
            <div class="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h2 class="font-semibold">
                  {{ t('appStatus.pauses') }}
                </h2>
                <p class="text-sm text-(--ui-text-muted)">
                  {{ t('appStatus.pausesHelp') }}
                </p>
              </div>
              <UButton
                v-if="canManage"
                icon="i-lucide-pause"
                color="warning"
                :label="t('appStatus.addPause')"
                :disabled="!freeAreas.length"
                @click="startPause(null)"
              />
            </div>
          </template>
          <UTable
            :data="pauses"
            :columns="pauseColumns"
            :empty="t('appStatus.noPauses')"
          >
            <template #area-cell="{ row }">
              <UBadge
                color="warning"
                variant="subtle"
              >
                {{ row.original.area }}
              </UBadge>
            </template>
            <template #message-cell="{ row }">
              <p class="max-w-sm whitespace-pre-line text-sm">
                {{ row.original.message.es || '—' }}
              </p>
              <p
                v-if="row.original.message.en"
                class="max-w-sm whitespace-pre-line text-xs text-(--ui-text-muted)"
              >
                {{ row.original.message.en }}
              </p>
            </template>
            <template #eta-cell="{ row }">
              <span class="whitespace-nowrap">{{ row.original.eta ? formatDate(row.original.eta, locale) : t('appStatus.noEta') }}</span>
            </template>
            <template #actions-cell="{ row }">
              <div class="flex justify-end gap-1">
                <UButton
                  size="xs"
                  color="neutral"
                  variant="ghost"
                  icon="i-lucide-pencil"
                  :aria-label="t('appStatus.editPause')"
                  @click="startPause(row.original)"
                />
                <UButton
                  size="xs"
                  color="error"
                  variant="ghost"
                  icon="i-lucide-play"
                  :label="t('appStatus.removePause')"
                  @click="askRemovePause(row.original)"
                />
              </div>
            </template>
          </UTable>
        </UCard>
      </div>

      <!-- Pause a city -->
      <UModal
        v-model:open="pauseOpen"
        :title="editingPause?.previous ? t('appStatus.editPauseTitle', { area: editingPause.previous }) : t('appStatus.addPause')"
        :description="t('appStatus.pauseModalHelp')"
        :ui="{ content: 'sm:max-w-2xl' }"
      >
        <template #body>
          <form
            id="pause-form"
            class="space-y-4"
            @submit.prevent="askPause"
          >
            <UFormField
              :label="t('appStatus.city')"
              required
            >
              <USelect
                v-model="pauseForm.area"
                :items="pauseAreaItems"
                class="w-56"
              />
            </UFormField>
            <ControlLocalizedFields
              v-model="pauseForm.message"
              :label="t('appStatus.message')"
              :help="t('appStatus.pauseMessageHelp')"
              textarea
              required
            />
            <UFormField
              :label="t('appStatus.eta')"
              :help="t('appStatus.etaHelp')"
            >
              <UInput
                v-model="pauseForm.eta"
                type="datetime-local"
                class="w-64"
              />
            </UFormField>
            <UAlert
              v-if="pauseShowIssues && pauseIssues.length"
              color="error"
              variant="subtle"
              icon="i-lucide-circle-alert"
              :title="t('appStatus.fixErrors')"
            >
              <template #description>
                <ul class="list-disc pl-4">
                  <li
                    v-for="issue in pauseIssues"
                    :key="issue"
                  >
                    {{ t(`appStatus.errors.${issue}`) }}
                  </li>
                </ul>
              </template>
            </UAlert>
          </form>
        </template>
        <template #footer>
          <div class="flex w-full justify-end gap-2">
            <UButton
              color="neutral"
              variant="ghost"
              :label="t('common.cancel')"
              @click="editingPause = null"
            />
            <UButton
              type="submit"
              form="pause-form"
              color="warning"
              :label="t('appStatus.continue')"
            />
          </div>
        </template>
      </UModal>

      <!-- Confirm a change -->
      <UModal
        v-model:open="confirmOpen"
        :title="confirming ? t(`appStatus.confirm.${confirming.action}.title`, confirming.params) : ''"
      >
        <template #body>
          <UAlert
            v-if="confirming"
            :color="DANGER.includes(confirming.action) ? 'error' : 'warning'"
            variant="subtle"
            icon="i-lucide-triangle-alert"
            :title="t(`appStatus.confirm.${confirming.action}.body`, confirming.params)"
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
              :color="confirming && DANGER.includes(confirming.action) ? 'error' : 'primary'"
              :label="t('common.confirm')"
              :loading="applying"
              @click="apply"
            />
          </div>
        </template>
      </UModal>
    </template>
  </UDashboardPanel>
</template>
