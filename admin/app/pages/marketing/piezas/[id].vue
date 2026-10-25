<script setup lang="ts">
import type { MarketingAudience, MarketingContent, MarketingPlatform, MarketingProduction, MarketingStatus } from '~/types/api'
import { MARKETING_AUDIENCES, MARKETING_PLATFORMS, MARKETING_PRODUCTIONS } from '~/types/api'

definePageMeta({ permission: 'marketing.view' })

const { t, locale } = useI18n()
const route = useRoute()
const { request } = useApi()
const auth = useAuth()
const toast = useToast()
const apiError = useApiError()

const id = computed(() => route.params.id as string)
const { data: content, status, error } = await useAsyncData(
  `marketing-content-${id.value}`,
  () => request<MarketingContent>(`/admin/marketing/contents/${id.value}`),
)

const canManage = computed(() => auth.can('marketing.manage'))
const canApprove = computed(() => auth.can('marketing.approve'))
const LOCKED: MarketingStatus[] = ['publicado', 'archivado', 'descartado']
const editable = computed(() => canManage.value && !!content.value && !LOCKED.includes(content.value.status))

function updated(next: MarketingContent) {
  content.value = next
}

// ---- Fields -----------------------------------------------------------------------------------
function fromContent(c: MarketingContent | null | undefined) {
  return {
    title: c?.title ?? '',
    pillar: c?.pillar ?? '',
    format: c?.format ?? '',
    audience: (c?.audience ?? 'ambos') as MarketingAudience,
    production: (c?.production ?? 'ia') as MarketingProduction,
    uses_character: c?.uses_character ?? false,
    scheduled_for: c?.scheduled_for ?? '',
    notes: c?.notes ?? '',
  }
}
const form = reactive(fromContent(content.value))
watch(content, c => Object.assign(form, fromContent(c)))
const audienceItems = computed(() => MARKETING_AUDIENCES.map(value => ({ label: t(`marketing.audiences.${value}`), value })))
const productionItems = computed(() => MARKETING_PRODUCTIONS.map(value => ({ label: t(`marketing.productions.${value}`), value })))

const savingFields = ref(false)
async function saveFields() {
  if (!form.title.trim()) return
  savingFields.value = true
  try {
    const wasApproved = content.value?.status === 'aprobado'
    content.value = await request<MarketingContent>(`/admin/marketing/contents/${id.value}`, {
      method: 'PATCH',
      body: {
        title: form.title.trim(),
        pillar: form.pillar.trim() || null,
        format: form.format.trim() || null,
        audience: form.audience,
        production: form.production,
        uses_character: form.uses_character,
        scheduled_for: form.scheduled_for || null,
        notes: form.notes.trim() || null,
      },
    })
    toast.add({ title: wasApproved ? t('marketing.backToApproval') : t('common.saved'), color: wasApproved ? 'warning' : 'success' })
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    savingFields.value = false
  }
}

// ---- Status -----------------------------------------------------------------------------------
const moving = ref<MarketingStatus | null>(null)
// Discarding locks the piece (no edits, no uploads) until it goes back to "idea": confirm first.
const discardOpen = ref(false)
function pick(next: MarketingStatus) {
  if (next === 'descartado') discardOpen.value = true
  else move(next)
}

async function move(next: MarketingStatus) {
  discardOpen.value = false
  moving.value = next
  try {
    content.value = await request<MarketingContent>(`/admin/marketing/contents/${id.value}/status`, { method: 'POST', body: { status: next } })
    toast.add({ title: t('marketing.statusChanged', { status: t(`marketing.statuses.${next}`) }), color: 'success' })
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    moving.value = null
  }
}

const approving = ref(false)
async function approve() {
  approving.value = true
  try {
    content.value = await request<MarketingContent>(`/admin/marketing/contents/${id.value}/approve`, { method: 'POST' })
    toast.add({ title: t('marketing.approved'), color: 'success' })
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    approving.value = false
  }
}
const changesOpen = ref(false)
const changesNote = ref('')
async function requestChanges() {
  if (!changesNote.value.trim()) return
  try {
    content.value = await request<MarketingContent>(`/admin/marketing/contents/${id.value}/request-changes`, { method: 'POST', body: { note: changesNote.value.trim() } })
    changesOpen.value = false
    changesNote.value = ''
    toast.add({ title: t('marketing.changesRequested'), color: 'success' })
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
}

// ---- New variant ------------------------------------------------------------------------------
const freePlatforms = computed(() => MARKETING_PLATFORMS.filter(p => !content.value?.variants.some(v => v.platform === p)))
const newPlatform = ref<MarketingPlatform | undefined>(undefined)
const platformItems = computed(() => freePlatforms.value.map(p => ({ label: platformLabel[p], value: p })))
async function addVariant() {
  if (!newPlatform.value) return
  try {
    content.value = await request<MarketingContent>(`/admin/marketing/contents/${id.value}/variants`, {
      method: 'POST',
      body: { platform: newPlatform.value, account: '@kuulis' },
    })
    newPlatform.value = undefined
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
}

// ---- Layout -----------------------------------------------------------------------------------
type Section = 'guion' | 'redes' | 'archivos' | 'datos'
const SECTIONS: Section[] = ['guion', 'redes', 'archivos', 'datos']
const router = useRouter()
const section = ref<Section>(SECTIONS.includes(route.query.tab as Section) ? route.query.tab as Section : 'guion')
watch(section, value => router.replace({ query: value === 'guion' ? {} : { tab: value } }))
const sectionItems = computed(() => [
  { label: t('marketing.script'), value: 'guion', icon: 'i-lucide-scroll-text' },
  { label: t('marketing.variants'), value: 'redes', icon: 'i-lucide-share-2', badge: content.value?.variants.length || undefined },
  { label: t('marketing.assets.title'), value: 'archivos', icon: 'i-lucide-paperclip', badge: content.value?.assets.length || undefined },
  { label: t('marketing.details'), value: 'datos', icon: 'i-lucide-settings-2' },
])
const shown = ref<string | null>(null)
function show(assetId: string) {
  shown.value = assetId
  if (window.matchMedia('(max-width: 1279px)').matches) window.scrollTo({ top: 0, behavior: 'smooth' })
}
</script>

<template>
  <UDashboardPanel id="marketing-content">
    <template #header>
      <UDashboardNavbar :title="content ? content.code : t('nav.marketingCalendar')">
        <template #leading>
          <UButton
            icon="i-lucide-arrow-left"
            color="neutral"
            variant="ghost"
            to="/marketing"
            :aria-label="t('common.back')"
          />
        </template>
        <template #right>
          <UBadge
            v-if="content"
            :color="marketingStatusColor[content.status]"
            variant="subtle"
            size="lg"
          >
            {{ t(`marketing.statuses.${content.status}`) }}
          </UBadge>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <UAlert
        v-if="error"
        color="error"
        variant="subtle"
        icon="i-lucide-circle-alert"
        :title="apiError(error)"
      />
      <div
        v-else-if="status === 'pending' && !content"
        class="space-y-3"
      >
        <USkeleton class="h-10 w-1/2" />
        <USkeleton class="h-48 w-full" />
      </div>

      <template v-if="content">
        <div class="space-y-1">
          <h1 class="text-xl font-semibold">
            {{ content.title }}
          </h1>
          <p class="text-sm text-(--ui-text-muted)">
            <template v-if="content.created_by_agent">
              {{ t('marketing.byAgent', { agent: content.created_by_agent }) }} ·
            </template>
            {{ t('marketing.createdAt', { date: formatDate(content.created_at, locale) }) }}
            <template v-if="content.approved_at">
              · {{ t('marketing.approvedAt', { date: formatDate(content.approved_at, locale) }) }}
            </template>
          </p>
        </div>

        <UAlert
          v-if="content.review_note"
          color="warning"
          variant="subtle"
          icon="i-lucide-message-square-warning"
          :title="t('marketing.reviewNote')"
          :description="content.review_note"
        />

        <UAlert
          v-if="content.status === 'descartado' || content.status === 'archivado'"
          color="neutral"
          variant="subtle"
          icon="i-lucide-lock"
          :title="t(`marketing.locked.${content.status}`)"
          :description="t(content.allowed_statuses.includes('idea') ? 'marketing.locked.reopenHelp' : 'marketing.locked.help')"
          :actions="canManage && content.allowed_statuses.includes('idea')
            ? [{ label: t('marketing.moveTo.idea'), icon: 'i-lucide-undo-2', loading: moving === 'idea', onClick: () => move('idea') }]
            : []"
        />

        <!-- Actions -->
        <div class="flex flex-wrap gap-2">
          <template v-if="canApprove && content.status === 'producido'">
            <UButton
              icon="i-lucide-badge-check"
              color="success"
              :label="t('marketing.approve')"
              :loading="approving"
              @click="approve"
            />
            <UButton
              icon="i-lucide-undo-2"
              color="warning"
              variant="outline"
              :label="t('marketing.requestChanges')"
              @click="changesOpen = true"
            />
          </template>
          <template v-if="canManage">
            <UButton
              v-for="next in content.allowed_statuses"
              :key="next"
              :color="next === 'descartado' ? 'error' : 'neutral'"
              variant="outline"
              :loading="moving === next"
              :label="t(`marketing.moveTo.${next}`)"
              @click="pick(next)"
            />
          </template>
        </div>

        <div class="grid grid-cols-1 items-start gap-6 xl:grid-cols-[minmax(18rem,24rem)_minmax(0,1fr)]">
          <div class="min-w-0 xl:sticky xl:top-4">
            <MarketingMediaViewer
              v-model="shown"
              :assets="content.assets"
            />
          </div>

          <div class="min-w-0 space-y-4">
            <UTabs
              v-model="section"
              :items="sectionItems"
              :content="false"
              variant="link"
              class="overflow-x-auto"
            />

            <MarketingScriptView
              v-if="section === 'guion'"
              :script="content.script"
              :notes="content.notes"
            />

            <section
              v-else-if="section === 'redes'"
              class="space-y-3"
            >
              <div class="flex flex-wrap items-center justify-between gap-2">
                <h2 class="font-semibold">
                  {{ t('marketing.variants') }}
                </h2>
                <div
                  v-if="editable && freePlatforms.length"
                  class="flex gap-2"
                >
                  <USelect
                    v-model="newPlatform"
                    :items="platformItems"
                    :placeholder="t('marketing.variant.choosePlatform')"
                    class="w-44"
                  />
                  <UButton
                    icon="i-lucide-plus"
                    :label="t('marketing.variant.add')"
                    :disabled="!newPlatform"
                    @click="addVariant"
                  />
                </div>
              </div>
              <p
                v-if="!content.variants.length"
                class="rounded-lg border border-dashed border-(--ui-border) p-6 text-center text-sm text-(--ui-text-muted)"
              >
                {{ t('marketing.variant.none') }}
              </p>
              <MarketingVariantEditor
                v-for="variant in content.variants"
                :key="variant.id"
                :content-id="content.id"
                :variant="variant"
                :assets="content.assets"
                :editable="editable"
                :can-manage="canManage"
                @updated="updated"
              />
            </section>

            <MarketingAssetsCard
              v-else-if="section === 'archivos'"
              :content-id="content.id"
              :assets="content.assets"
              :can-upload="editable"
              @updated="updated"
              @show="show"
            />

            <UCard v-else>
              <template #header>
                <h3 class="font-semibold">
                  {{ t('marketing.details') }}
                </h3>
              </template>
              <form
                class="space-y-3"
                @submit.prevent="saveFields"
              >
                <UFormField
                  :label="t('marketing.fields.title')"
                  required
                >
                  <UInput
                    v-model="form.title"
                    :maxlength="120"
                    :disabled="!editable"
                    class="w-full"
                  />
                </UFormField>
                <div class="grid grid-cols-2 gap-3">
                  <UFormField :label="t('marketing.fields.pillar')">
                    <UInput
                      v-model="form.pillar"
                      :maxlength="40"
                      :disabled="!editable"
                      class="w-full"
                    />
                  </UFormField>
                  <UFormField :label="t('marketing.fields.format')">
                    <UInput
                      v-model="form.format"
                      :maxlength="40"
                      :disabled="!editable"
                      class="w-full"
                    />
                  </UFormField>
                  <UFormField :label="t('marketing.fields.audience')">
                    <USelect
                      v-model="form.audience"
                      :items="audienceItems"
                      :disabled="!editable"
                      class="w-full"
                    />
                  </UFormField>
                  <UFormField :label="t('marketing.fields.production')">
                    <USelect
                      v-model="form.production"
                      :items="productionItems"
                      :disabled="!editable"
                      class="w-full"
                    />
                  </UFormField>
                </div>
                <UFormField :label="t('marketing.fields.scheduledFor')">
                  <UInput
                    v-model="form.scheduled_for"
                    type="date"
                    :disabled="!editable"
                    class="w-full"
                  />
                </UFormField>
                <USwitch
                  v-model="form.uses_character"
                  :label="t('marketing.fields.usesCharacter')"
                  :disabled="!editable"
                />
                <UFormField :label="t('marketing.fields.notes')">
                  <UTextarea
                    v-model="form.notes"
                    :rows="3"
                    :maxlength="4000"
                    :disabled="!editable"
                    class="w-full"
                  />
                </UFormField>
                <div
                  v-if="editable"
                  class="flex justify-end"
                >
                  <UButton
                    type="submit"
                    :label="t('common.save')"
                    :loading="savingFields"
                    :disabled="!form.title.trim()"
                  />
                </div>
              </form>
            </UCard>
          </div>
        </div>
      </template>

      <UModal
        v-model:open="changesOpen"
        :title="t('marketing.requestChanges')"
        :description="t('marketing.requestChangesHelp')"
      >
        <template #body>
          <UTextarea
            v-model="changesNote"
            :rows="4"
            :maxlength="2000"
            class="w-full"
            autofocus
          />
        </template>
        <template #footer>
          <div class="flex w-full justify-end gap-2">
            <UButton
              color="neutral"
              variant="ghost"
              :label="t('common.cancel')"
              @click="changesOpen = false"
            />
            <UButton
              color="warning"
              :label="t('marketing.sendChanges')"
              :disabled="!changesNote.trim()"
              @click="requestChanges"
            />
          </div>
        </template>
      </UModal>

      <UModal
        v-model:open="discardOpen"
        :title="t('marketing.discardTitle')"
        :description="t('marketing.discardHelp')"
      >
        <template #footer>
          <div class="flex w-full justify-end gap-2">
            <UButton
              color="neutral"
              variant="ghost"
              :label="t('common.cancel')"
              @click="discardOpen = false"
            />
            <UButton
              color="error"
              :label="t('marketing.moveTo.descartado')"
              :loading="moving === 'descartado'"
              @click="move('descartado')"
            />
          </div>
        </template>
      </UModal>
    </template>
  </UDashboardPanel>
</template>
