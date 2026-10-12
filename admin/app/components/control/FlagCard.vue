<script setup lang="ts">
import type { AppMode, FeatureFlag, FlagCheck, FlagRules } from '~/types/api'
import { APP_MODES, APP_PLATFORMS } from '~/types/api'

// One feature flag: on/off, who gets it (rules), a plain-language summary and a per-account preview.
const props = defineProps<{ flag: FeatureFlag, areas: string[], canManage: boolean }>()
const emit = defineEmits<{ saved: [flag: FeatureFlag] }>()

const { t, locale } = useI18n()
const { request } = useApi()
const apiError = useApiError()
const toast = useToast()

const copyRules = (r: FlagRules): FlagRules => ({ ...r, platforms: [...r.platforms], areas: [...r.areas], roles: [...r.roles] })
const draft = reactive<{ enabled: boolean, rules: FlagRules }>({ enabled: props.flag.enabled, rules: copyRules(props.flag.rules) })
function reset() {
  draft.enabled = props.flag.enabled
  draft.rules = copyRules(props.flag.rules)
}
watch(() => props.flag, reset)

const dirty = computed(() => !sameFlagState(draft, props.flag))
const summary = computed(() => flagSummary(draft.enabled, draft.rules, t, locale.value))
const readOnly = computed(() => !props.canManage)

const platformItems = APP_PLATFORMS.map(p => ({ label: PLATFORM_LABELS[p], value: p }))
const roleItems = computed(() => APP_MODES.map(r => ({ label: t(`control.modes.${r}`), value: r })))
const areaItems = computed(() => {
  const names = [...props.areas, ...draft.rules.areas.filter(a => !props.areas.includes(a))]
  return names.map(name => ({ label: name, value: name }))
})
// USlider / UInputNumber bind numbers; null min_build means "any build".
const minBuild = computed<number | undefined>({
  get: () => draft.rules.min_build ?? undefined,
  set: (v) => {
    draft.rules.min_build = v === undefined || v === null || Number.isNaN(v) ? null : v
  },
})

const saving = ref(false)
async function save() {
  saving.value = true
  try {
    const flag = await request<FeatureFlag>(`/admin/flags/${encodeURIComponent(props.flag.key)}`, {
      method: 'PUT',
      body: { enabled: draft.enabled, rules: normalizeRules(draft.rules) },
    })
    toast.add({ title: t('flags.saved', { key: flag.key }), color: 'success' })
    emit('saved', flag)
  }
  catch (err) {
    toast.add({ title: apiError(err), color: 'error' })
  }
  finally {
    saving.value = false
  }
}

// ---- Preview: does this account get it? (uses the SAVED state) -------------------------------------

const email = ref('')
const mode = ref<'auto' | AppMode>('auto')
const modeItems = computed(() => [
  { label: t('flags.preview.auto'), value: 'auto' },
  ...APP_MODES.map(r => ({ label: t(`control.modes.${r}`), value: r })),
])
const checking = ref(false)
const result = ref<FlagCheck | null>(null)
const checkError = ref('')
async function check() {
  const value = email.value.trim()
  if (!value) return
  checking.value = true
  checkError.value = ''
  result.value = null
  try {
    result.value = await request<FlagCheck>(`/admin/flags/${encodeURIComponent(props.flag.key)}/check`, {
      query: { email: value, ...(mode.value !== 'auto' ? { mode: mode.value } : {}) },
    })
  }
  catch (err) {
    checkError.value = apiError(err)
  }
  finally {
    checking.value = false
  }
}
</script>

<template>
  <UCard>
    <template #header>
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div class="min-w-0">
          <div class="flex flex-wrap items-center gap-2">
            <h2 class="font-semibold">
              {{ props.flag.description }}
            </h2>
            <UBadge
              v-if="!props.flag.changed"
              color="neutral"
              variant="outline"
              size="sm"
            >
              {{ t('flags.byDefault') }}
            </UBadge>
          </div>
          <p class="text-xs text-(--ui-text-muted)">
            <code>{{ props.flag.key }}</code>
            · {{ t('flags.defaultIs', { value: props.flag.default ? t('flags.on') : t('flags.off') }) }}
            <template v-if="props.flag.updated_at">
              · {{ t('flags.updated', { date: formatDate(props.flag.updated_at, locale), email: props.flag.updated_by_email ?? '—' }) }}
            </template>
          </p>
        </div>
        <USwitch
          v-model="draft.enabled"
          :label="draft.enabled ? t('flags.on') : t('flags.off')"
          :disabled="readOnly"
        />
      </div>
    </template>

    <div class="space-y-5">
      <div
        class="flex items-start gap-2 rounded-md p-3 text-sm"
        :class="draft.enabled ? 'bg-(--ui-bg-elevated)' : 'bg-(--ui-bg-muted) text-(--ui-text-muted)'"
      >
        <UIcon
          name="i-lucide-users"
          class="mt-0.5 size-4 shrink-0"
        />
        <p>
          <span class="font-medium">{{ t('flags.whoGetsIt') }}</span>
          {{ summary }}
        </p>
      </div>

      <div
        v-if="draft.enabled"
        class="grid gap-5 sm:grid-cols-2"
      >
        <UFormField
          :label="t('flags.rules.roles')"
          :help="t('flags.rules.emptyMeansAll')"
        >
          <UCheckboxGroup
            v-model="draft.rules.roles"
            :items="roleItems"
            orientation="horizontal"
            :disabled="readOnly"
          />
        </UFormField>
        <UFormField
          :label="t('flags.rules.platforms')"
          :help="t('flags.rules.emptyMeansAll')"
        >
          <UCheckboxGroup
            v-model="draft.rules.platforms"
            :items="platformItems"
            orientation="horizontal"
            :disabled="readOnly"
          />
        </UFormField>
        <UFormField
          :label="t('flags.rules.areas')"
          :help="areaItems.length ? t('flags.rules.emptyMeansAll') : t('flags.rules.noAreas')"
          class="sm:col-span-2"
        >
          <UCheckboxGroup
            v-model="draft.rules.areas"
            :items="areaItems"
            orientation="horizontal"
            :disabled="readOnly"
          />
        </UFormField>
        <UFormField
          :label="t('flags.rules.minBuild')"
          :help="t('flags.rules.minBuildHelp')"
        >
          <UInputNumber
            v-model="minBuild"
            :min="0"
            :placeholder="t('flags.rules.anyBuild')"
            :disabled="readOnly"
          />
        </UFormField>
        <UFormField
          :label="t('flags.rules.percent')"
          :help="t('flags.rules.percentHelp')"
        >
          <div class="flex items-center gap-3">
            <USlider
              v-model="draft.rules.percent"
              :min="0"
              :max="100"
              :step="1"
              class="flex-1"
              :disabled="readOnly"
            />
            <UInputNumber
              v-model="draft.rules.percent"
              :min="0"
              :max="100"
              class="w-28"
              :disabled="readOnly"
            />
          </div>
        </UFormField>
      </div>

      <div
        v-if="props.canManage"
        class="flex flex-wrap gap-2"
      >
        <UButton
          :label="t('common.save')"
          :loading="saving"
          :disabled="!dirty"
          @click="save"
        />
        <UButton
          color="neutral"
          variant="ghost"
          :label="t('common.discard')"
          :disabled="!dirty || saving"
          @click="reset"
        />
      </div>

      <USeparator />

      <form
        class="space-y-2"
        @submit.prevent="check"
      >
        <p class="text-sm font-medium">
          {{ t('flags.preview.title') }}
        </p>
        <p class="text-xs text-(--ui-text-muted)">
          {{ dirty ? t('flags.preview.unsaved') : t('flags.preview.help') }}
        </p>
        <div class="flex flex-wrap items-center gap-2">
          <UInput
            v-model="email"
            type="email"
            :placeholder="t('flags.preview.email')"
            icon="i-lucide-mail"
            class="w-72"
          />
          <USelect
            v-model="mode"
            :items="modeItems"
            class="w-40"
          />
          <UButton
            type="submit"
            color="neutral"
            variant="subtle"
            icon="i-lucide-search"
            :label="t('flags.preview.check')"
            :loading="checking"
            :disabled="!email.trim()"
          />
        </div>
        <UAlert
          v-if="result"
          :color="result.enabled ? 'success' : 'neutral'"
          variant="subtle"
          :icon="result.enabled ? 'i-lucide-circle-check' : 'i-lucide-circle-x'"
          :title="t(result.enabled ? 'flags.preview.yes' : 'flags.preview.no', { email: result.email, role: t(`control.modes.${result.role}`) })"
        />
        <UAlert
          v-if="checkError"
          color="error"
          variant="subtle"
          icon="i-lucide-circle-alert"
          :title="checkError"
        />
      </form>
    </div>
  </UCard>
</template>
