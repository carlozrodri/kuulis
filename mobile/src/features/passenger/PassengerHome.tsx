import { router } from 'expo-router';
import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Pressable, StyleSheet, View } from 'react-native';

import { Bike, ChevronRight, Clock, Mail, Search } from '@/components/icons';
import { RideMap } from '@/components/map/RideMap';
import { MapSheetLayout } from '@/components/MapSheetLayout';
import { Button, Card, IconTile, ListRow, Notice, Txt, Wordmark } from '@/components/ui';
import { LocationPrompt } from '@/features/ride/LocationPrompt';
import { rideDraft, setDraftPlace } from '@/features/ride/store';
import { useCurrentPickup } from '@/features/ride/useCurrentPickup';
import { useUserLocation } from '@/hooks/useLocation';
import { useActiveRide, useRideHistory } from '@/hooks/useRides';
import { api } from '@/lib/api';
import { isActiveStatus, shortAddress } from '@/lib/ride';
import type { Place } from '@/lib/types';
import { useAuth } from '@/providers/AuthProvider';
import { elevation, radius, space, useTheme } from '@/theme';

export function greetingKey(date = new Date()) {
  const hour = date.getHours();
  if (hour < 12) return 'home.goodMorning';
  if (hour < 19) return 'home.goodAfternoon';
  return 'home.goodEvening';
}

export function firstName(fullName: string | null | undefined) {
  return fullName?.trim().split(/\s+/)[0] ?? '';
}

/** Recent destinations from the ride history, newest first, without duplicates. */
function useRecentDestinations(limit = 3): Place[] {
  const history = useRideHistory('passenger');
  return useMemo(() => {
    const seen = new Set<string>();
    const places: Place[] = [];
    for (const ride of history.data?.pages.flatMap((page) => page.items) ?? []) {
      const key = ride.dropoff.address.trim().toLowerCase();
      if (seen.has(key)) continue;
      seen.add(key);
      places.push(ride.dropoff);
      if (places.length >= limit) break;
    }
    return places;
  }, [history.data, limit]);
}

/** Passenger home: the map with "¿A dónde vamos?" on a bottom sheet. */
export function PassengerHome() {
  const { t } = useTranslation();
  const theme = useTheme();
  const { user } = useAuth();
  const [sent, setSent] = useState(false);
  const name = firstName(user?.full_name);
  const { permission } = useUserLocation();
  const active = useActiveRide();
  const recents = useRecentDestinations();
  useCurrentPickup();

  useEffect(() => {
    // Coming back home starts a fresh request from the current location.
    rideDraft.set((draft) => ({ ...draft, dropoff: null }));
  }, []);

  const activeRide = active.data && isActiveStatus(active.data.status) ? active.data : null;

  const goTo = (place: Place) => {
    setDraftPlace('dropoff', place);
    if (rideDraft.get().pickup) router.push('/ride/quote');
    else router.push({ pathname: '/ride/search', params: { field: 'pickup' } });
  };

  return (
    <MapSheetLayout
      map={(insets) => <RideMap insets={insets} followUser showUser />}
      topBar={
        <View style={[styles.brand, { backgroundColor: theme.surface }, elevation(theme)]}>
          <Wordmark size={22} />
        </View>
      }>
      <Txt variant="title" accessibilityRole="header">
        {name ? t('home.greetingName', { greeting: t(greetingKey()), name }) : t(greetingKey())}
      </Txt>

      {activeRide ? (
        <Card
          tone="tint"
          onPress={() => router.push({ pathname: '/ride', params: { id: activeRide.id } })}
          accessibilityLabel={t('home.activeRide')}
          style={styles.activeCard}>
          <IconTile icon={Bike} tone="primary" />
          <View style={{ flex: 1 }}>
            <Txt variant="bodyStrong">{t('home.activeRide')}</Txt>
            <Txt variant="caption" color="muted" numberOfLines={1}>
              {t(`ride.status.${activeRide.status}`)}
            </Txt>
          </View>
          <ChevronRight size={20} color={theme.muted} />
        </Card>
      ) : (
        <Pressable
          accessibilityRole="search"
          accessibilityLabel={t('home.whereTo')}
          accessibilityHint={t('home.whereToHint')}
          onPress={() => router.push({ pathname: '/ride/search', params: { field: 'dropoff' } })}
          style={({ pressed }) => [styles.search, { backgroundColor: theme.background, opacity: pressed ? 0.8 : 1 }]}>
          <Search size={22} color={theme.primary} strokeWidth={2.4} />
          <Txt variant="subtitle" style={{ flex: 1 }}>
            {t('home.whereTo')}
          </Txt>
          <View style={[styles.go, { backgroundColor: theme.primary }]}>
            <ChevronRight size={20} color={theme.onPrimary} strokeWidth={2.6} />
          </View>
        </Pressable>
      )}

      {permission !== 'granted' ? <LocationPrompt /> : null}

      {!activeRide && recents.length ? (
        <View>
          {recents.map((place, index) => (
            <ListRow
              key={`${place.lat},${place.lng}`}
              icon={Clock}
              iconTone="neutral"
              title={shortAddress(place.address)}
              subtitle={place.address}
              onPress={() => goTo(place)}
              divider={index < recents.length - 1}
            />
          ))}
        </View>
      ) : null}

      {!user?.is_verified ? (
        <Notice tone="warning" icon={Mail} title={t('home.verifyTitle')}>
          <Txt variant="caption" style={{ fontSize: 14, lineHeight: 20 }}>
            {sent ? t('home.verifySent') : t('home.verifyEmail')}
          </Txt>
          {!sent ? (
            <Button
              title={t('home.resend')}
              variant="secondary"
              size="sm"
              style={{ alignSelf: 'flex-start' }}
              onPress={() =>
                api('/auth/verify-email/resend', { method: 'POST' })
                  .then(() => setSent(true))
                  .catch(() => setSent(true))
              }
            />
          ) : null}
        </Notice>
      ) : null}
    </MapSheetLayout>
  );
}

const styles = StyleSheet.create({
  brand: { alignSelf: 'flex-start', borderRadius: radius.pill, paddingHorizontal: space.md, paddingVertical: space.xs },
  search: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.sm,
    height: 64,
    borderRadius: 20,
    paddingLeft: space.md,
    paddingRight: space.xs,
  },
  go: { width: 48, height: 48, borderRadius: 24, alignItems: 'center', justifyContent: 'center' },
  activeCard: { flexDirection: 'row', alignItems: 'center', gap: space.sm, padding: space.md },
});
