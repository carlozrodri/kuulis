import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Pressable, RefreshControl, SectionList, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import {
  Bell,
  Bike,
  Gauge,
  Gift,
  IdCard,
  type Icon,
  LifeBuoy,
  Megaphone,
  Receipt,
  ShieldAlert,
  User,
  Wallet,
} from '@/components/icons';
import { Button, Card, EmptyState, IconTile, Skeleton, TAB_BAR_SPACE, type Tone, Txt } from '@/components/ui';
import { markNotificationRead, NOTIFICATIONS_KEY } from '@/hooks/useNotifications';
import { api } from '@/lib/api';
import { type DayLabel, groupByDay, notificationKind, type NotificationKind } from '@/lib/notificationRoutes';
import type { AppNotification, Page } from '@/lib/types';
import { radius, space, useTheme } from '@/theme';

import { useOpenNotification } from './useOpenNotification';

const KIND_ICON: Record<NotificationKind, { icon: Icon; tone: Tone }> = {
  ride: { icon: Bike, tone: 'primary' },
  wallet: { icon: Wallet, tone: 'success' },
  subscription: { icon: Receipt, tone: 'warning' },
  support: { icon: LifeBuoy, tone: 'info' },
  safety: { icon: ShieldAlert, tone: 'danger' },
  campaign: { icon: Megaphone, tone: 'accent' },
  account: { icon: User, tone: 'neutral' },
  documents: { icon: IdCard, tone: 'primary' },
  referral: { icon: Gift, tone: 'accent' },
  quality: { icon: Gauge, tone: 'warning' },
  general: { icon: Bell, tone: 'neutral' },
};

/** Tab "Notificaciones": the inbox grouped by day; tapping an item marks it read and opens what it is about. */
export function InboxScreen() {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const queryClient = useQueryClient();
  const open = useOpenNotification();

  const { data, isLoading, refetch, isRefetching } = useQuery({
    queryKey: NOTIFICATIONS_KEY,
    queryFn: () => api<Page<AppNotification>>('/notifications', { query: { limit: 50 } }),
  });

  const markAll = useMutation({
    mutationFn: () => api('/notifications/read-all', { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: NOTIFICATIONS_KEY, exact: true }),
  });
  const items = data?.items;
  const hasUnread = !!items?.some((n) => !n.read_at);
  const sections = useMemo(
    () => groupByDay(items ?? []).map((group) => ({ key: group.key, label: group.label, data: group.items })),
    [items],
  );

  const dayTitle = (label: DayLabel) => {
    if (label.kind === 'today') return t('notifications.today');
    if (label.kind === 'yesterday') return t('notifications.yesterday');
    const sameYear = label.date.getFullYear() === new Date().getFullYear();
    return label.date.toLocaleDateString(i18n.language, {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
      ...(sameYear ? {} : { year: 'numeric' }),
    });
  };

  const onPress = (item: AppNotification) => {
    if (!item.read_at) void markNotificationRead(queryClient, item.id).catch(() => undefined);
    void open(item, 'inbox').catch(() => undefined);
  };

  return (
    <View style={{ flex: 1, backgroundColor: theme.background, paddingTop: insets.top }}>
      <SectionList
        sections={sections}
        keyExtractor={(item) => item.id}
        stickySectionHeadersEnabled={false}
        contentContainerStyle={{ paddingHorizontal: space.lg, paddingBottom: TAB_BAR_SPACE + insets.bottom, flexGrow: 1 }}
        refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={() => void refetch()} tintColor={theme.primary} />}
        ItemSeparatorComponent={() => <View style={{ height: space.sm }} />}
        ListHeaderComponent={
          <View style={styles.header}>
            <Txt variant="title" accessibilityRole="header">
              {t('tabs.notifications')}
            </Txt>
            {hasUnread ? (
              <Button
                title={t('notifications.markAll')}
                variant="ghost"
                size="sm"
                style={{ marginTop: 0 }}
                loading={markAll.isPending}
                onPress={() => markAll.mutate()}
              />
            ) : null}
          </View>
        }
        renderSectionHeader={({ section }) => (
          <Txt variant="overline" color="muted" accessibilityRole="header" style={styles.day}>
            {dayTitle(section.label)}
          </Txt>
        )}
        ListEmptyComponent={
          isLoading ? (
            <View style={{ gap: space.sm }}>
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} height={84} radius={radius.card} />
              ))}
            </View>
          ) : (
            <EmptyState icon={Bell} title={t('notifications.empty')} body={t('notifications.emptyBody')} />
          )
        }
        renderItem={({ item }) => {
          const unread = !item.read_at;
          const kind = KIND_ICON[notificationKind(item, item.category)];
          return (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={`${unread ? `${t('notifications.unread')}. ` : ''}${item.title}. ${item.body ?? ''}`}
              onPress={() => onPress(item)}
              style={({ pressed }) => ({ opacity: pressed ? 0.7 : 1 })}>
              <Card style={[styles.item, { opacity: unread ? 1 : 0.7 }]}>
                <IconTile icon={kind.icon} tone={kind.tone} size={40} />
                <View style={{ flex: 1, gap: 2 }}>
                  <Txt variant="bodyStrong">{item.title}</Txt>
                  {item.body ? <Txt color="muted">{item.body}</Txt> : null}
                  <Txt variant="caption" color="muted" style={{ marginTop: 4 }}>
                    {new Date(item.created_at).toLocaleTimeString(i18n.language, { hour: 'numeric', minute: '2-digit' })}
                  </Txt>
                </View>
                <View style={[styles.dot, { backgroundColor: unread ? theme.primary : 'transparent' }]} />
              </Card>
            </Pressable>
          );
        }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingTop: space.lg, paddingBottom: space.sm },
  day: { paddingTop: space.md, paddingBottom: space.sm },
  item: { flexDirection: 'row', gap: space.sm, padding: space.md },
  dot: { width: 10, height: 10, borderRadius: 5, marginTop: 6 },
});
