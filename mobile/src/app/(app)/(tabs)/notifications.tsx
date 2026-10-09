import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { FlatList, Pressable, RefreshControl, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Bell } from '@/components/icons';
import { Button, Card, EmptyState, Skeleton, TAB_BAR_SPACE, Txt } from '@/components/ui';
import { api } from '@/lib/api';
import type { AppNotification, Page } from '@/lib/types';
import { radius, space, useTheme } from '@/theme';

export default function NotificationsScreen() {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const queryClient = useQueryClient();

  const { data, isLoading, refetch, isRefetching } = useQuery({
    queryKey: ['notifications'],
    queryFn: () => api<Page<AppNotification>>('/notifications', { query: { limit: 50 } }),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['notifications'] });
  const markRead = useMutation({
    mutationFn: (id: string) => api(`/notifications/${id}/read`, { method: 'POST' }),
    onSuccess: invalidate,
  });
  const markAll = useMutation({
    mutationFn: () => api('/notifications/read-all', { method: 'POST' }),
    onSuccess: invalidate,
  });
  const hasUnread = !!data?.items.some((n) => !n.read_at);

  return (
    <View style={{ flex: 1, backgroundColor: theme.background, paddingTop: insets.top }}>
      <FlatList
        data={data?.items ?? []}
        keyExtractor={(item) => item.id}
        contentContainerStyle={{ paddingHorizontal: space.lg, paddingBottom: TAB_BAR_SPACE + insets.bottom, gap: space.sm, flexGrow: 1 }}
        refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} tintColor={theme.primary} />}
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
          return (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={`${unread ? `${t('notifications.unread')}. ` : ''}${item.title}. ${item.body ?? ''}`}
              onPress={() => unread && markRead.mutate(item.id)}>
              <Card style={[styles.item, { opacity: unread ? 1 : 0.7 }]}>
                <View style={[styles.dot, { backgroundColor: unread ? theme.primary : 'transparent' }]} />
                <View style={{ flex: 1, gap: 2 }}>
                  <Txt variant="bodyStrong">{item.title}</Txt>
                  {item.body ? <Txt color="muted">{item.body}</Txt> : null}
                  <Txt variant="caption" color="muted" style={{ marginTop: 4 }}>
                    {new Date(item.created_at).toLocaleString(i18n.language, { dateStyle: 'medium', timeStyle: 'short' })}
                  </Txt>
                </View>
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
  item: { flexDirection: 'row', gap: space.sm, padding: space.md },
  dot: { width: 10, height: 10, borderRadius: 5, marginTop: 6 },
});
