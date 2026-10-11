<script setup lang="ts">
import type { LegalDocument, LegalKind, LegalVersion } from '~/types/api'
import { LEGAL_KINDS } from '~/types/api'

definePageMeta({ roles: ['admin'] })

const { t, locale } = useI18n()
const { request } = useApi()
const apiError = useApiError()
const toast = useToast()

const { data: versions, status, error, refresh } = await useAsyncData('legal', () => request<LegalVersion[]>('/admin/legal'))

interface KindRow { kind: LegalKind, current: LegalVersion | null, history: LegalVersion[] }
const rows = computed<KindRow[]>(() =>
  LEGAL_KINDS.map((kind) => {
    // One row per version (the Spanish one; both languages are published together).
    const history = (versions.value ?? []).filter(v => v.kind === kind && v.locale === 'es')
    return { kind, current: history[0] ?? null, history }
  }),
)
const expanded = ref<LegalKind | null>(null)

// ---- Read a version ---------------------------------------------------------------------------
const reading = ref<LegalDocument[] | null>(null)
const readLocale = ref<'es' | 'en'>('es')
const readOpen = computed({
  get: () => reading.value !== null,
  set: (v) => {
    if (!v) reading.value = null
  },
})
const readDoc = computed(() => reading.value?.find(d => d.locale === readLocale.value) ?? reading.value?.[0])
async function read(kind: LegalKind, version: number) {
  try {
    reading.value = await request<LegalDocument[]>(`/admin/legal/${kind}/${version}`)
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
}

// ---- Publish ----------------------------------------------------------------------------------
const publishing = ref<LegalKind | null>(null)
const publishOpen = computed({
  get: () => publishing.value !== null,
  set: (v) => {
    if (!v) publishing.value = null
  },
})
const form = reactive({
  es: { title: '', body_md: '' },
  en: { title: '', body_md: '' },
  summary: '',
  requires_reacceptance: false,
})
const saving = ref(false)
async function startPublish(row: KindRow) {
  try {
    const docs = row.current ? await request<LegalDocument[]>(`/admin/legal/${row.kind}/${row.current.version}`) : []
    for (const loc of ['es', 'en'] as const) {
      const doc = docs.find(d => d.locale === loc)
      form[loc].title = doc?.title ?? ''
      form[loc].body_md = doc?.body_md ?? ''
    }
    form.summary = ''
    form.requires_reacceptance = false
    publishing.value = row.kind
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
}
const canPublish = computed(() =>
  (['es', 'en'] as const).every(loc => form[loc].title.trim() && form[loc].body_md.trim().length >= 20),
)
async function publish() {
  if (!publishing.value || !canPublish.value) return
  saving.value = true
  try {
    const [doc] = await request<LegalDocument[]>(`/admin/legal/${publishing.value}`, { method: 'POST', body: { ...form } })
    toast.add({ title: t('legal.published', { version: doc?.version }), color: 'success' })
    publishing.value = null
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
  <UDashboardPanel id="legal">
    <template #header>
      <UDashboardNavbar :title="t('nav.legal')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <p class="text-sm text-(--ui-text-muted)">
        {{ t('legal.help') }}
      </p>
      <UAlert
        v-if="error"
        color="error"
        variant="subtle"
        icon="i-lucide-circle-alert"
        :title="apiError(error)"
      />
      <div
        v-if="status === 'pending'"
        class="text-sm text-(--ui-text-muted)"
      >
        …
      </div>
      <div class="grid gap-4">
        <UCard
          v-for="row in rows"
          :key="row.kind"
        >
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div class="space-y-1">
              <h2 class="font-semibold">
                {{ t(`legal.kinds.${row.kind}`) }}
              </h2>
              <p
                v-if="row.current"
                class="text-sm text-(--ui-text-muted)"
              >
                {{ t('legal.current', { version: row.current.version, date: formatDate(row.current.published_at, locale) }) }}
              </p>
              <p
                v-else
                class="text-sm text-(--ui-text-muted)"
              >
                {{ t('legal.none') }}
              </p>
              <p class="text-xs text-(--ui-text-muted)">
                {{ t(`legal.who.${row.kind}`) }}
              </p>
            </div>
            <div class="flex gap-2">
              <UButton
                v-if="row.current"
                color="neutral"
                variant="outline"
                icon="i-lucide-eye"
                :label="t('legal.read')"
                @click="read(row.kind, row.current.version)"
              />
              <UButton
                icon="i-lucide-upload"
                :label="t('legal.publish')"
                @click="startPublish(row)"
              />
            </div>
          </div>
          <div
            v-if="row.history.length > 1"
            class="mt-3"
          >
            <UButton
              size="xs"
              color="neutral"
              variant="ghost"
              :icon="expanded === row.kind ? 'i-lucide-chevron-up' : 'i-lucide-chevron-down'"
              :label="t('legal.history', { n: row.history.length })"
              @click="expanded = expanded === row.kind ? null : row.kind"
            />
            <ul
              v-if="expanded === row.kind"
              class="mt-2 divide-y divide-(--ui-border) text-sm"
            >
              <li
                v-for="v in row.history"
                :key="v.version"
                class="flex flex-wrap items-center justify-between gap-2 py-2"
              >
                <div>
                  <span class="font-medium">v{{ v.version }}</span>
                  <span class="text-(--ui-text-muted)"> · {{ formatDate(v.published_at, locale) }}</span>
                  <UBadge
                    v-if="v.requires_reacceptance"
                    class="ml-2"
                    size="sm"
                    color="warning"
                    variant="subtle"
                  >
                    {{ t('legal.reaccept') }}
                  </UBadge>
                  <p
                    v-if="v.summary"
                    class="text-xs text-(--ui-text-muted)"
                  >
                    {{ v.summary }}
                  </p>
                </div>
                <UButton
                  size="xs"
                  color="neutral"
                  variant="ghost"
                  icon="i-lucide-eye"
                  :aria-label="t('legal.read')"
                  @click="read(row.kind, v.version)"
                />
              </li>
            </ul>
          </div>
        </UCard>
      </div>

      <UModal
        v-model:open="readOpen"
        :title="readDoc ? `${readDoc.title} · v${readDoc.version}` : ''"
        :ui="{ content: 'max-w-3xl' }"
      >
        <template #body>
          <div class="space-y-3">
            <UTabs
              v-model="readLocale"
              :items="[{ label: 'Español', value: 'es' }, { label: 'English', value: 'en' }]"
              :content="false"
            />
            <pre class="max-h-[60vh] overflow-auto whitespace-pre-wrap font-sans text-sm">{{ readDoc?.body_md }}</pre>
          </div>
        </template>
      </UModal>

      <UModal
        v-model:open="publishOpen"
        :title="publishing ? t('legal.publishTitle', { kind: t(`legal.kinds.${publishing}`) }) : ''"
        :description="t('legal.publishHelp')"
        :ui="{ content: 'max-w-4xl' }"
      >
        <template #body>
          <form
            id="legal-form"
            class="space-y-4"
            @submit.prevent="publish"
          >
            <div class="grid gap-4 lg:grid-cols-2">
              <div
                v-for="loc in (['es', 'en'] as const)"
                :key="loc"
                class="space-y-2"
              >
                <UFormField :label="t(`legal.title_${loc}`)">
                  <UInput
                    v-model="form[loc].title"
                    class="w-full"
                    :maxlength="120"
                  />
                </UFormField>
                <UFormField :label="t(`legal.body_${loc}`)">
                  <UTextarea
                    v-model="form[loc].body_md"
                    class="w-full font-mono"
                    :rows="16"
                  />
                </UFormField>
              </div>
            </div>
            <UFormField
              :label="t('legal.summary')"
              :help="t('legal.summaryHelp')"
            >
              <UInput
                v-model="form.summary"
                class="w-full"
                :maxlength="500"
              />
            </UFormField>
            <USwitch
              v-model="form.requires_reacceptance"
              :label="t('legal.reacceptLabel')"
              :description="t('legal.reacceptHelp')"
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
              form="legal-form"
              :label="t('legal.publish')"
              :loading="saving"
              :disabled="!canPublish"
            />
          </div>
        </template>
      </UModal>
    </template>
  </UDashboardPanel>
</template>
