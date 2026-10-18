<script setup lang="ts">
import type { LearningStatus, MarketingLearning, MarketingPlatform } from '~/types/api'
import { LEARNING_STATUSES, MARKETING_PLATFORMS } from '~/types/api'

definePageMeta({ permission: 'marketing.view' })

const { t, locale } = useI18n()
const { request } = useApi()
const auth = useAuth()
const toast = useToast()
const apiError = useApiError()
const canManage = computed(() => auth.can('marketing.manage'))

type Filter = LearningStatus | 'all'
const filter = ref<Filter>('all')
const tabs = computed(() => [
  { label: t('marketing.allStatuses'), value: 'all' },
  ...LEARNING_STATUSES.map(value => ({ label: t(`marketing.learnings.statuses.${value}`), value })),
])
const { data, status, error, refresh } = await useAsyncData(
  'marketing-learnings',
  () => request<MarketingLearning[]>('/admin/marketing/learnings', { query: filter.value === 'all' ? {} : { status: filter.value } }),
  { watch: [filter] },
)

const NONE = '__none__'
const editing = ref<MarketingLearning | null>(null)
const open = ref(false)
const form = reactive({ statement: '', evidence: '', status: 'hipotesis' as LearningStatus, platform: NONE as MarketingPlatform | typeof NONE, pillar: '', format: '' })
const statusItems = computed(() => LEARNING_STATUSES.map(value => ({ label: t(`marketing.learnings.statuses.${value}`), value })))
const platformItems = computed(() => [{ label: t('marketing.allPlatforms'), value: NONE }, ...MARKETING_PLATFORMS.map(p => ({ label: platformLabel[p], value: p }))])

function start(learning: MarketingLearning | null) {
  editing.value = learning
  Object.assign(form, {
    statement: learning?.statement ?? '',
    evidence: learning?.evidence ?? '',
    status: learning?.status ?? 'hipotesis',
    platform: learning?.platform ?? NONE,
    pillar: learning?.pillar ?? '',
    format: learning?.format ?? '',
  })
  open.value = true
}
const saving = ref(false)
async function save() {
  if (!form.statement.trim()) return
  saving.value = true
  const body = {
    statement: form.statement.trim(),
    evidence: form.evidence.trim() || null,
    status: form.status,
    platform: form.platform === NONE ? null : form.platform,
    pillar: form.pillar.trim() || null,
    format: form.format.trim() || null,
  }
  try {
    if (editing.value) await request(`/admin/marketing/learnings/${editing.value.id}`, { method: 'PATCH', body })
    else await request('/admin/marketing/learnings', { method: 'POST', body })
    open.value = false
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
</script>

<template>
  <UDashboardPanel id="marketing-learnings">
    <template #header>
      <UDashboardNavbar :title="t('nav.marketingLearnings')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton
            v-if="canManage"
            icon="i-lucide-plus"
            :label="t('marketing.learnings.new')"
            @click="start(null)"
          />
        </template>
      </UDashboardNavbar>
      <UDashboardToolbar>
        <UTabs
          v-model="filter"
          :items="tabs"
          :content="false"
          size="sm"
          variant="link"
        />
      </UDashboardToolbar>
    </template>

    <template #body>
      <p class="text-sm text-(--ui-text-muted)">
        {{ t('marketing.learnings.help') }}
      </p>
      <UAlert
        v-if="error"
        color="error"
        variant="subtle"
        icon="i-lucide-circle-alert"
        :title="apiError(error)"
      />
      <p
        v-if="status !== 'pending' && !data?.length"
        class="rounded-lg border border-dashed border-(--ui-border) p-6 text-center text-sm text-(--ui-text-muted)"
      >
        {{ t('common.empty') }}
      </p>
      <div class="grid gap-3 lg:grid-cols-2">
        <UCard
          v-for="learning in data ?? []"
          :key="learning.id"
          :ui="{ body: 'space-y-2' }"
        >
          <div class="flex items-start justify-between gap-2">
            <p class="font-medium">
              {{ learning.statement }}
            </p>
            <UBadge
              :color="learningStatusColor[learning.status]"
              variant="subtle"
              class="shrink-0"
            >
              {{ t(`marketing.learnings.statuses.${learning.status}`) }}
            </UBadge>
          </div>
          <p
            v-if="learning.evidence"
            class="text-sm whitespace-pre-line text-(--ui-text-muted)"
          >
            {{ learning.evidence }}
          </p>
          <div class="flex flex-wrap items-center justify-between gap-2 text-xs text-(--ui-text-muted)">
            <span>
              <template v-if="learning.platform">{{ platformLabel[learning.platform] }} · </template>
              <template v-if="learning.pillar">{{ learning.pillar }} · </template>
              <template v-if="learning.format">{{ learning.format }} · </template>
              {{ formatDate(learning.reviewed_at ?? learning.created_at, locale) }}
            </span>
            <UButton
              v-if="canManage"
              size="xs"
              color="neutral"
              variant="ghost"
              icon="i-lucide-pencil"
              :label="t('marketing.edit')"
              @click="start(learning)"
            />
          </div>
        </UCard>
      </div>

      <UModal
        v-model:open="open"
        :title="editing ? t('marketing.learnings.edit') : t('marketing.learnings.new')"
      >
        <template #body>
          <form
            id="learning-form"
            class="space-y-3"
            @submit.prevent="save"
          >
            <UFormField
              :label="t('marketing.learnings.statement')"
              required
            >
              <UTextarea
                v-model="form.statement"
                :rows="2"
                :maxlength="2000"
                class="w-full"
              />
            </UFormField>
            <UFormField
              :label="t('marketing.learnings.evidence')"
              :help="t('marketing.learnings.evidenceHelp')"
            >
              <UTextarea
                v-model="form.evidence"
                :rows="3"
                :maxlength="4000"
                class="w-full"
              />
            </UFormField>
            <div class="grid grid-cols-2 gap-3">
              <UFormField :label="t('marketing.learnings.status')">
                <USelect
                  v-model="form.status"
                  :items="statusItems"
                  class="w-full"
                />
              </UFormField>
              <UFormField :label="t('marketing.performance.platform')">
                <USelect
                  v-model="form.platform"
                  :items="platformItems"
                  class="w-full"
                />
              </UFormField>
              <UFormField :label="t('marketing.fields.pillar')">
                <UInput
                  v-model="form.pillar"
                  :maxlength="40"
                  class="w-full"
                />
              </UFormField>
              <UFormField :label="t('marketing.fields.format')">
                <UInput
                  v-model="form.format"
                  :maxlength="40"
                  class="w-full"
                />
              </UFormField>
            </div>
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
              form="learning-form"
              :label="t('common.save')"
              :loading="saving"
              :disabled="!form.statement.trim()"
            />
          </div>
        </template>
      </UModal>
    </template>
  </UDashboardPanel>
</template>
