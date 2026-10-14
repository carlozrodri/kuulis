import { router } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { StyleSheet, View } from 'react-native';

import { CalendarClock, CirclePause, Gauge } from '@/components/icons';
import { Button, Txt } from '@/components/ui';
import { useNow } from '@/features/ride/RideSheets';
import { pauseUntilText } from '@/i18n';
import { formatCountdown } from '@/lib/quality';
import { secondsUntil } from '@/lib/ride';
import type { QualityPause } from '@/lib/types';
import { radius, space, useTheme } from '@/theme';

/**
 * Doc 15: a temporary pause for quality. The driver sees a live countdown until they can go online again
 * (it replaces the CONECTARME explanation); the passenger, until when they cannot request rides.
 */
export function PausePanel({
  pause,
  variant,
  showQualityLink = variant === 'driver',
}: {
  pause: QualityPause;
  variant: 'passenger' | 'driver';
  /** "Ver mi calidad" (drivers), hidden on the quality screen itself. */
  showQualityLink?: boolean;
}) {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const now = useNow(1000);
  const driver = variant === 'driver';
  const left = formatCountdown(secondsUntil(pause.until, now));
  const reason = pause.reason ? t(`quality.pause.reason.${pause.reason}`) : null;
  const body = driver ? t('quality.pause.driverBody') : t('quality.pause.passengerBody');

  return (
    <View accessibilityRole="alert" style={[styles.panel, { backgroundColor: theme.warningSoft }]}>
      <View style={styles.titleRow}>
        <View style={[styles.icon, { backgroundColor: theme.surface }]}>
          <CirclePause size={22} color={theme.warning} strokeWidth={2.2} />
        </View>
        <Txt variant="heading" style={{ flex: 1 }} accessibilityRole="header">
          {driver ? t('quality.pause.driverTitle') : t('quality.pause.passengerTitle')}
        </Txt>
      </View>
      <Txt>{body}</Txt>

      <View style={[styles.facts, { backgroundColor: theme.surface }]}>
        {driver ? (
          <View accessible accessibilityRole="timer" accessibilityLabel={t('quality.pause.countdownA11y', { time: left })} style={styles.countdown}>
            <Txt variant="micro" color="muted">
              {t('quality.pause.countdownLabel')}
            </Txt>
            <Txt variant="display" tabular style={{ color: theme.warning }}>
              {left}
            </Txt>
            <Txt variant="caption" color="muted">
              {pauseUntilText(pause.until, i18n.language)}
            </Txt>
          </View>
        ) : (
          <View style={styles.untilRow} accessible>
            <CalendarClock size={18} color={theme.muted} strokeWidth={2.2} />
            <View style={{ flex: 1 }}>
              <Txt variant="micro" color="muted">
                {t('quality.pause.untilLabel')}
              </Txt>
              <Txt variant="bodyStrong" tabular>
                {pauseUntilText(pause.until, i18n.language)}
              </Txt>
            </View>
          </View>
        )}
        {reason ? (
          <View style={[styles.reason, { borderTopColor: theme.divider }]}>
            <Txt variant="micro" color="muted">
              {t('quality.pause.why')}
            </Txt>
            <Txt variant="label">{reason}</Txt>
          </View>
        ) : null}
      </View>

      {showQualityLink ? (
        <Button
          title={t('quality.pause.seeQuality')}
          variant="ghost"
          size="sm"
          icon={Gauge}
          style={{ alignSelf: 'flex-start', marginTop: 0 }}
          onPress={() => router.push('/driver/quality')}
        />
      ) : !driver ? (
        <Txt variant="caption" color="muted">
          {t('quality.pause.passengerHint')}
        </Txt>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  panel: { borderRadius: radius.card, padding: space.md, gap: space.sm },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
  icon: { width: 44, height: 44, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  facts: { borderRadius: radius.tile, paddingHorizontal: space.md },
  countdown: { alignItems: 'center', gap: 2, paddingVertical: space.md },
  untilRow: { flexDirection: 'row', alignItems: 'center', gap: space.sm, paddingVertical: space.sm },
  reason: { borderTopWidth: 1, paddingVertical: space.sm, gap: 2 },
});
