import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { type StyleProp, StyleSheet, View, type ViewStyle } from 'react-native';

import { Download, Sparkles, X } from '@/components/icons';
import { Card, IconButton, IconTile, Txt } from '@/components/ui';
import { useAppUpdate } from '@/hooks/useAppUpdate';
import { useCanRestart, useJsUpdate } from '@/hooks/useJsUpdate';
import { trackOnce } from '@/lib/analytics';
import { formatMegabytes } from '@/lib/appVersion';
import { space } from '@/theme';

import { RestartControls } from './RestartControls';
import { InstallControls } from './UpdateControls';

/**
 * "Nueva versión disponible" card on the passenger and driver homes. Optional updates can be dismissed
 * for that build; a mandatory one postponed by a ride in progress cannot. Without a new APK to show, a
 * downloaded JS update may show "Hay una mejora lista" instead.
 */
export function UpdateBanner({ style }: { style?: StyleProp<ViewStyle> }) {
  const { t } = useTranslation();
  const { latest, available, required, dismissed, dismiss } = useAppUpdate();
  const shown = available && !!latest && (required || !dismissed);
  useEffect(() => {
    if (shown && latest) trackOnce(`apk:${latest.version}:${required}`, 'update_prompt_shown', { kind: required ? 'required' : 'optional' });
  }, [shown, latest, required]);
  if (!shown || !latest) return <JsUpdateBanner style={style} />;
  return (
    <Card tone="tint" style={[styles.card, style]}>
      <View style={styles.row}>
        <IconTile icon={Download} tone={required ? 'warning' : 'primary'} size={40} />
        <View style={{ flex: 1, gap: 2 }}>
          <Txt variant="bodyStrong">{required ? t('update.banner.requiredTitle') : t('update.banner.title')}</Txt>
          <Txt variant="caption" color="muted">
            {required
              ? t('update.banner.requiredBody', { version: latest.version })
              : t('update.banner.body', { version: latest.version, size: formatMegabytes(latest.size) })}
          </Txt>
        </View>
        {!required ? <IconButton icon={X} label={t('update.banner.dismiss')} tone="plain" size={36} onPress={dismiss} /> : null}
      </View>
      <InstallControls size="sm" />
    </Card>
  );
}

/**
 * A JS update was downloaded and applies on the next start. Offers a restart only when nothing would be
 * interrupted: hidden during a ride and while the driver is online. Closing it hides it until the next start.
 */
function JsUpdateBanner({ style }: { style?: StyleProp<ViewStyle> }) {
  const { t } = useTranslation();
  const js = useJsUpdate();
  const { allowed } = useCanRestart(js.pending && !js.dismissed);
  const shown = js.pending && !js.dismissed && allowed;
  useEffect(() => {
    if (shown) trackOnce('ota', 'update_prompt_shown', { kind: 'ota' });
  }, [shown]);
  if (!shown) return null;
  return (
    <Card tone="tint" style={[styles.card, style]}>
      <View style={styles.row}>
        <IconTile icon={Sparkles} tone="primary" size={40} />
        <View style={{ flex: 1, gap: 2 }}>
          <Txt variant="bodyStrong">{t('update.ota.bannerTitle')}</Txt>
          <Txt variant="caption" color="muted">
            {t('update.ota.bannerBody')}
          </Txt>
        </View>
        <IconButton icon={X} label={t('update.banner.dismiss')} tone="plain" size={36} onPress={js.dismiss} />
      </View>
      <RestartControls size="sm" title={t('update.ota.restart')} />
    </Card>
  );
}

const styles = StyleSheet.create({
  card: { gap: space.sm, padding: space.md },
  row: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
});
