import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { FlatList, Pressable, RefreshControl, StyleSheet, Text, View } from 'react-native';

import { Body, Button, Screen, Title } from '@/components/ui';
import { api } from '@/lib/api';
import type { AppNotification, Page } from '@/lib/types';
import { useTheme } from '@/theme';

export default function NotificationsScreen() {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
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

  return (
    <Screen>
      <Title>{t('tabs.notifications')}</Title>
      {!!data?.items.some((n) => !n.read_at) && (
        <Button title={t('notifications.markAll')} variant="ghost" onPress={() => markAll.mutate()} />
      )}
      <FlatList
        data={data?.items ?? []}
        keyExtractor={(item) => item.id}
        refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} />}
        ListEmptyComponent={isLoading ? <Body muted>{t('common.loading')}</Body> : <Body muted>{t('notifications.empty')}</Body>}
        renderItem={({ item }) => (
          <Pressable onPress={() => !item.read_at && markRead.mutate(item.id)}>
            <View style={[styles.item, { borderColor: theme.border, opacity: item.read_at ? 0.6 : 1 }]}>
              <Text style={[styles.itemTitle, { color: theme.text }]}>{item.title}</Text>
              {!!item.body && <Text style={{ color: theme.muted }}>{item.body}</Text>}
              <Text style={[styles.date, { color: theme.muted }]}>
                {new Date(item.created_at).toLocaleString(i18n.language)}
              </Text>
            </View>
          </Pressable>
        )}
      />
    </Screen>
  );
}

const styles = StyleSheet.create({
  item: { paddingVertical: 12, borderBottomWidth: StyleSheet.hairlineWidth, gap: 4 },
  itemTitle: { fontSize: 16, fontWeight: '600' },
  date: { fontSize: 12 },
});
