<script setup lang="ts">
import type { EmailPreview, EmailTemplateInfo } from '~/types/api'

definePageMeta({ permission: 'notifications.send' })

const { t } = useI18n()
const { request } = useApi()
const route = useRoute()
const router = useRouter()
const apiError = useApiError()

const { data: templates, status: listStatus, error: listError } = await useAsyncData(
  'email-templates',
  () => request<EmailTemplateInfo[]>('/admin/email-templates'),
)

const selected = ref(typeof route.query.name === 'string' ? route.query.name : '')
const previewLocale = ref<'es' | 'en'>(route.query.locale === 'en' ? 'en' : 'es')
const view = ref<'html' | 'text'>('html')
const width = ref<'phone' | 'desktop'>('desktop')

// Opens the first template when none (or an unknown one) was asked for.
watch(templates, (list) => {
  if (list?.length && !list.some(item => item.name === selected.value)) selected.value = list[0]!.name
}, { immediate: true })
watch([selected, previewLocale], () => {
  router.replace({ query: { ...(selected.value ? { name: selected.value } : {}), ...(previewLocale.value !== 'es' ? { locale: previewLocale.value } : {}) } })
})

const { data: preview, status: previewStatus, error: previewError } = await useAsyncData(
  'email-template-preview',
  () => (selected.value
    ? request<EmailPreview>(`/admin/email-templates/${encodeURIComponent(selected.value)}`, { query: { locale: previewLocale.value } })
    : Promise.resolve(null)),
  { watch: [selected, previewLocale] },
)

const current = computed(() => templates.value?.find(item => item.name === selected.value) ?? null)
const localeItems = computed(() => [
  { label: t('control.spanish'), value: 'es' },
  { label: t('control.english'), value: 'en' },
])
const viewItems = computed(() => [
  { label: t('emailTemplates.html'), value: 'html' },
  { label: t('emailTemplates.text'), value: 'text' },
])
const widthItems = computed(() => [
  { label: t('emailTemplates.desktop'), value: 'desktop', icon: 'i-lucide-monitor' },
  { label: t('emailTemplates.phone'), value: 'phone', icon: 'i-lucide-smartphone' },
])
</script>

<template>
  <UDashboardPanel id="email-templates">
    <template #header>
      <UDashboardNavbar :title="t('nav.emailTemplates')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <UAlert
        v-if="listError"
        color="error"
        variant="subtle"
        icon="i-lucide-circle-alert"
        :title="apiError(listError)"
      />
      <USkeleton
        v-else-if="listStatus === 'pending'"
        class="h-96"
      />
      <p
        v-else-if="!templates?.length"
        class="text-sm text-(--ui-text-muted)"
      >
        {{ t('emailTemplates.empty') }}
      </p>

      <div
        v-else
        class="grid gap-6 lg:grid-cols-[18rem_1fr]"
      >
        <nav class="space-y-1">
          <p class="mb-2 text-sm text-(--ui-text-muted)">
            {{ t('emailTemplates.help') }}
          </p>
          <button
            v-for="item in templates"
            :key="item.name"
            type="button"
            class="w-full rounded-md px-3 py-2 text-left transition-colors"
            :class="item.name === selected ? 'bg-primary/10 text-primary' : 'hover:bg-(--ui-bg-elevated)'"
            @click="selected = item.name"
          >
            <span class="block text-sm font-medium">{{ item.label }}</span>
            <span class="block text-xs text-(--ui-text-muted)">{{ item.description }}</span>
          </button>
        </nav>

        <UCard>
          <template #header>
            <div class="flex flex-wrap items-center justify-between gap-3">
              <div class="min-w-0">
                <h2 class="font-semibold">
                  {{ current?.label }}
                </h2>
                <p class="font-mono text-xs text-(--ui-text-muted)">
                  {{ current?.name }}
                </p>
              </div>
              <div class="flex flex-wrap items-center gap-2">
                <UTabs
                  v-model="previewLocale"
                  :items="localeItems"
                  size="xs"
                  :content="false"
                />
                <UTabs
                  v-model="view"
                  :items="viewItems"
                  size="xs"
                  :content="false"
                />
                <UTabs
                  v-if="view === 'html'"
                  v-model="width"
                  :items="widthItems"
                  size="xs"
                  :content="false"
                />
              </div>
            </div>
          </template>

          <UAlert
            v-if="previewError"
            color="error"
            variant="subtle"
            icon="i-lucide-circle-alert"
            :title="apiError(previewError)"
          />
          <USkeleton
            v-else-if="previewStatus === 'pending' && !preview"
            class="h-[70vh]"
          />
          <div
            v-else-if="preview"
            class="space-y-3"
          >
            <p class="text-sm">
              <span class="text-(--ui-text-muted)">{{ t('emailTemplates.subject') }}</span>
              <span class="font-medium">{{ preview.subject }}</span>
            </p>
            <div
              v-if="view === 'html'"
              class="rounded-md border border-(--ui-border) bg-(--ui-bg-muted) p-2"
            >
              <!-- Sandboxed with no permissions: the email's HTML cannot run scripts or reach the panel. -->
              <iframe
                :srcdoc="preview.html"
                sandbox=""
                referrerpolicy="no-referrer"
                :title="t('emailTemplates.frameTitle', { name: current?.label ?? preview.name })"
                class="mx-auto block h-[70vh] rounded bg-white transition-[width]"
                :class="width === 'phone' ? 'w-[375px] max-w-full' : 'w-full'"
              />
            </div>
            <pre
              v-else
              class="max-h-[70vh] overflow-auto rounded-md border border-(--ui-border) bg-(--ui-bg-muted) p-4 text-sm whitespace-pre-wrap"
            >{{ preview.text }}</pre>
            <p class="text-xs text-(--ui-text-muted)">
              {{ t('emailTemplates.sample') }}
            </p>
          </div>
        </UCard>
      </div>
    </template>
  </UDashboardPanel>
</template>
