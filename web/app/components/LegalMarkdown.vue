<script setup lang="ts">
import { parseMarkdown } from '~/utils/markdown'

const props = defineProps<{ source: string }>()
const blocks = computed(() => parseMarkdown(props.source))
</script>

<template>
  <div class="md">
    <template
      v-for="(block, index) in blocks"
      :key="index"
    >
      <component
        :is="block.level === 3 ? 'h3' : 'h2'"
        v-if="block.type === 'heading'"
      >
        <MarkdownSpans :spans="block.spans" />
      </component>
      <p v-else-if="block.type === 'paragraph'">
        <MarkdownSpans :spans="block.spans" />
      </p>
      <blockquote v-else-if="block.type === 'quote'">
        <MarkdownSpans :spans="block.spans" />
      </blockquote>
      <component
        :is="block.ordered ? 'ol' : 'ul'"
        v-else-if="block.type === 'list'"
      >
        <li
          v-for="(item, n) in block.items"
          :key="n"
        >
          <MarkdownSpans :spans="item" />
        </li>
      </component>
      <div
        v-else-if="block.type === 'table'"
        class="table"
      >
        <table>
          <thead>
            <tr>
              <th
                v-for="(cell, n) in block.header"
                :key="n"
              >
                <MarkdownSpans :spans="cell" />
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(row, r) in block.rows"
              :key="r"
            >
              <td
                v-for="(cell, n) in row"
                :key="n"
              >
                <MarkdownSpans :spans="cell" />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>

<style scoped>
.md :deep(h2) {
  font-size: 1.35rem;
  margin-top: 1.8em;
}

.md :deep(h3) {
  margin-top: 1.4em;
}

blockquote {
  margin: 0 0 1.2em;
  padding: 14px 18px;
  border-radius: 14px;
  background: var(--surface-alt);
}

ul,
ol {
  padding-left: 1.3em;
  margin: 0 0 1em;
}

li {
  margin-bottom: 0.4em;
}

.table {
  overflow-x: auto;
  margin-bottom: 1.2em;
}

table {
  border-collapse: collapse;
  width: 100%;
  font-size: 0.95rem;
}

th,
td {
  text-align: left;
  padding: 10px 12px;
  border-bottom: 1px solid var(--border);
}
</style>
