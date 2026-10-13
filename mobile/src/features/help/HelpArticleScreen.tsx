import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Linking, RefreshControl, StyleSheet, View } from 'react-native';

import { CircleX, Flag, ThumbsDown, ThumbsUp } from '@/components/icons';
import { Button, EmptyState, Screen, Skeleton, StatusPill, Txt } from '@/components/ui';
import { Markdown } from '@/features/legal/Markdown';
import { FlowHeader } from '@/features/wallet/components';
import { useHelpArticle, useHelpFeedback } from '@/hooks/useHelp';
import { apiErrorMessage } from '@/i18n';
import { selectionHaptic } from '@/lib/feedback';
import { articleLink } from '@/lib/support';
import { radius, space, useTheme } from '@/theme';

import { openArticle } from './components';

function leave() {
  if (router.canGoBack()) router.back();
  else router.replace('/help');
}

const openLink = (href: string) => {
  const link = articleLink(href);
  if (link?.kind === 'external') void Linking.openURL(link.url).catch(() => undefined);
  else if (link?.kind === 'article') openArticle(link.slug);
};

/** A help article (Markdown), "¿Te ayudó?" and "Contactar a soporte" with the article as context. */
export function HelpArticleScreen() {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const { slug } = useLocalSearchParams<{ slug: string }>();
  const article = useHelpArticle(slug);
  const feedback = useHelpFeedback();
  const [answer, setAnswer] = useState<boolean | null>(null);
  const data = article.data;

  const vote = (helpful: boolean) => {
    if (!data || answer !== null) return;
    selectionHaptic();
    setAnswer(helpful);
    // Counted best effort: a rate limit or a network error does not bother the reader.
    feedback.mutate({ id: data.id, helpful });
  };

  const contact = () =>
    router.push({ pathname: '/report', params: data ? { help_article_id: data.id } : {} });

  return (
    <Screen
      header={<FlowHeader title={data?.title ?? t('help.title')} onBack={leave} />}
      refreshControl={
        <RefreshControl refreshing={article.isRefetching} onRefresh={() => void article.refetch()} tintColor={theme.primary} />
      }>
      {!data ? (
        article.isError ? (
          <View>
            <EmptyState icon={CircleX} title={t('common.error')} body={apiErrorMessage(article.error)} />
            <Button title={t('common.retry')} variant="secondary" onPress={() => void article.refetch()} />
          </View>
        ) : (
          <View style={{ gap: space.sm }}>
            <Skeleton height={18} width="40%" />
            <Skeleton height={120} radius={radius.card} />
            <Skeleton height={80} radius={radius.card} />
          </View>
        )
      ) : (
        <View style={{ gap: space.lg }}>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: space.xs, alignItems: 'center' }}>
            <StatusPill label={t(`help.topic.${data.topic}`, { defaultValue: data.topic })} tone="primary" />
            <Txt variant="caption" color="muted">
              {t('help.updated', {
                date: new Date(data.updated_at).toLocaleDateString(i18n.language, { day: 'numeric', month: 'long', year: 'numeric' }),
              })}
            </Txt>
          </View>

          <Markdown source={data.body_md} onLink={openLink} />

          <View style={[styles.card, { backgroundColor: theme.surface }]}>
            {answer === null ? (
              <>
                <Txt variant="subtitle" align="center">
                  {t('help.helpful.question')}
                </Txt>
                <View style={styles.votes}>
                  <Button title={t('help.helpful.yes')} variant="secondary" icon={ThumbsUp} style={styles.vote} onPress={() => vote(true)} />
                  <Button title={t('help.helpful.no')} variant="secondary" icon={ThumbsDown} style={styles.vote} onPress={() => vote(false)} />
                </View>
              </>
            ) : (
              <Txt align="center" accessibilityRole="alert">
                {answer ? t('help.helpful.thanksYes') : t('help.helpful.thanksNo')}
              </Txt>
            )}
          </View>

          <View style={{ gap: space.xs }}>
            <Txt color="muted" align="center">
              {t('help.stillNeed')}
            </Txt>
            <Button
              title={t('help.contact')}
              icon={Flag}
              variant={answer === false ? 'primary' : 'secondary'}
              accessibilityHint={t('help.contactHint')}
              onPress={contact}
            />
          </View>
        </View>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  card: { borderRadius: radius.card, padding: space.md, gap: space.sm },
  votes: { flexDirection: 'row', gap: space.sm },
  vote: { flex: 1 },
});
