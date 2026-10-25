<script setup lang="ts">
/** The script as something to read: idea, scenes on a timeline, call to action, and the AI prompts. */
const props = defineProps<{ script: Record<string, unknown>, notes: string | null }>()
const { t, locale } = useI18n()

const parts = computed(() => readableScript(props.script))
const empty = computed(() => !Object.keys(props.script).length)
const raw = computed(() => JSON.stringify(props.script, null, 2))
const range = (from: number | null, to: number | null) =>
  from === null ? '' : to === null ? formatClock(from) : `${formatClock(from)}–${formatClock(to)}`
const totalCost = computed(() => parts.value.prompts.reduce((sum, p) => sum + (p.costUsd ?? 0), 0))
</script>

<template>
  <div class="space-y-5">
    <p
      v-if="empty && !props.notes"
      class="rounded-xl border border-dashed border-(--ui-border) p-6 text-center text-sm text-(--ui-text-muted)"
    >
      {{ t('marketing.noScript') }}
    </p>

    <div
      v-if="parts.idea || props.notes"
      class="grid gap-3 sm:grid-cols-2"
    >
      <div
        v-if="parts.idea"
        class="rounded-xl bg-(--ui-bg-elevated) p-4"
      >
        <p class="text-xs font-semibold tracking-wide text-(--ui-text-muted) uppercase">
          {{ t('marketing.scriptView.idea') }}
        </p>
        <p class="mt-1 text-sm">
          {{ parts.idea }}
        </p>
      </div>
      <div
        v-if="props.notes"
        class="rounded-xl bg-(--ui-bg-elevated) p-4"
      >
        <p class="text-xs font-semibold tracking-wide text-(--ui-text-muted) uppercase">
          {{ t('marketing.fields.notes') }}
        </p>
        <p class="mt-1 text-sm whitespace-pre-line">
          {{ props.notes }}
        </p>
      </div>
    </div>

    <section
      v-if="parts.scenes.length"
      class="space-y-2"
    >
      <h3 class="text-sm font-semibold">
        {{ t('marketing.scriptView.scenes') }}
      </h3>
      <ol class="space-y-2">
        <li
          v-for="(scene, i) in parts.scenes"
          :key="i"
          class="flex gap-3 rounded-xl border border-(--ui-border) p-3"
        >
          <span class="h-fit shrink-0 rounded-md bg-(--ui-primary)/10 px-2 py-1 font-mono text-xs font-semibold text-(--ui-primary)">
            {{ range(scene.from, scene.to) || i + 1 }}
          </span>
          <div class="min-w-0 space-y-1 text-sm">
            <p
              v-if="scene.shot"
              class="font-medium"
            >
              {{ scene.shot }}
            </p>
            <p
              v-if="scene.voice"
              class="text-(--ui-text-muted)"
            >
              <UIcon
                name="i-lucide-mic"
                class="me-1 size-3.5 align-[-2px]"
              />
              <span class="sr-only">{{ t('marketing.scriptView.voice') }}:</span>
              {{ scene.voice }}
            </p>
            <p
              v-if="scene.text"
              class="text-(--ui-text-muted)"
            >
              <UIcon
                name="i-lucide-type"
                class="me-1 size-3.5 align-[-2px]"
              />
              <span class="sr-only">{{ t('marketing.scriptView.onScreen') }}:</span>
              {{ scene.text }}
            </p>
          </div>
        </li>
      </ol>
    </section>

    <div
      v-if="parts.cta"
      class="flex items-start gap-2 rounded-xl border border-(--ui-primary)/30 bg-(--ui-primary)/5 p-3 text-sm"
    >
      <UIcon
        name="i-lucide-megaphone"
        class="mt-0.5 size-4 shrink-0 text-(--ui-primary)"
      />
      <p><span class="font-semibold">{{ t('marketing.scriptView.cta') }}:</span> {{ parts.cta }}</p>
    </div>

    <section
      v-if="parts.prompts.length"
      class="space-y-2"
    >
      <h3 class="flex flex-wrap items-baseline gap-2 text-sm font-semibold">
        {{ t('marketing.scriptView.prompts', { n: parts.prompts.length }) }}
        <span
          v-if="totalCost"
          class="text-xs font-normal text-(--ui-text-muted)"
        >{{ t('marketing.scriptView.listCost', { cost: formatMoney(totalCost, locale) }) }}</span>
      </h3>
      <details
        v-for="(p, i) in parts.prompts"
        :key="i"
        class="group rounded-xl border border-(--ui-border) [&_summary::-webkit-details-marker]:hidden"
      >
        <summary class="flex cursor-pointer list-none items-center gap-2 rounded-xl p-3 text-sm focus-visible:ring-2 focus-visible:ring-(--ui-primary) focus-visible:outline-none">
          <UIcon
            name="i-lucide-chevron-right"
            class="size-4 shrink-0 transition group-open:rotate-90"
          />
          <span class="font-medium">{{ p.shot || t('marketing.scriptView.prompt', { n: i + 1 }) }}</span>
          <span class="truncate text-xs text-(--ui-text-muted)">{{ [p.tool, p.model].filter(Boolean).join(' · ') }}</span>
          <span
            v-if="p.costUsd"
            class="ms-auto shrink-0 text-xs text-(--ui-text-muted)"
          >{{ formatMoney(p.costUsd, locale) }}</span>
        </summary>
        <div class="space-y-2 border-t border-(--ui-border) p-3">
          <p class="text-sm whitespace-pre-line">
            {{ p.prompt }}
          </p>
          <p
            v-if="p.requestId"
            class="font-mono text-xs break-all text-(--ui-text-muted)"
          >
            {{ t('marketing.scriptView.requestId') }}: {{ p.requestId }}
          </p>
        </div>
      </details>
    </section>

    <div
      v-if="parts.facts.length"
      class="flex flex-wrap items-center gap-1.5 text-xs text-(--ui-text-muted)"
    >
      {{ t('marketing.scriptView.facts') }}:
      <UBadge
        v-for="fact in parts.facts"
        :key="fact"
        color="neutral"
        variant="subtle"
        size="sm"
      >
        {{ fact }}
      </UBadge>
    </div>

    <details
      v-if="!empty"
      class="group rounded-xl border border-(--ui-border) [&_summary::-webkit-details-marker]:hidden"
      :open="!parts.idea && !parts.scenes.length && !parts.prompts.length"
    >
      <summary class="flex cursor-pointer list-none items-center gap-2 rounded-xl p-3 text-sm text-(--ui-text-muted) focus-visible:ring-2 focus-visible:ring-(--ui-primary) focus-visible:outline-none">
        <UIcon
          name="i-lucide-chevron-right"
          class="size-4 shrink-0 transition group-open:rotate-90"
        />
        {{ t('marketing.scriptView.raw') }}
      </summary>
      <pre class="max-h-96 overflow-auto border-t border-(--ui-border) p-3 text-xs whitespace-pre-wrap">{{ raw }}</pre>
    </details>
  </div>
</template>
