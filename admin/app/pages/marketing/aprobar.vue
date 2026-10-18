<script setup lang="ts">
import type { MarketingContent, MarketingContentSummary, MarketingVariant, Page } from '~/types/api'

definePageMeta({ permission: 'marketing.approve' })

const { t, locale } = useI18n()
const { request } = useApi()
const toast = useToast()
const apiError = useApiError()

// The queue is short (a few pieces a day): load each piece whole to show its files and texts.
const { data: pieces, status, error, refresh } = await useAsyncData('marketing-approve', async () => {
  const page = await request<Page<MarketingContentSummary>>('/admin/marketing/contents', { query: { status: 'producido', limit: 50 } })
  return Promise.all(page.items.map(item => request<MarketingContent>(`/admin/marketing/contents/${item.id}`)))
})

const busy = ref<string | null>(null)
function drop(id: string) {
  pieces.value = (pieces.value ?? []).filter(p => p.id !== id)
}
async function approve(piece: MarketingContent) {
  busy.value = piece.id
  try {
    await request(`/admin/marketing/contents/${piece.id}/approve`, { method: 'POST' })
    toast.add({ title: t('marketing.approvedCode', { code: piece.code }), color: 'success' })
    drop(piece.id)
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    busy.value = null
  }
}

const reviewing = ref<MarketingContent | null>(null)
const note = ref('')
const changesOpen = computed({
  get: () => reviewing.value !== null,
  set: (v) => {
    if (!v) reviewing.value = null
  },
})
async function sendChanges() {
  const piece = reviewing.value
  if (!piece || !note.value.trim()) return
  try {
    await request(`/admin/marketing/contents/${piece.id}/request-changes`, { method: 'POST', body: { note: note.value.trim() } })
    toast.add({ title: t('marketing.changesRequested'), color: 'success' })
    reviewing.value = null
    note.value = ''
    drop(piece.id)
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
}

const fileOf = (piece: MarketingContent, variant: MarketingVariant) => piece.assets.find(a => a.id === variant.asset_id)
const coverOf = (piece: MarketingContent, variant: MarketingVariant) => piece.assets.find(a => a.id === variant.cover_asset_id)
const notReady = (piece: MarketingContent) => !piece.variants.length || piece.variants.some(v => variantMissing(v, piece.assets).length > 0)
</script>

<template>
  <UDashboardPanel id="marketing-approve">
    <template #header>
      <UDashboardNavbar :title="t('nav.marketingApprove')">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton
            icon="i-lucide-refresh-cw"
            color="neutral"
            variant="ghost"
            :loading="status === 'pending'"
            :aria-label="t('marketing.refresh')"
            @click="refresh()"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="mx-auto w-full max-w-3xl space-y-4">
        <p class="text-sm text-(--ui-text-muted)">
          {{ t('marketing.approveHelp') }}
        </p>
        <UAlert
          v-if="error"
          color="error"
          variant="subtle"
          icon="i-lucide-circle-alert"
          :title="apiError(error)"
        />
        <div
          v-if="status !== 'pending' && !error && !pieces?.length"
          class="rounded-lg border border-dashed border-(--ui-border) p-8 text-center"
        >
          <UIcon
            name="i-lucide-circle-check"
            class="mx-auto size-8 text-(--ui-success)"
          />
          <p class="mt-2 font-medium">
            {{ t('marketing.approveEmpty') }}
          </p>
        </div>

        <UCard
          v-for="piece in pieces ?? []"
          :key="piece.id"
          :ui="{ body: 'space-y-4 p-4 sm:p-5' }"
        >
          <div class="flex items-start justify-between gap-2">
            <div class="min-w-0">
              <NuxtLink
                :to="`/marketing/piezas/${piece.id}`"
                class="font-semibold hover:underline"
              >
                {{ piece.title }}
              </NuxtLink>
              <p class="text-xs text-(--ui-text-muted)">
                <span class="font-mono">{{ piece.code }}</span>
                <template v-if="piece.pillar">
                  · {{ piece.pillar }}
                </template>
                <template v-if="piece.format">
                  · {{ piece.format }}
                </template>
                <template v-if="piece.created_by_agent">
                  · {{ t('marketing.byAgent', { agent: piece.created_by_agent }) }}
                </template>
              </p>
            </div>
          </div>

          <div
            v-for="variant in piece.variants"
            :key="variant.id"
            class="flex flex-col gap-3 rounded-lg border border-(--ui-border) p-3 sm:flex-row"
          >
            <div class="w-full shrink-0 sm:w-40">
              <video
                v-if="fileOf(piece, variant)?.kind === 'video' && fileOf(piece, variant)?.download_url"
                :src="fileOf(piece, variant)!.download_url!"
                :poster="coverOf(piece, variant)?.download_url ?? undefined"
                controls
                playsinline
                preload="metadata"
                class="mx-auto aspect-[9/16] max-h-96 rounded-md bg-black object-contain"
              />
              <img
                v-else-if="fileOf(piece, variant)?.download_url"
                :src="fileOf(piece, variant)!.download_url!"
                :alt="variant.platform"
                class="w-full rounded-md object-cover"
              >
              <UAlert
                v-else
                color="warning"
                variant="subtle"
                icon="i-lucide-triangle-alert"
                :title="t('marketing.variant.noFile')"
              />
            </div>
            <div class="min-w-0 flex-1 space-y-2 text-sm">
              <div class="flex flex-wrap items-center gap-2">
                <UBadge
                  :icon="platformIcon[variant.platform]"
                  color="neutral"
                  variant="solid"
                >
                  {{ platformLabel[variant.platform] }}
                </UBadge>
                <span class="text-(--ui-text-muted)">{{ variant.account }}</span>
                <span
                  class="ml-auto font-medium"
                  :class="variant.scheduled_at ? '' : 'text-(--ui-warning)'"
                >
                  {{ variant.scheduled_at ? formatCaracasDateTime(variant.scheduled_at, locale) : t('marketing.variant.noTime') }}
                </span>
              </div>
              <p
                v-if="variant.title"
                class="font-medium"
              >
                {{ variant.title }}
              </p>
              <p class="whitespace-pre-line">
                {{ variant.caption || '—' }}
              </p>
              <p
                v-if="variant.hashtags.length"
                class="text-(--ui-primary)"
              >
                {{ formatHashtags(variant.hashtags) }}
              </p>
              <p
                v-if="!variant.ai_label"
                class="text-xs text-(--ui-warning)"
              >
                {{ t('marketing.variant.noAiLabel') }}
              </p>
            </div>
          </div>

          <div class="flex flex-col gap-2 sm:flex-row sm:justify-end">
            <UButton
              size="lg"
              color="warning"
              variant="outline"
              icon="i-lucide-undo-2"
              :label="t('marketing.requestChanges')"
              class="justify-center"
              @click="reviewing = piece"
            />
            <UButton
              size="lg"
              color="success"
              icon="i-lucide-badge-check"
              :label="t('marketing.approve')"
              :loading="busy === piece.id"
              :disabled="notReady(piece)"
              class="justify-center"
              @click="approve(piece)"
            />
          </div>
          <p
            v-if="notReady(piece)"
            class="text-right text-xs text-(--ui-warning)"
          >
            {{ t('errors.marketing_not_ready') }}
          </p>
        </UCard>
      </div>

      <UModal
        v-model:open="changesOpen"
        :title="t('marketing.requestChanges')"
        :description="reviewing ? `${reviewing.code} · ${reviewing.title}` : ''"
      >
        <template #body>
          <UTextarea
            v-model="note"
            :rows="4"
            :maxlength="2000"
            :placeholder="t('marketing.requestChangesHelp')"
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
              @click="reviewing = null"
            />
            <UButton
              color="warning"
              :label="t('marketing.sendChanges')"
              :disabled="!note.trim()"
              @click="sendChanges"
            />
          </div>
        </template>
      </UModal>
    </template>
  </UDashboardPanel>
</template>
