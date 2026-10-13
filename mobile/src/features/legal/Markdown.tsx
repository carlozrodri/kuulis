import { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';

import { Txt, type TxtProps } from '@/components/ui';
import { parseMarkdown, type Span } from '@/lib/legal';
import { fonts, radius, space, useTheme } from '@/theme';

type LinkHandler = (href: string) => void;

function Spans({ spans, onLink, ...props }: { spans: Span[]; onLink?: LinkHandler } & Omit<TxtProps, 'children'>) {
  const theme = useTheme();
  return (
    <Txt {...props}>
      {spans.map((span, index) =>
        span.href ? (
          <Txt
            key={index}
            variant={props.variant}
            accessibilityRole="link"
            onPress={() => onLink?.(span.href!)}
            style={[styles.link, { color: theme.scheme === 'dark' ? theme.primary : theme.primaryPressed }, span.bold && styles.bold]}>
            {span.text}
          </Txt>
        ) : span.bold ? (
          <Txt key={index} variant={props.variant} color={props.color} style={styles.bold}>
            {span.text}
          </Txt>
        ) : (
          span.text
        ),
      )}
    </Txt>
  );
}

/**
 * Renders the legal texts' and help articles' Markdown (lib/legal parseMarkdown) with the app's type scale.
 * Links call `onLink` (they are plain text without it).
 */
export function Markdown({ source, onLink }: { source: string; onLink?: LinkHandler }) {
  const theme = useTheme();
  const blocks = useMemo(() => parseMarkdown(source), [source]);
  return (
    <View style={{ gap: space.sm }}>
      {blocks.map((block, index) => {
        switch (block.type) {
          case 'heading':
            return (
              <Spans
                key={index}
                spans={block.spans}
                onLink={onLink}
                variant={block.level === 2 ? 'subtitle' : 'bodyStrong'}
                accessibilityRole="header"
                style={{ marginTop: space.sm }}
              />
            );
          case 'quote':
            return (
              <View key={index} style={[styles.quote, { backgroundColor: theme.warningSoft, borderColor: theme.warning }]}>
                <Spans spans={block.spans} onLink={onLink} variant="caption" />
              </View>
            );
          case 'list':
            return (
              <View key={index} style={{ gap: space.xs }}>
                {block.items.map((item, n) => (
                  <View key={n} style={styles.item}>
                    <Txt color="muted" style={styles.bullet}>
                      {block.ordered ? `${n + 1}.` : '•'}
                    </Txt>
                    <Spans spans={item} onLink={onLink} style={styles.flex} />
                  </View>
                ))}
              </View>
            );
          case 'table':
            return (
              <View key={index} style={[styles.table, { borderColor: theme.border }]}>
                {[block.header, ...block.rows].map((row, r) => (
                  <View
                    key={r}
                    style={[
                      styles.tableRow,
                      { borderColor: theme.border, backgroundColor: r === 0 ? theme.surfaceAlt : theme.surface },
                    ]}>
                    {row.map((cell, c) => (
                      <Spans key={c} spans={cell} onLink={onLink} variant={r === 0 ? 'label' : 'caption'} style={styles.cell} />
                    ))}
                  </View>
                ))}
              </View>
            );
          default:
            return <Spans key={index} spans={block.spans} onLink={onLink} />;
        }
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  bold: { fontFamily: fonts.bold },
  link: { fontFamily: fonts.semibold, textDecorationLine: 'underline' },
  quote: { borderLeftWidth: 3, borderRadius: radius.field, padding: space.sm },
  item: { flexDirection: 'row', gap: space.xs },
  bullet: { minWidth: 18 },
  table: { borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.field, overflow: 'hidden' },
  tableRow: { flexDirection: 'row', borderTopWidth: StyleSheet.hairlineWidth },
  cell: { flex: 1, padding: space.xs },
});
