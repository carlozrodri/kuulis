import { router } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { ActivityIndicator, FlatList, RefreshControl, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { CircleX, Route } from '@/components/icons';
import { Button, Card, EmptyState, Skeleton, StatusPill, TAB_BAR_SPACE, type Tone, Txt } from '@/components/ui';
import { useRideHistory } from '@/hooks/useRides';
import { apiErrorMessage } from '@/i18n';
import { formatFare } from '@/lib/ride';
import type { Ride, RideStatus } from '@/lib/types';
import { useMode } from '@/providers/ModeProvider';
import { radius, space, useTheme } from '@/theme';

import { PlaceRows } from './components';

export const STATUS_TONE: Record<RideStatus, Tone> = {
  searching: 'info',
  driver_assigned: 'info',
  driver_arrived: 'accent',
  in_progress: 'primary',
  completed: 'success',
  cancelled_by_passenger: 'neutral',
  cancelled_by_driver: 'danger',
  cancelled_by_admin: 'danger',
  no_drivers: 'warning',
};

/** "Tus viajes": the user's rides in the current mode (passenger or driver). */
export function HistoryScreen() {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const { mode } = useMode();
  const role = mode === 'driver' ? 'driver' : 'passenger';
  const history = useRideHistory(role);
  const rides = history.data?.pages.flatMap((page) => page.items) ?? [];

  const renderItem = ({ item }: { item: Ride }) => {
    const date = new Date(item.requested_at);
    return (
      <Card
        onPress={() => router.push({ pathname: '/ride/detail', params: { id: item.id } })}
        accessibilityLabel={`${date.toLocaleString(i18n.language)}. ${t(`ride.status.${item.status}`)}. ${item.dropoff.address}. ${formatFare(item.fare)}`}
        style={styles.item}>
        <View style={styles.itemTop}>
          <Txt variant="label" color="muted" style={{ flex: 1 }}>
            {date.toLocaleDateString(i18n.language, { weekday: 'short', day: 'numeric', month: 'short' })} ·{' '}
            {date.toLocaleTimeString(i18n.language, { hour: '2-digit', minute: '2-digit' })}
          </Txt>
          <Txt variant="subtitle" tabular style={{ opacity: item.status === 'completed' ? 1 : 0.5 }}>
            {formatFare(item.fare)}
          </Txt>
        </View>
        <PlaceRows pickup={item.pickup} dropoff={item.dropoff} compact />
        <StatusPill label={t(`ride.status.${item.status}`)} tone={STATUS_TONE[item.status] ?? 'neutral'} />
      </Card>
    );
  };

  return (
    <View style={{ flex: 1, backgroundColor: theme.background, paddingTop: insets.top }}>
      <FlatList
        data={rides}
        keyExtractor={(item) => item.id}
        renderItem={renderItem}
        contentContainerStyle={{ paddingHorizontal: space.lg, paddingBottom: TAB_BAR_SPACE + insets.bottom, gap: space.sm, flexGrow: 1 }}
        refreshControl={<RefreshControl refreshing={history.isRefetching && !history.isFetchingNextPage} onRefresh={() => void history.refetch()} tintColor={theme.primary} />}
        onEndReachedThreshold={0.4}
        onEndReached={() => {
          if (history.hasNextPage && !history.isFetchingNextPage) void history.fetchNextPage();
        }}
        ListHeaderComponent={
          <View style={{ paddingTop: space.lg, paddingBottom: space.sm }}>
            <Txt variant="title" accessibilityRole="header">
              {t('history.title')}
            </Txt>
            <Txt color="muted">{role === 'driver' ? t('history.subtitleDriver') : t('history.subtitlePassenger')}</Txt>
          </View>
        }
        ListFooterComponent={history.isFetchingNextPage ? <ActivityIndicator color={theme.primary} style={{ margin: space.md }} /> : null}
        ListEmptyComponent={
          history.isPending ? (
            <View style={{ gap: space.sm }}>
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} height={150} radius={radius.card} />
              ))}
            </View>
          ) : history.isError ? (
            <View>
              <EmptyState icon={CircleX} title={t('common.error')} body={apiErrorMessage(history.error)} />
              <Button title={t('common.retry')} variant="secondary" onPress={() => void history.refetch()} />
            </View>
          ) : (
            <EmptyState icon={Route} title={t('history.empty')} body={role === 'driver' ? t('history.emptyDriver') : t('history.emptyPassenger')} />
          )
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  item: { gap: space.sm, padding: space.md },
  itemTop: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
});
