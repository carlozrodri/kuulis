import { useQuery } from '@tanstack/react-query';
import { Tabs } from 'expo-router';
import { useTranslation } from 'react-i18next';

import { TabBar } from '@/components/TabBar';
import { api } from '@/lib/api';
import type { AppNotification, Page } from '@/lib/types';
import { useTheme } from '@/theme';

export default function TabsLayout() {
  const { t } = useTranslation();
  const theme = useTheme();

  const { data } = useQuery({
    queryKey: ['notifications'],
    queryFn: () => api<Page<AppNotification>>('/notifications', { query: { limit: 50 } }),
  });
  const unread = !!data?.items.some((n) => !n.read_at);

  return (
    <Tabs
      tabBar={(props) => <TabBar {...props} badges={{ notifications: unread }} />}
      screenOptions={{ headerShown: false, sceneStyle: { backgroundColor: theme.background } }}>
      <Tabs.Screen name="index" options={{ title: t('tabs.home') }} />
      <Tabs.Screen name="rides" options={{ title: t('tabs.rides') }} />
      <Tabs.Screen name="notifications" options={{ title: t('tabs.notifications') }} />
      <Tabs.Screen name="profile" options={{ title: t('tabs.profile') }} />
    </Tabs>
  );
}
