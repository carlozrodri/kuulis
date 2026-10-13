import { router } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { Pressable, StyleSheet, View } from 'react-native';

import {
  Banknote,
  Bike,
  ChevronRight,
  FileText,
  type Icon,
  ShieldCheck,
  Smartphone,
  User,
  Wallet,
} from '@/components/icons';
import { Txt } from '@/components/ui';
import type { HelpArticleSummary, HelpTopic } from '@/lib/types';
import { radius, space, useTheme } from '@/theme';

export const TOPIC_ICONS: Record<HelpTopic, Icon> = {
  account: User,
  rides: Bike,
  payments: Banknote,
  wallet: Wallet,
  safety: ShieldCheck,
  documents: FileText,
  app: Smartphone,
};

export const openArticle = (slug: string) => router.push({ pathname: '/help/article/[slug]', params: { slug } });

/** One article in a list: title and its short excerpt. */
export function ArticleRow({ article, divider }: { article: HelpArticleSummary; divider?: boolean }) {
  const theme = useTheme();
  const { t } = useTranslation();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={article.title}
      accessibilityHint={t('help.openArticleHint')}
      onPress={() => openArticle(article.slug)}
      style={({ pressed }) => [
        styles.row,
        divider && { borderBottomWidth: 1, borderBottomColor: theme.divider },
        { opacity: pressed ? 0.6 : 1 },
      ]}>
      <View style={{ flex: 1, gap: 2 }}>
        <Txt variant="bodyStrong">{article.title}</Txt>
        {article.excerpt ? (
          <Txt variant="caption" color="muted" numberOfLines={2}>
            {article.excerpt}
          </Txt>
        ) : null}
      </View>
      <ChevronRight size={20} color={theme.muted} strokeWidth={2.2} />
    </Pressable>
  );
}

/** Articles inside a card, one per row. */
export function ArticleList({ articles }: { articles: HelpArticleSummary[] }) {
  const theme = useTheme();
  return (
    <View style={[styles.card, { backgroundColor: theme.surface }]}>
      {articles.map((article, index) => (
        <ArticleRow key={article.id} article={article} divider={index < articles.length - 1} />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: space.sm, paddingVertical: space.sm, minHeight: 56 },
  card: { borderRadius: radius.card, paddingHorizontal: space.md, paddingVertical: space.xxs },
});
