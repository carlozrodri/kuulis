<script setup lang="ts">
import type { PostingCard } from '~/types/api'

definePageMeta({ permission: 'marketing.publish' })

const { t, locale } = useI18n()
const { request } = useApi()
const apiError = useApiError()
const toast = useToast()
const route = useRoute()
const router = useRouter()

// The day lives in the URL so a refresh (or a shared link) keeps it.
const initialDay = typeof route.query.day === 'string' && isDay(route.query.day) ? route.query.day : caracasToday()
const day = ref(initialDay)
watch(day, value => router.replace({ query: value === caracasToday() ? {} : { day: value } }))

const { data: cards, status, error, refresh } = await useAsyncData(
  'marketing-queue',
  () => request<PostingCard[]>('/admin/marketing/queue', { query: { day: day.value } }),
  { watch: [day] },
)

const isToday = computed(() => day.value === caracasToday())
const dayLabel = computed(() =>
  new Intl.DateTimeFormat(locale.value, { weekday: 'long', day: 'numeric', month: 'long', timeZone: 'UTC' }).format(new Date(`${day.value}T00:00:00Z`)),
)
const pending = computed(() => (cards.value ?? []).filter(c => !c.published_at).length)

async function copy(text: string, what: string) {
  try {
    await navigator.clipboard.writeText(text)
    toast.add({ title: t('marketing.publish.copied', { what }), color: 'success', icon: 'i-lucide-check' })
  }
  catch {
    toast.add({ title: t('errors.generic'), color: 'error' })
  }
}

// Steps ticked on this phone only (nothing to save: they are a memory aid).
const ticked = ref<Record<string, boolean>>({})
const tickKey = (card: PostingCard, i: number) => `${card.variant_id}:${i}`

// ---- "Ya lo publiqué" -------------------------------------------------------------------------
const publishing = ref<PostingCard | null>(null)
const linkOnly = ref(false)
const postUrl = ref('')
const open = computed({
  get: () => publishing.value !== null,
  set: (v) => {
    if (!v) publishing.value = null
  },
})
function startPublish(card: PostingCard, addLink = false) {
  publishing.value = card
  linkOnly.value = addLink
  postUrl.value = card.published_url ?? ''
}
const saving = ref(false)
async function confirmPublish() {
  const card = publishing.value
  if (!card) return
  const url = postUrl.value.trim() || null
  if (url && !/^https?:\/\//i.test(url)) {
    toast.add({ title: t('marketing.publish.badUrl'), color: 'error' })
    return
  }
  saving.value = true
  try {
    if (linkOnly.value && card.publication_id) {
      await request(`/admin/marketing/publications/${card.publication_id}`, { method: 'PATCH', body: { url } })
    }
    else {
      await request(`/admin/marketing/variants/${card.variant_id}/publish`, { method: 'POST', body: { url } })
    }
    toast.add({ title: linkOnly.value ? t('marketing.publish.linkSaved') : t('marketing.publish.done'), color: 'success' })
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
  <UDashboardPanel id="marketing-publish">
    <template #header>
      <UDashboardNavbar :title="t('nav.marketingPublish')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton
            icon="i-lucide-refresh-cw"
            color="neutral"
            variant="ghost"
            :loading="status === 'pending'"
            :aria-label="t('marketing.publish.refresh')"
            @click="refresh()"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="mx-auto w-full max-w-xl space-y-4">
        <div class="flex items-center justify-between gap-2">
          <UButton
            icon="i-lucide-chevron-left"
            color="neutral"
            variant="outline"
            :aria-label="t('marketing.publish.previousDay')"
            @click="day = addDays(day, -1)"
          />
          <div class="text-center">
            <p class="font-semibold capitalize">
              {{ isToday ? t('marketing.publish.today') : dayLabel }}
            </p>
            <p class="text-xs text-(--ui-text-muted)">
              {{ isToday ? dayLabel : '' }}
              <template v-if="cards?.length">
                · {{ t('marketing.publish.pending', { n: pending }) }}
              </template>
            </p>
          </div>
          <UButton
            icon="i-lucide-chevron-right"
            color="neutral"
            variant="outline"
            :aria-label="t('marketing.publish.nextDay')"
            @click="day = addDays(day, 1)"
          />
        </div>

        <UAlert
          v-if="error"
          color="error"
          variant="subtle"
          icon="i-lucide-circle-alert"
          :title="apiError(error)"
        />

        <div
          v-if="status !== 'pending' && !error && !cards?.length"
          class="rounded-lg border border-dashed border-(--ui-border) p-8 text-center"
        >
          <UIcon
            name="i-lucide-inbox"
            class="mx-auto size-8 text-(--ui-text-muted)"
          />
          <p class="mt-2 font-medium">
            {{ t('marketing.publish.empty') }}
          </p>
          <p class="text-sm text-(--ui-text-muted)">
            {{ t('marketing.publish.emptyHelp') }}
          </p>
        </div>

        <UCard
          v-for="card in cards ?? []"
          :key="card.variant_id"
          :class="card.published_at ? 'opacity-80' : ''"
          :ui="{ body: 'space-y-4 p-4 sm:p-5' }"
        >
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <div class="flex flex-wrap items-center gap-2">
                <UBadge
                  :icon="platformIcon[card.platform]"
                  color="neutral"
                  variant="solid"
                  size="lg"
                >
                  {{ platformLabel[card.platform] }}
                </UBadge>
                <span
                  v-if="card.account"
                  class="text-sm font-medium"
                >{{ card.account }}</span>
              </div>
              <p class="mt-1 text-xs text-(--ui-text-muted)">
                {{ card.code }} · {{ card.content_title }}
              </p>
            </div>
            <div class="shrink-0 text-right">
              <p class="text-2xl font-bold tabular-nums">
                {{ formatCaracasTime(card.scheduled_at, locale) }}
              </p>
              <p class="text-xs text-(--ui-text-muted)">
                {{ t('marketing.publish.caracasTime') }}
              </p>
            </div>
          </div>

          <UAlert
            v-if="card.published_at"
            color="success"
            variant="subtle"
            icon="i-lucide-circle-check"
            :title="t('marketing.publish.publishedAt', { time: formatCaracasTime(card.published_at, locale) })"
          >
            <template #description>
              <a
                v-if="card.published_url"
                :href="card.published_url"
                target="_blank"
                rel="noopener"
                class="break-all underline"
              >{{ card.published_url }}</a>
              <UButton
                v-else-if="card.publication_id"
                size="xs"
                variant="link"
                class="px-0"
                :label="t('marketing.publish.addLink')"
                @click="startPublish(card, true)"
              />
            </template>
          </UAlert>

          <div class="flex gap-3">
            <img
              v-if="card.cover_url"
              :src="card.cover_url"
              :alt="t('marketing.publish.cover')"
              class="h-28 w-20 shrink-0 rounded-md object-cover"
              loading="lazy"
            >
            <div class="flex min-w-0 flex-1 flex-col justify-center gap-2">
              <UButton
                v-if="card.file_url"
                :to="card.file_url"
                target="_blank"
                rel="noopener"
                :download="card.file_name ?? undefined"
                size="xl"
                block
                icon="i-lucide-download"
                :label="card.file_kind === 'imagen' ? t('marketing.publish.downloadImage') : t('marketing.publish.downloadVideo')"
              />
              <UAlert
                v-else
                color="warning"
                variant="subtle"
                icon="i-lucide-triangle-alert"
                :title="t('marketing.publish.noFile')"
              />
              <UButton
                v-if="card.cover_url"
                :to="card.cover_url"
                target="_blank"
                rel="noopener"
                color="neutral"
                variant="outline"
                block
                icon="i-lucide-image"
                :label="t('marketing.publish.downloadCover')"
              />
            </div>
          </div>

          <div
            v-if="card.title"
            class="space-y-1"
          >
            <div class="flex items-center justify-between">
              <span class="text-xs font-semibold text-(--ui-text-muted) uppercase">{{ t('marketing.publish.title') }}</span>
              <UButton
                size="sm"
                color="neutral"
                variant="soft"
                icon="i-lucide-copy"
                :label="t('marketing.publish.copy')"
                @click="copy(card.title, t('marketing.publish.title'))"
              />
            </div>
            <p class="rounded-md bg-(--ui-bg-elevated) p-3 text-sm">
              {{ card.title }}
            </p>
          </div>

          <div
            v-if="card.caption"
            class="space-y-1"
          >
            <div class="flex items-center justify-between">
              <span class="text-xs font-semibold text-(--ui-text-muted) uppercase">{{ t('marketing.publish.caption') }}</span>
              <UButton
                size="sm"
                color="neutral"
                variant="soft"
                icon="i-lucide-copy"
                :label="t('marketing.publish.copy')"
                @click="copy(card.caption, t('marketing.publish.caption'))"
              />
            </div>
            <p class="rounded-md bg-(--ui-bg-elevated) p-3 text-sm whitespace-pre-line">
              {{ card.caption }}
            </p>
          </div>

          <div
            v-if="card.hashtags.length"
            class="space-y-1"
          >
            <div class="flex items-center justify-between">
              <span class="text-xs font-semibold text-(--ui-text-muted) uppercase">{{ t('marketing.publish.hashtags') }}</span>
              <UButton
                size="sm"
                color="neutral"
                variant="soft"
                icon="i-lucide-copy"
                :label="t('marketing.publish.copy')"
                @click="copy(card.hashtags.join(' '), t('marketing.publish.hashtags'))"
              />
            </div>
            <p class="rounded-md bg-(--ui-bg-elevated) p-3 text-sm text-(--ui-primary)">
              {{ card.hashtags.join(' ') }}
            </p>
          </div>

          <div
            v-if="card.checklist.length"
            class="space-y-2"
          >
            <span class="text-xs font-semibold text-(--ui-text-muted) uppercase">{{ t('marketing.publish.checklist') }}</span>
            <UCheckbox
              v-for="(item, i) in card.checklist"
              :key="i"
              v-model="ticked[tickKey(card, i)]"
              :label="item"
              size="lg"
            />
          </div>

          <UButton
            v-if="!card.published_at"
            size="xl"
            block
            color="success"
            icon="i-lucide-send"
            :label="t('marketing.publish.markDone')"
            @click="startPublish(card)"
          />
        </UCard>
      </div>

      <UModal
        v-model:open="open"
        :title="linkOnly ? t('marketing.publish.addLink') : t('marketing.publish.confirmTitle')"
        :description="publishing ? `${platformLabel[publishing.platform]} · ${publishing.code}` : ''"
      >
        <template #body>
          <form
            id="publish-form"
            class="space-y-3"
            @submit.prevent="confirmPublish"
          >
            <UFormField
              :label="t('marketing.publish.postUrl')"
              :help="t('marketing.publish.postUrlHelp')"
            >
              <UInput
                v-model="postUrl"
                type="url"
                inputmode="url"
                placeholder="https://"
                class="w-full"
                size="lg"
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
              @click="publishing = null"
            />
            <UButton
              type="submit"
              form="publish-form"
              color="success"
              icon="i-lucide-check"
              :loading="saving"
              :label="linkOnly ? t('common.save') : t('marketing.publish.confirm')"
            />
          </div>
        </template>
      </UModal>
    </template>
  </UDashboardPanel>
</template>
