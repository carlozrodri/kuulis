/**
 * Tiny Markdown reader for the help center preview (doc 13): headings, paragraphs, bullet and numbered lists,
 * **bold**, *italic* and [links](https://…). It returns plain data rendered by MarkdownPreview with text
 * interpolation, so nothing typed in an article is ever injected as HTML.
 */

export interface MdInline {
  text: string
  bold?: boolean
  italic?: boolean
  href?: string
}

export type MdBlock
  = | { type: 'heading', level: 1 | 2 | 3, inlines: MdInline[] }
    | { type: 'paragraph', inlines: MdInline[] }
    | { type: 'list', ordered: boolean, items: MdInline[][] }

const SAFE_LINK = /^(https?:\/\/|mailto:|tel:)/i
const INLINE = /\[([^\]]+)\]\(([^)\s]+)\)|\*\*([^*]+)\*\*|\*([^*]+)\*|_([^_]+)_/g

export function parseInline(text: string): MdInline[] {
  const out: MdInline[] = []
  let last = 0
  const push = (piece: MdInline) => {
    if (piece.text) out.push(piece)
  }
  for (const match of text.matchAll(INLINE)) {
    const index = match.index ?? 0
    push({ text: text.slice(last, index) })
    const [whole, linkText, href, bold, italic, italicUnderscore] = match
    if (linkText !== undefined && href !== undefined) {
      // Unsafe schemes (javascript:, data:) stay as plain text.
      push(SAFE_LINK.test(href) ? { text: linkText, href } : { text: whole })
    }
    else if (bold !== undefined) push({ text: bold, bold: true })
    else push({ text: italic ?? italicUnderscore ?? '', italic: true })
    last = index + whole.length
  }
  push({ text: text.slice(last) })
  return out
}

const HEADING = /^(#{1,3})\s+(.*)$/
const BULLET = /^\s*[-*+]\s+(.*)$/
const NUMBERED = /^\s*\d+[.)]\s+(.*)$/

export function parseMarkdown(source: string): MdBlock[] {
  const blocks: MdBlock[] = []
  let paragraph: string[] = []
  let list: { ordered: boolean, items: MdInline[][] } | null = null

  const flushParagraph = () => {
    if (paragraph.length) blocks.push({ type: 'paragraph', inlines: parseInline(paragraph.join(' ')) })
    paragraph = []
  }
  const flushList = () => {
    if (list) blocks.push({ type: 'list', ...list })
    list = null
  }

  for (const raw of source.replace(/\r\n?/g, '\n').split('\n')) {
    const line = raw.trimEnd()
    if (!line.trim()) {
      flushParagraph()
      flushList()
      continue
    }
    const heading = HEADING.exec(line)
    if (heading) {
      flushParagraph()
      flushList()
      blocks.push({ type: 'heading', level: heading[1]!.length as 1 | 2 | 3, inlines: parseInline(heading[2]!.trim()) })
      continue
    }
    const bullet = BULLET.exec(line)
    const numbered = bullet ? null : NUMBERED.exec(line)
    const item = bullet ?? numbered
    if (item) {
      flushParagraph()
      const ordered = !!numbered
      if (list && list.ordered !== ordered) flushList()
      if (!list) list = { ordered, items: [] }
      list.items.push(parseInline(item[1]!.trim()))
      continue
    }
    if (list) {
      // A wrapped line continues the last item.
      const items: MdInline[][] = list.items
      const lastItem = items[items.length - 1]!
      items[items.length - 1] = [...lastItem, { text: ' ' }, ...parseInline(line.trim())]
      continue
    }
    paragraph.push(line.trim())
  }
  flushParagraph()
  flushList()
  return blocks
}
