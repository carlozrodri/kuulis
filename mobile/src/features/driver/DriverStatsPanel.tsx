import { useTranslation } from 'react-i18next';
import { StyleSheet, View } from 'react-native';

import { Star } from '@/components/icons';
import { Card, Skeleton, Txt } from '@/components/ui';
import { formatFare } from '@/lib/ride';
import type { DriverStats, PeriodStats } from '@/lib/types';
import { radius, space, useTheme } from '@/theme';

/** Earnings at the top of the driver's "Tus viajes": today, yesterday, week, month and the last 7 days. */
export function DriverStatsPanel({ stats, loading }: { stats: DriverStats | undefined; loading: boolean }) {
  const { t, i18n } = useTranslation();
  const theme = useTheme();

  if (!stats) {
    return loading ? (
      <View style={{ gap: space.sm }}>
        <Skeleton height={112} radius={radius.card} />
        <Skeleton height={76} radius={radius.card} />
      </View>
    ) : null;
  }

  const rides = (period: PeriodStats) => t('stats.rides', { count: period.rides });
  const max = Math.max(...stats.by_day.map((day) => Number.parseFloat(day.earnings) || 0), 0);
  const weekday = (value: string) =>
    new Date(`${value}T12:00:00`).toLocaleDateString(i18n.language, { weekday: 'narrow' });

  return (
    <View style={{ gap: space.sm }}>
      <Card tone="tint" style={styles.today} accessibilityLabel={`${t('stats.today')}: ${formatFare(stats.today.earnings)}, ${rides(stats.today)}`}>
        <View style={{ flex: 1, gap: 2 }}>
          <Txt variant="label" color="muted">
            {t('stats.today')}
          </Txt>
          <Txt variant="display" tabular>
            {formatFare(stats.today.earnings)}
          </Txt>
          <Txt variant="caption" color="muted">
            {rides(stats.today)}
          </Txt>
        </View>
        <View style={styles.chart} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
          {stats.by_day.map((day, index) => {
            const value = Number.parseFloat(day.earnings) || 0;
            const today = index === stats.by_day.length - 1;
            return (
              <View key={day.date} style={styles.barColumn}>
                <View style={styles.barTrack}>
                  <View
                    style={[
                      styles.bar,
                      {
                        height: max > 0 ? `${Math.max((value / max) * 100, value > 0 ? 6 : 0)}%` : 0,
                        backgroundColor: today ? theme.primary : theme.border,
                      },
                    ]}
                  />
                </View>
                <Txt variant="micro" color={today ? 'text' : 'muted'}>
                  {weekday(day.date)}
                </Txt>
              </View>
            );
          })}
        </View>
      </Card>

      <View style={styles.grid}>
        {(
          [
            ['yesterday', stats.yesterday],
            ['week', stats.week],
            ['month', stats.month],
          ] as const
        ).map(([key, period]) => (
          <Card key={key} style={styles.tile} accessibilityLabel={`${t(`stats.${key}`)}: ${formatFare(period.earnings)}, ${rides(period)}`}>
            <Txt variant="label" color="muted" numberOfLines={1}>
              {t(`stats.${key}`)}
            </Txt>
            <Txt variant="subtitle" tabular numberOfLines={1}>
              {formatFare(period.earnings)}
            </Txt>
            <Txt variant="caption" color="muted" numberOfLines={1}>
              {rides(period)}
            </Txt>
          </Card>
        ))}
      </View>

      <View style={styles.footer}>
        <Txt variant="caption" color="muted" style={{ flex: 1 }}>
          {t('stats.lastMonth', { earnings: formatFare(stats.last_month.earnings), rides: rides(stats.last_month) })}
        </Txt>
        {stats.rating != null ? (
          <View style={styles.rating} accessibilityLabel={t('stats.rating', { rating: stats.rating.toFixed(2) })}>
            <Star size={14} color={theme.accent} fill={theme.accent} />
            <Txt variant="label">{stats.rating.toFixed(2)}</Txt>
          </View>
        ) : null}
        <Txt variant="caption" color="muted">
          {t('stats.total', { count: stats.total_rides })}
        </Txt>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  today: { flexDirection: 'row', alignItems: 'flex-end', gap: space.md, padding: space.md },
  chart: { flexDirection: 'row', alignItems: 'flex-end', gap: 6, height: 84 },
  barColumn: { alignItems: 'center', gap: 4 },
  barTrack: { width: 12, height: 64, justifyContent: 'flex-end' },
  bar: { width: 12, borderRadius: 6 },
  grid: { flexDirection: 'row', gap: space.sm },
  tile: { flex: 1, gap: 2, padding: space.md },
  footer: { flexDirection: 'row', alignItems: 'center', gap: space.sm, paddingHorizontal: space.xs },
  rating: { flexDirection: 'row', alignItems: 'center', gap: 4 },
});
