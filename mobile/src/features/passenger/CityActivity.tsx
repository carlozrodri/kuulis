import { useTranslation } from 'react-i18next';
import { ScrollView, StyleSheet, View } from 'react-native';

import { HandCoins, X } from '@/components/icons';
import { Illustration } from '@/components/illustrations';
import { Pop, Rise } from '@/components/motion';
import { IconButton, Txt } from '@/components/ui';
import { formatDistance, formatFare } from '@/lib/ride';
import type { ActiveTrip, PublicActivity } from '@/lib/types';
import { ON_NAV, radius, space, useTheme } from '@/theme';

/**
 * "Caracas en movimiento" on the passenger home (docs/product/wow/01-mapa-vivo.md, part B). Everything here
 * is real: trips in progress (on the map) and finished ones (the strip), anonymous. Below the admin
 * threshold there is no layer, only the honest line with the real number of verified drivers.
 */
export function ActivityStrip({ activity }: { activity: PublicActivity | undefined }) {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  if (!activity) return null;

  if (!activity.live) {
    return (
      <Rise style={[styles.honest, { backgroundColor: theme.surfaceAlt }]}>
        <Illustration name="moto" size={64} />
        <View style={{ flex: 1, gap: 2 }}>
          <Txt variant="bodyStrong">{t('home.activity.startingTitle')}</Txt>
          <Txt variant="caption" color="muted" style={styles.caption}>
            {activity.verified_drivers > 0
              ? t('home.activity.startingBody', { n: activity.verified_drivers })
              : t('home.activity.startingBodyNone')}
          </Txt>
        </View>
      </Rise>
    );
  }

  return (
    <Rise style={{ gap: space.sm }}>
      <View style={styles.header}>
        <View style={[styles.live, { backgroundColor: theme.success }]} />
        <Txt variant="subtitle" accessibilityRole="header">
          {t('home.activity.title')}
        </Txt>
        <Txt variant="caption" color="muted" style={{ marginLeft: 'auto' }}>
          {t('home.activity.lastHour', { n: activity.trips_last_hour })}
        </Txt>
      </View>
      {activity.recent.length ? (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: space.sm }}>
          {activity.recent.map((trip, index) => (
            <View
              // Recent trips have no id on purpose; their order is stable within the 30 s cache.
              key={`${index}-${trip.minutes_ago}-${trip.fare}`}
              accessible
              accessibilityLabel={t('home.activity.recentA11y', {
                minutes: trip.minutes_ago,
                distance: formatDistance(trip.distance_m, i18n.language),
                fare: formatFare(trip.fare),
              })}
              style={[styles.chip, { backgroundColor: theme.surfaceAlt }]}>
              <Txt variant="caption" color="muted">
                {t('home.activity.minutesAgo', { minutes: trip.minutes_ago })}
              </Txt>
              <Txt variant="bodyStrong" tabular>
                {formatFare(trip.fare)}
                <Txt variant="caption" color="muted">
                  {'  '}
                  {formatDistance(trip.distance_m, i18n.language)}
                </Txt>
              </Txt>
            </View>
          ))}
        </ScrollView>
      ) : null}
      <Txt variant="caption" color="muted" style={styles.caption}>
        {t('home.activity.privacy')}
      </Txt>
    </Rise>
  );
}

/** The card shown when a moving moto on the map is tapped. */
export function ActivityTripCard({ trip, onClose }: { trip: ActiveTrip; onClose: () => void }) {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  return (
    <Pop trigger={trip.id} style={[styles.card, { backgroundColor: theme.nav }]}>
      <View style={{ flex: 1, gap: 2 }}>
        <Txt variant="caption" style={{ color: theme.accent }}>
          {t('home.activity.inProgress')}
        </Txt>
        <Txt variant="title" style={{ color: ON_NAV }} tabular>
          {formatFare(trip.fare)}
          <Txt variant="body" style={{ color: theme.navIcon }}>
            {'  ·  ~'}
            {formatDistance(trip.distance_m, i18n.language)}
          </Txt>
        </Txt>
        <View style={styles.full}>
          <HandCoins size={14} color={theme.accent} strokeWidth={2.4} />
          <Txt variant="caption" style={{ color: ON_NAV }}>
            {t('home.activity.allForDriver')}
          </Txt>
        </View>
      </View>
      <IconButton icon={X} label={t('common.close')} onPress={onClose} />
    </Pop>
  );
}

const styles = StyleSheet.create({
  honest: { flexDirection: 'row', alignItems: 'center', gap: space.md, padding: space.md, borderRadius: radius.card },
  header: { flexDirection: 'row', alignItems: 'center', gap: space.xs },
  live: { width: 8, height: 8, borderRadius: 4 },
  chip: { paddingHorizontal: space.md, paddingVertical: space.sm, borderRadius: radius.tile, gap: 2 },
  caption: { fontSize: 13, lineHeight: 18 },
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.md,
    padding: space.md,
    borderRadius: radius.card,
    marginHorizontal: space.md,
  },
  full: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 2 },
});
