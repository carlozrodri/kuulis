<script setup lang="ts">
import type { MdInline } from '~/utils/markdown'

/** Help article preview: the same Markdown subset the apps render, drawn without v-html. */
const props = defineProps<{ source: string }>()

const blocks = computed(() => parseMarkdown(props.source))
const inlineClass = (piece: MdInline) => [piece.bold ? 'font-semibold' : '', piece.italic ? 'italic' : ''].join(' ')
</script>

<template>
  <div class="space-y-3 text-sm leading-relaxed">
    <template
      v-for="(block, index) in blocks"
      :key="index"
    >
      <component
        :is="`h${block.level + 1}`"
        v-if="block.type === 'heading'"
        class="font-semibold"
        :class="block.level === 1 ? 'text-lg' : block.level === 2 ? 'text-base' : 'text-sm'"
      >
        <template
          v-for="(piece, i) in block.inlines"
          :key="i"
        >
          <a
            v-if="piece.href"
            :href="piece.href"
            target="_blank"
            rel="noopener noreferrer"
            class="text-primary underline"
          >{{ piece.text }}</a>
          <span
            v-else
            :class="inlineClass(piece)"
          >{{ piece.text }}</span>
        </template>
      </component>
      <p v-else-if="block.type === 'paragraph'">
        <template
          v-for="(piece, i) in block.inlines"
          :key="i"
        >
          <a
            v-if="piece.href"
            :href="piece.href"
            target="_blank"
            rel="noopener noreferrer"
            class="text-primary underline"
          >{{ piece.text }}</a>
          <span
            v-else
            :class="inlineClass(piece)"
          >{{ piece.text }}</span>
        </template>
      </p>
      <component
        :is="block.ordered ? 'ol' : 'ul'"
        v-else
        class="space-y-1 pl-5"
        :class="block.ordered ? 'list-decimal' : 'list-disc'"
      >
        <li
          v-for="(item, j) in block.items"
          :key="j"
        >
          <template
            v-for="(piece, i) in item"
            :key="i"
          >
            <a
              v-if="piece.href"
              :href="piece.href"
              target="_blank"
              rel="noopener noreferrer"
              class="text-primary underline"
            >{{ piece.text }}</a>
            <span
              v-else
              :class="inlineClass(piece)"
            >{{ piece.text }}</span>
          </template>
        </li>
      </component>
    </template>
  </div>
</template>
