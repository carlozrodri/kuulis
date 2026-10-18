<script setup lang="ts">
import type { MarketingAsset, MarketingAssetRole, MarketingAssetUpload, MarketingContent } from '~/types/api'
import { MARKETING_ASSET_ROLES } from '~/types/api'

const props = defineProps<{ contentId: string, assets: MarketingAsset[], canUpload: boolean }>()
const emit = defineEmits<{ updated: [content: MarketingContent] }>()

const { t, locale } = useI18n()
const { request } = useApi()
const toast = useToast()
const apiError = useApiError()

const ACCEPT = 'video/mp4,video/quicktime,image/jpeg,image/png,image/webp,audio/mpeg,audio/mp4,audio/wav'
const role = ref<MarketingAssetRole>('final')
const source = ref('manual')
const roleItems = computed(() => MARKETING_ASSET_ROLES.map(value => ({ label: t(`marketing.assetRoles.${value}`), value })))
const input = ref<HTMLInputElement | null>(null)
const uploading = ref<string | null>(null)

/** Width, height and length read in the browser, so the registry has them without a server step. */
function mediaInfo(file: File): Promise<{ width?: number, height?: number, duration_s?: number }> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file)
    const done = (info: { width?: number, height?: number, duration_s?: number }) => {
      URL.revokeObjectURL(url)
      resolve(info)
    }
    if (file.type.startsWith('video/')) {
      const video = document.createElement('video')
      video.preload = 'metadata'
      video.onloadedmetadata = () => done({ width: video.videoWidth || undefined, height: video.videoHeight || undefined, duration_s: Number.isFinite(video.duration) && video.duration > 0 ? Math.round(video.duration * 10) / 10 : undefined })
      video.onerror = () => done({})
      video.src = url
    }
    else if (file.type.startsWith('image/')) {
      const img = new Image()
      img.onload = () => done({ width: img.naturalWidth, height: img.naturalHeight })
      img.onerror = () => done({})
      img.src = url
    }
    else {
      done({})
    }
  })
}

async function upload(files: FileList | null) {
  if (!files?.length) return
  for (const file of Array.from(files)) {
    uploading.value = file.name
    try {
      const info = await mediaInfo(file)
      const created = await request<MarketingAssetUpload>(`/admin/marketing/contents/${props.contentId}/assets`, {
        method: 'POST',
        body: { filename: file.name, content_type: file.type, size: file.size, role: role.value, source: source.value.trim() || 'manual', ...info },
      })
      await $fetch(created.upload_url, { method: created.method, body: file, headers: created.headers })
      await request(`/admin/marketing/contents/${props.contentId}/assets/${created.asset.id}/confirm`, { method: 'POST' })
      toast.add({ title: t('marketing.assets.uploaded', { name: file.name }), color: 'success' })
    }
    catch (err) {
      toast.add({ title: `${file.name}: ${apiError(err)}`, color: 'error' })
    }
  }
  uploading.value = null
  if (input.value) input.value.value = ''
  emit('updated', await request<MarketingContent>(`/admin/marketing/contents/${props.contentId}`))
}

const kindIcon = { video: 'i-lucide-film', imagen: 'i-lucide-image', audio: 'i-lucide-music-2' } as const
</script>

<template>
  <UCard :ui="{ body: 'space-y-3' }">
    <template #header>
      <div class="flex flex-wrap items-center justify-between gap-2">
        <h3 class="font-semibold">
          {{ t('marketing.assets.title') }}
          <span class="font-normal text-(--ui-text-muted)">({{ props.assets.length }})</span>
        </h3>
      </div>
    </template>

    <div
      v-if="props.canUpload"
      class="flex flex-wrap items-end gap-2"
    >
      <UFormField
        :label="t('marketing.assets.role')"
        class="w-36"
      >
        <USelect
          v-model="role"
          :items="roleItems"
          class="w-full"
        />
      </UFormField>
      <UFormField
        :label="t('marketing.assets.source')"
        :help="t('marketing.assets.sourceHelp')"
        class="w-40"
      >
        <UInput
          v-model="source"
          :maxlength="32"
          class="w-full"
        />
      </UFormField>
      <input
        ref="input"
        type="file"
        multiple
        :accept="ACCEPT"
        class="hidden"
        @change="upload(($event.target as HTMLInputElement).files)"
      >
      <UButton
        icon="i-lucide-upload"
        :label="uploading ? t('marketing.assets.uploading', { name: uploading }) : t('marketing.assets.upload')"
        :loading="!!uploading"
        @click="input?.click()"
      />
    </div>

    <p
      v-if="!props.assets.length"
      class="text-sm text-(--ui-text-muted)"
    >
      {{ t('marketing.assets.none') }}
    </p>
    <ul
      v-else
      class="divide-y divide-(--ui-border)"
    >
      <li
        v-for="asset in props.assets"
        :key="asset.id"
        class="flex items-center gap-3 py-2"
      >
        <UIcon
          :name="kindIcon[asset.kind]"
          class="size-5 shrink-0 text-(--ui-text-muted)"
        />
        <div class="min-w-0 flex-1">
          <p class="truncate text-sm font-medium">
            {{ asset.filename }}
          </p>
          <p class="text-xs text-(--ui-text-muted)">
            {{ t(`marketing.assetRoles.${asset.role}`) }} · {{ asset.source }}<template v-if="asset.model">
              · {{ asset.model }}
            </template>
            · {{ formatBytes(asset.size, locale) }}
            <template v-if="asset.width && asset.height">
              · {{ asset.width }}×{{ asset.height }}
            </template>
            <template v-if="asset.duration_s">
              · {{ formatNumber(asset.duration_s, locale, 1) }} s
            </template>
            <template v-if="asset.cost_usd">
              · ${{ asset.cost_usd }}
            </template>
          </p>
        </div>
        <UBadge
          v-if="!asset.uploaded_at"
          color="warning"
          variant="subtle"
        >
          {{ t('marketing.assets.notUploaded') }}
        </UBadge>
        <UButton
          v-else-if="asset.download_url"
          :to="asset.download_url"
          target="_blank"
          rel="noopener"
          size="xs"
          color="neutral"
          variant="ghost"
          icon="i-lucide-download"
          :aria-label="t('marketing.assets.download')"
        />
      </li>
    </ul>
  </UCard>
</template>
