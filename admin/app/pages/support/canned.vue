<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { CannedAction, CannedInput, CannedResponse, TagCount } from '~/types/api'
import { CANNED_ACTIONS, HELP_LOCALES } from '~/types/api'

definePageMeta({ permission: 'reports.manage' })

const { t, locale } = useI18n()
const { request } = useApi()
const toast = useToast()
const apiError = useApiError()

const localeFilter = ref<'all' | 'es' | 'en'>('all')
const search = ref('')

const { data, status, error, refresh } = await useAsyncData('support-canned', () => request<CannedResponse[]>('/admin/support/canned'))
const { data: tagCounts } = useAsyncData('support-tags-canned', () => request<TagCount[]>('/admin/support/tags').catch(() => [] as TagCount[]), { lazy: true })

const items = computed(() => {
  const q = search.value.trim().toLowerCase()
  return (data.value ?? [])
    .filter(item => localeFilter.value === 'all' || item.locale === localeFilter.value)
    .filter(item => !q || item.title.toLowerCase().includes(q) || item.body.toLowerCase().includes(q) || item.tags.some(tag => tag.includes(q)))
})

const localeTabs = computed(() => [
  { label: t('canned.allLocales'), value: 'all' },
  ...HELP_LOCALES.map(value => ({ label: t(`canned.locales.${value}`), value })),
])
const localeItems = computed(() => HELP_LOCALES.map(value => ({ label: t(`canned.locales.${value}`), value: value as string })))
const actionItems = computed(() => CANNED_ACTIONS.map(value => ({ label: t(`canned.actions.${value}`), value })))
const actionColor: Record<CannedAction, 'neutral' | 'info' | 'success'> = { none: 'neutral', wait_user: 'info', resolve: 'success' }

const columns = computed<TableColumn<CannedResponse>[]>(() => [
  { accessorKey: 'title', header: t('canned.title') },
  { accessorKey: 'locale', header: t('canned.locale') },
  { accessorKey: 'action', header: t('canned.action') },
  { accessorKey: 'uses', header: t('canned.uses') },
  { accessorKey: 'updated_at', header: t('canned.updated') },
  { id: 'actions', header: '' },
])

// ---- Create / edit ------------------------------------------------------------------------------

const editing = ref<CannedResponse | null>(null)
const formOpen = ref(false)
const emptyForm = (): CannedInput => ({ title: '', body: '', locale: 'es', action: 'wait_user', tags: [] })
const form = reactive<CannedInput>(emptyForm())

function openCreate() {
  editing.value = null
  Object.assign(form, emptyForm())
  formOpen.value = true
}
function openEdit(item: CannedResponse) {
  editing.value = item
  Object.assign(form, { title: item.title, body: item.body, locale: item.locale, action: item.action, tags: [...item.tags] })
  formOpen.value = true
}

const valid = computed(() => !!form.title.trim() && form.title.length <= CANNED_TITLE_MAX && !!form.body.trim() && form.body.length <= CANNED_BODY_MAX)
const saving = ref(false)
async function save() {
  if (!valid.value) return
  saving.value = true
  const body: CannedInput = { ...form, title: form.title.trim(), body: form.body.trim(), tags: normalizeTags(form.tags) }
  try {
    if (editing.value) await request(`/admin/support/canned/${editing.value.id}`, { method: 'PATCH', body })
    else await request('/admin/support/canned', { method: 'POST', body })
    toast.add({ title: t(editing.value ? 'canned.toast.updated' : 'canned.toast.created'), color: 'success' })
    formOpen.value = false
    await refresh()
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    saving.value = false
  }
}

function insertPlaceholder(token: string) {
  form.body = form.body ? `${form.body}${form.body.endsWith(' ') ? '' : ' '}${token}` : token
}

// ---- Delete -------------------------------------------------------------------------------------

const deleting = ref<CannedResponse | null>(null)
const deleteOpen = computed({
  get: () => deleting.value !== null,
  set: (open: boolean) => {
    if (!open) deleting.value = null
  },
})
const removing = ref(false)
async function confirmDelete() {
  if (!deleting.value) return
  removing.value = true
  try {
    await request(`/admin/support/canned/${deleting.value.id}`, { method: 'DELETE' })
    toast.add({ title: t('canned.toast.deleted'), color: 'success' })
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
</script>

<template>
  <UDashboardPanel id="support-canned">
    <template #header>
      <UDashboardNavbar :title="t('nav.cannedReplies')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton
            icon="i-lucide-plus"
            :label="t('canned.new')"
            @click="openCreate"
          />
        </template>
      </UDashboardNavbar>
      <UDashboardToolbar>
        <template #left>
          <UTabs
            v-model="localeFilter"
            :items="localeTabs"
            :content="false"
            size="sm"
            variant="link"
          />
        </template>
        <template #right>
          <UInput
            v-model="search"
            icon="i-lucide-search"
            :placeholder="t('canned.search')"
            class="w-72 max-w-full"
          />
        </template>
      </UDashboardToolbar>
    </template>

    <template #body>
      <p class="text-sm text-(--ui-text-muted)">
        {{ t('canned.help') }}
      </p>
      <UAlert
        v-if="error"
        color="error"
        variant="subtle"
        icon="i-lucide-circle-alert"
        :title="apiError(error)"
      />

      <UTable
        :data="items"
        :columns="columns"
        :loading="status === 'pending'"
        :empty="t('canned.empty')"
      >
        <template #title-cell="{ row }">
          <p class="font-medium">
            {{ row.original.title }}
          </p>
          <p
            class="max-w-md truncate text-xs text-(--ui-text-muted)"
            :title="row.original.body"
          >
            {{ row.original.body }}
          </p>
          <div
            v-if="row.original.tags.length"
            class="mt-1 flex flex-wrap gap-1"
          >
            <UBadge
              v-for="tag in row.original.tags"
              :key="tag"
              color="neutral"
              variant="outline"
              size="sm"
            >
              {{ tag }}
            </UBadge>
          </div>
        </template>
        <template #locale-cell="{ row }">
          <UBadge
            color="neutral"
            variant="subtle"
          >
            {{ row.original.locale.toUpperCase() }}
          </UBadge>
        </template>
        <template #action-cell="{ row }">
          <UBadge
            :color="actionColor[row.original.action] ?? 'neutral'"
            variant="subtle"
          >
            {{ t(`canned.actions.${row.original.action}`, row.original.action) }}
          </UBadge>
        </template>
        <template #uses-cell="{ row }">
          {{ formatNumber(row.original.uses, locale) }}
        </template>
        <template #updated_at-cell="{ row }">
          <span class="text-sm whitespace-nowrap text-(--ui-text-muted)">{{ formatDate(row.original.updated_at, locale) }}</span>
        </template>
        <template #actions-cell="{ row }">
          <div class="flex justify-end gap-1">
            <UButton
              icon="i-lucide-pencil"
              size="xs"
              color="neutral"
              variant="ghost"
              :aria-label="t('canned.edit')"
              @click="openEdit(row.original)"
            />
            <UButton
              icon="i-lucide-trash-2"
              size="xs"
              color="error"
              variant="ghost"
              :aria-label="t('canned.delete')"
              @click="deleting = row.original"
            />
          </div>
        </template>
      </UTable>

      <UModal
        v-model:open="formOpen"
        :title="editing ? t('canned.edit') : t('canned.new')"
        :ui="{ content: 'sm:max-w-2xl' }"
      >
        <template #body>
          <form
            id="canned-form"
            class="space-y-4"
            @submit.prevent="save"
          >
            <UFormField
              :label="t('canned.title')"
              required
            >
              <UInput
                v-model="form.title"
                class="w-full"
                :maxlength="CANNED_TITLE_MAX"
                autofocus
              />
            </UFormField>
            <UFormField
              :label="t('canned.body')"
              :help="t('canned.bodyHelp')"
              required
            >
              <UTextarea
                v-model="form.body"
                class="w-full"
                :rows="6"
                autoresize
                :maxlength="CANNED_BODY_MAX"
              />
              <div class="mt-1 flex gap-1">
                <UButton
                  v-for="token in ['{nombre}', '{viaje}']"
                  :key="token"
                  size="xs"
                  color="neutral"
                  variant="soft"
                  :label="token"
                  @click="insertPlaceholder(token)"
                />
              </div>
            </UFormField>
            <div class="grid gap-4 sm:grid-cols-2">
              <UFormField :label="t('canned.locale')">
                <USelect
                  v-model="form.locale"
                  :items="localeItems"
                  class="w-full"
                />
              </UFormField>
              <UFormField
                :label="t('canned.action')"
                :help="t(`canned.actionsHelp.${form.action}`)"
              >
                <USelect
                  v-model="form.action"
                  :items="actionItems"
                  class="w-full"
                />
              </UFormField>
            </div>
            <UFormField
              :label="t('support.tags')"
              :help="t('canned.tagsHelp')"
            >
              <TagEditor
                v-model="form.tags"
                :suggestions="tagCounts"
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
              @click="formOpen = false"
            />
            <UButton
              type="submit"
              form="canned-form"
              :label="t('common.save')"
              :disabled="!valid"
              :loading="saving"
            />
          </div>
        </template>
      </UModal>

      <UModal
        v-model:open="deleteOpen"
        :title="t('canned.deleteTitle')"
        :description="deleting ? t('canned.deleteHelp', { title: deleting.title }) : ''"
      >
        <template #footer>
          <div class="flex w-full justify-end gap-2">
            <UButton
              color="neutral"
              variant="ghost"
              :label="t('common.cancel')"
              @click="deleteOpen = false"
            />
            <UButton
              color="error"
              icon="i-lucide-trash-2"
              :label="t('canned.delete')"
              :loading="removing"
              @click="confirmDelete"
            />
          </div>
        </template>
      </UModal>
    </template>
  </UDashboardPanel>
</template>
