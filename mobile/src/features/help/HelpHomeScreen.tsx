import { router } from 'expo-router';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Linking, Pressable, StyleSheet, View } from 'react-native';

import { ErrorState } from '@/components/ErrorState';
import {
  ChevronRight,
  Flag,
  Mail,
  MessageCircle,
  MessagesSquare,
  PhoneCall,
  Search,
  SearchX,
} from '@/components/icons';
import { Button, Card, EmptyState, Field, ListRow, Screen, Skeleton, StatusPill, Txt } from '@/components/ui';
import { callEmergency } from '@/features/reports/components';
import { FlowHeader } from '@/features/wallet/components';
import { useAppLinks } from '@/hooks/useBootstrap';
import { useAppConfig } from '@/hooks/useDriver';
import { useDebounced, useHelpArticles } from '@/hooks/useHelp';
import { useMyReports } from '@/hooks/useReports';
import { apiErrorMessage } from '@/i18n';
import { supportWhatsappUrl } from '@/lib/bootstrap';
import { groupByTopic, responsePromise, searchTerm, unreadCount } from '@/lib/support';
import { radius, space, useTheme } from '@/theme';

import { ArticleList, TOPIC_ICONS } from './components';

function leave() {
  if (router.canGoBack()) router.back();
  else router.replace('/profile');
}

/**
 * Ayuda (doc 13): search, topics with the articles for this mode (passenger or driver), "Mis conversaciones",
 * contact (with the configured response promise), WhatsApp when configured, and the emergency number.
 */
export function HelpHomeScreen() {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const [query, setQuery] = useState('');
  const term = useDebounced(searchTerm(query));
  const all = useHelpArticles();
  const results = useHelpArticles({ q: term });
  const reports = useMyReports();
  const { config } = useAppConfig();
  const links = useAppLinks();
  const whatsapp = supportWhatsappUrl(links.support_whatsapp);
  const email = links.support_email;

  const groups = groupByTopic(all.data ?? []);
  const unread = unreadCount(reports.data?.pages.flatMap((page) => page.items) ?? []);
  const searching = !!searchTerm(query);

  return (
    <Screen header={<FlowHeader title={t('help.title')} subtitle={t('help.subtitle')} onBack={leave} />}>
      <View style={{ gap: space.md }}>
        <Field
          label={t('help.searchLabel')}
          placeholder={t('help.searchPlaceholder')}
          icon={Search}
          value={query}
          onChangeText={setQuery}
          returnKeyType="search"
          autoCorrect={false}
          clearButtonMode="while-editing"
        />

        {searching ? (
          <View style={{ gap: space.sm }} accessibilityLiveRegion="polite">
            <Txt variant="overline" color="muted">
              {t('help.results')}
            </Txt>
            {!term || (results.isFetching && !results.data?.length) ? (
              <View style={{ gap: space.sm }}>
                <Skeleton height={64} radius={radius.card} />
                <Skeleton height={64} radius={radius.card} />
              </View>
            ) : results.isError ? (
              <Txt color="danger">{apiErrorMessage(results.error)}</Txt>
            ) : results.data?.length ? (
              <ArticleList articles={results.data} />
            ) : (
              <View>
                <EmptyState icon={SearchX} title={t('help.noResults', { query: term })} body={t('help.noResultsBody')} />
                <Button title={t('help.contact')} variant="secondary" icon={Flag} onPress={() => router.push('/report')} />
              </View>
            )}
          </View>
        ) : (
          <View style={{ gap: space.sm }}>
            <Txt variant="overline" color="muted">
              {t('help.topics')}
            </Txt>
            {all.isPending ? (
              <View style={styles.grid}>
                {[0, 1, 2, 3].map((i) => (
                  <Skeleton key={i} height={92} radius={radius.card} style={styles.tileSkeleton} />
                ))}
              </View>
            ) : all.isError ? (
              <ErrorState error={all.error} onRetry={() => all.refetch()} />
            ) : groups.length ? (
              <View style={styles.grid}>
                {groups.map(({ topic, articles }) => {
                  const TopicIcon = TOPIC_ICONS[topic];
                  const label = t(`help.topic.${topic}`);
                  const count = t('help.articleCount', { count: articles.length });
                  return (
                    <Pressable
                      key={topic}
                      accessibilityRole="button"
                      accessibilityLabel={`${label}. ${count}`}
                      onPress={() => router.push({ pathname: '/help/topic/[topic]', params: { topic } })}
                      style={({ pressed }) => [
                        styles.tile,
                        { backgroundColor: theme.surface, transform: [{ scale: pressed ? 0.97 : 1 }] },
                      ]}>
                      <View style={[styles.tileIcon, { backgroundColor: theme.surfaceAlt }]}>
                        <TopicIcon size={22} color={theme.primary} strokeWidth={2.2} />
                      </View>
                      <Txt variant="bodyStrong" numberOfLines={2}>
                        {label}
                      </Txt>
                      <Txt variant="caption" color="muted">
                        {count}
                      </Txt>
                    </Pressable>
                  );
                })}
              </View>
            ) : (
              <Txt color="muted">{t('help.noArticles')}</Txt>
            )}
          </View>
        )}

        <Txt variant="overline" color="muted" style={{ marginTop: space.sm }}>
          {t('help.contactSection')}
        </Txt>
        <Card style={{ paddingVertical: space.xxs }}>
          <ListRow
            icon={MessagesSquare}
            title={t('reports.title')}
            subtitle={unread ? t('help.unread', { count: unread }) : t('help.conversationsHint')}
            right={unread ? <StatusPill label={String(unread)} tone="primary" dot /> : null}
            accessibilityLabel={unread ? `${t('reports.title')}. ${t('help.unread', { count: unread })}` : t('reports.title')}
            divider
            onPress={() => router.push('/reports')}
          />
          <ListRow
            icon={Flag}
            title={t('help.contact')}
            subtitle={responsePromise(config, i18n.language)}
            divider={!!(whatsapp || email)}
            onPress={() => router.push('/report')}
          />
          {whatsapp ? (
            <ListRow
              icon={MessageCircle}
              iconTone="success"
              title={t('reports.support.whatsapp')}
              subtitle={t('reports.support.whatsappHint')}
              divider={!!email}
              onPress={() => void Linking.openURL(whatsapp).catch(() => undefined)}
            />
          ) : null}
          {email ? (
            <ListRow
              icon={Mail}
              iconTone="neutral"
              title={t('reports.support.email')}
              subtitle={email}
              onPress={() => void Linking.openURL(`mailto:${email}`).catch(() => undefined)}
            />
          ) : null}
        </Card>
        <Card style={{ paddingVertical: space.xxs }}>
          <ListRow
            icon={PhoneCall}
            iconTone="danger"
            title={t('reports.emergency')}
            subtitle={t('reports.emergencyHint', { number: links.emergency })}
            onPress={callEmergency}
          />
        </Card>
        <Pressable
          accessibilityRole="button"
          onPress={() => router.push('/rides')}
          style={({ pressed }) => [styles.hint, { backgroundColor: theme.surface, opacity: pressed ? 0.7 : 1 }]}>
          <Txt variant="caption" color="muted" style={{ flex: 1 }}>
            {t('help.rideHint')}
          </Txt>
          <ChevronRight size={18} color={theme.muted} strokeWidth={2.2} />
        </Pressable>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: space.sm },
  tile: { width: '48%', flexGrow: 1, borderRadius: radius.card, padding: space.md, gap: space.xxs, minHeight: 112 },
  tileSkeleton: { width: '48%', flexGrow: 1 },
  tileIcon: { width: 40, height: 40, borderRadius: 12, alignItems: 'center', justifyContent: 'center', marginBottom: space.xxs },
  hint: { flexDirection: 'row', alignItems: 'center', gap: space.sm, borderRadius: radius.tile, padding: space.md },
});
