/**
 * Legal texts (doc 07): kinds, who accepts what, and a small Markdown parser for the texts the API
 * serves (headings, paragraphs, lists, quotes and tables, with **bold**). Pure, so it is unit tested.
 */

export type LegalKind = 'terms' | 'privacy' | 'community' | 'driver_terms' | 'wallet';

export const LEGAL_KINDS: LegalKind[] = ['terms', 'privacy', 'community', 'driver_terms', 'wallet'];
export const DRIVER_KINDS: LegalKind[] = ['driver_terms', 'wallet'];

export function isLegalKind(value: unknown): value is LegalKind {
  return typeof value === 'string' && (LEGAL_KINDS as string[]).includes(value);
}

export type LegalDocument = {
  kind: LegalKind;
  version: number;
  locale: string;
  title: string;
  body_md: string;
  summary: string;
  requires_reacceptance: boolean;
  published_at: string;
};

export type LegalSummary = Omit<LegalDocument, 'body_md'>;

/** A run of text, bold or not. */
export type Span = { text: string; bold: boolean };

export type Block =
  | { type: 'heading'; level: 2 | 3; spans: Span[] }
  | { type: 'paragraph'; spans: Span[] }
  | { type: 'quote'; spans: Span[] }
  | { type: 'list'; ordered: boolean; items: Span[][] }
  | { type: 'table'; header: Span[][]; rows: Span[][][] };

export function parseInline(text: string): Span[] {
  const spans: Span[] = [];
  text.split(/(\*\*[^*]+\*\*)/).forEach((part) => {
    if (!part) return;
    const bold = part.startsWith('**') && part.endsWith('**') && part.length > 4;
    spans.push({ text: bold ? part.slice(2, -2) : part, bold });
  });
  return spans;
}

const cells = (line: string) =>
  line
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map((cell) => parseInline(cell.trim()));

/** Lines that continue the previous one are joined, as Markdown does. */
export function parseMarkdown(source: string): Block[] {
  const blocks: Block[] = [];
  const lines = source.replace(/\r\n/g, '\n').split('\n');
  let i = 0;
  const take = (test: (line: string) => boolean) => {
    const taken: string[] = [];
    while (i < lines.length && test(lines[i])) taken.push(lines[i++]);
    return taken;
  };
  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();
    if (!trimmed) {
      i++;
    } else if (/^#{1,3}\s/.test(trimmed)) {
      const level = trimmed.startsWith('###') ? 3 : 2;
      blocks.push({ type: 'heading', level, spans: parseInline(trimmed.replace(/^#+\s*/, '')) });
      i++;
    } else if (trimmed.startsWith('>')) {
      const text = take((l) => l.trim().startsWith('>'))
        .map((l) => l.trim().replace(/^>\s?/, ''))
        .join(' ');
      blocks.push({ type: 'quote', spans: parseInline(text) });
    } else if (trimmed.startsWith('|')) {
      const rows = take((l) => l.trim().startsWith('|')).filter((l) => !/^\|?\s*:?-{2,}/.test(l.trim()));
      const [header, ...body] = rows.map(cells);
      blocks.push({ type: 'table', header: header ?? [], rows: body });
    } else if (/^([-*]|\d+\.)\s/.test(trimmed)) {
      const ordered = /^\d+\./.test(trimmed);
      const items: string[] = [];
      while (i < lines.length && lines[i].trim()) {
        const current = lines[i].trim();
        if (/^([-*]|\d+\.)\s/.test(current)) items.push(current.replace(/^([-*]|\d+\.)\s+/, ''));
        else if (items.length) items[items.length - 1] += ` ${current}`;
        i++;
      }
      blocks.push({ type: 'list', ordered, items: items.map(parseInline) });
    } else {
      const text = take(
        (l) => !!l.trim() && !/^(#{1,3}\s|>|\||[-*]\s|\d+\.\s)/.test(l.trim()),
      ).join(' ');
      if (!text) i++; // a line no rule takes (never expected): skip it instead of looping
      else blocks.push({ type: 'paragraph', spans: parseInline(text.trim()) });
    }
  }
  return blocks;
}
