import { router, useLocalSearchParams } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { RefreshControl, View } from 'react-native';

import { ErrorState } from '@/components/ErrorState';
import { BookOpen, Flag } from '@/components/icons';
import { Button, EmptyState, IconTile, Screen, Skeleton, Txt } from '@/components/ui';
import { FlowHeader } from '@/features/wallet/components';
import { useHelpArticles } from '@/hooks/useHelp';
import { isHelpTopic } from '@/lib/support';
import { radius, space, useTheme } from '@/theme';

import { ArticleList, TOPIC_ICONS } from './components';

function leave() {
  if (router.canGoBack()) router.back();
  else router.replace('/help');
}

/** One help topic: its articles for this mode, by position. */
export function HelpTopicScreen() {
  const { t } = useTranslation();
  const theme = useTheme();
  const params = useLocalSearchParams<{ topic: string }>();
  const topic = isHelpTopic(params.topic) ? params.topic : undefined;
  const articles = useHelpArticles({ topic });
  const items = topic ? (articles.data ?? []).filter((a) => a.topic === topic).sort((a, b) => a.position - b.position) : [];

  return (
    <Screen
      header={<FlowHeader title={topic ? t(`help.topic.${topic}`) : t('help.title')} onBack={leave} />}
      refreshControl={
        <RefreshControl refreshing={articles.isRefetching} onRefresh={() => void articles.refetch()} tintColor={theme.primary} />
      }>
      <View style={{ gap: space.md }}>
        {topic ? <IconTile icon={TOPIC_ICONS[topic]} size={56} /> : null}
        {articles.isPending ? (
          <View style={{ gap: space.sm }}>
            <Skeleton height={64} radius={radius.card} />
            <Skeleton height={64} radius={radius.card} />
            <Skeleton height={64} radius={radius.card} />
          </View>
        ) : articles.isError ? (
          <ErrorState error={articles.error} onRetry={() => articles.refetch()} />
        ) : items.length ? (
          <ArticleList articles={items} />
        ) : (
          <EmptyState icon={BookOpen} title={t('help.noArticles')} />
        )}
        <View style={{ gap: space.xs, marginTop: space.md }}>
          <Txt color="muted" align="center">
            {t('help.notFound')}
          </Txt>
          <Button title={t('help.contact')} variant="secondary" icon={Flag} onPress={() => router.push('/report')} />
        </View>
      </View>
    </Screen>
  );
}
