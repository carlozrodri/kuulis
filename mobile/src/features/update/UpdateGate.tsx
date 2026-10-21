import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { BackHandler, StyleSheet, View } from 'react-native';

import { Download } from '@/components/icons';
import { Card, IconTile, Screen, Txt } from '@/components/ui';
import { useAppUpdate } from '@/hooks/useAppUpdate';
import { useActiveRide } from '@/hooks/useRides';
import { trackOnce } from '@/lib/analytics';
import { appVersion, formatMegabytes, fromPlayStore } from '@/lib/appVersion';
import { isActiveStatus } from '@/lib/ride';
import { space } from '@/theme';

import { InstallControls } from './UpdateControls';

/**
 * Mandatory update (doc 09): covers the signed-in app with "Necesitas actualizar" until the new APK is
 * installed. A ride in progress (passenger or driver) is never interrupted: the homes show the banner
 * instead and the block starts when the ride ends.
 */
export function UpdateGate() {
  const { required } = useAppUpdate();
  const active = useActiveRide(required);
  const inRide = !!active.data && isActiveStatus(active.data.status);
  // While the active ride is unknown (first load), do not block: it would flash over a ride screen.
  const blocking = required && !inRide && !active.isPending;

  useEffect(() => {
    if (!blocking) return;
    trackOnce('apk:gate', 'update_prompt_shown', { kind: 'required' });
    // Android back would only reveal the screens underneath.
    const sub = BackHandler.addEventListener('hardwareBackPress', () => true);
    return () => sub.remove();
  }, [blocking]);

  if (!blocking) return null;
  return (
    <View style={StyleSheet.absoluteFill}>
      <UpdateRequiredScreen />
    </View>
  );
}

function UpdateRequiredScreen() {
  const { t } = useTranslation();
  const { latest } = useAppUpdate();
  return (
    <Screen edges={['top', 'bottom', 'left', 'right']} footer={<InstallControls />}>
      <View style={{ alignItems: 'flex-start', gap: space.sm, marginTop: space.xl, marginBottom: space.lg }}>
        <IconTile icon={Download} tone="warning" size={56} />
        <Txt variant="title" accessibilityRole="header">
          {t('update.required.title')}
        </Txt>
        <Txt color="muted">{t('update.required.body')}</Txt>
      </View>
      {fromPlayStore ? null : (
        <Card style={{ gap: space.xs }}>
          <Txt variant="label" color="muted">
            {latest
              ? t('update.required.version', {
                  version: latest.version,
                  build: latest.build,
                  size: formatMegabytes(latest.size),
                })
              : t('update.required.checking')}
          </Txt>
          {latest?.notes ? <Txt>{latest.notes}</Txt> : null}
          <Txt variant="caption" color="muted">
            {t('update.required.current', { version: appVersion.version, build: appVersion.build })}
          </Txt>
        </Card>
      )}
      {fromPlayStore ? null : (
        <Txt variant="caption" color="muted" style={{ marginTop: space.md }}>
          {t('update.unknownSources.hint')}
        </Txt>
      )}
    </Screen>
  );
}
