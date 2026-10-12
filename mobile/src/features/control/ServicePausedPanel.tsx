import { useTranslation } from 'react-i18next';
import { StyleSheet, View } from 'react-native';

import { CirclePause, Clock, Wrench } from '@/components/icons';
import { Txt } from '@/components/ui';
import { formatEta, localize, type Notice } from '@/lib/bootstrap';
import { radius, space, useTheme } from '@/theme';

/**
 * "Pausamos los pedidos en Caracas": replaces the search (passenger) or the CONECTARME button's explanation
 * (driver) while the city is paused or in maintenance, with the reason and the estimated time back.
 */
export function ServicePausedPanel({ notice, variant }: { notice: Notice; variant: 'passenger' | 'driver' }) {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const maintenance = notice.kind === 'maintenance';
  const message =
    localize(notice.message, i18n.language) || t(maintenance ? 'control.maintenance.defaultBody' : 'control.pause.defaultBody');
  const eta = formatEta(notice.eta, i18n.language);
  const PanelIcon = maintenance ? Wrench : CirclePause;
  const title = maintenance
    ? t('control.maintenance.title')
    : notice.area
      ? t(variant === 'driver' ? 'control.pause.driverTitleArea' : 'control.pause.titleArea', { area: notice.area })
      : t(variant === 'driver' ? 'control.pause.driverTitle' : 'control.pause.title');
  return (
    <View accessibilityRole="alert" style={[styles.panel, { backgroundColor: theme.warningSoft }]}>
      <View style={styles.titleRow}>
        <PanelIcon size={22} color={theme.warning} strokeWidth={2.2} />
        <Txt variant="subtitle" style={{ color: theme.text, flex: 1 }} accessibilityRole="header">
          {title}
        </Txt>
      </View>
      <Txt style={{ color: theme.text }}>{message}</Txt>
      {eta ? (
        <View style={styles.titleRow}>
          <Clock size={16} color={theme.warning} strokeWidth={2.4} />
          <Txt variant="label" style={{ color: theme.warning }}>
            {t('control.maintenance.eta', { time: eta })}
          </Txt>
        </View>
      ) : null}
      {variant === 'driver' ? (
        <Txt variant="caption" color="muted">
          {t('control.pause.driverHint')}
        </Txt>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  panel: { borderRadius: radius.card, padding: space.md, gap: space.xs },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: space.xs },
});
