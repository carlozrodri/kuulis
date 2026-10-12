import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { RotateCcw } from '@/components/icons';
import { Button, ErrorText, Txt } from '@/components/ui';
import { useCanRestart, useJsUpdate } from '@/hooks/useJsUpdate';
import { space } from '@/theme';

/**
 * "Reiniciar ahora" for a downloaded JS update. The app never restarts by itself; this button is the only
 * way, and it stays disabled (saying why) during a ride or while the driver is online.
 */
export function RestartControls({ size = 'md', title }: { size?: 'sm' | 'md'; title?: string }) {
  const { t } = useTranslation();
  const js = useJsUpdate();
  const { allowed, blocker } = useCanRestart();
  return (
    <View style={{ gap: space.xs }}>
      <Button
        title={title ?? t('update.ota.restartNow')}
        icon={RotateCcw}
        size={size}
        variant="secondary"
        disabled={!allowed}
        style={size === 'sm' ? { alignSelf: 'flex-start' } : undefined}
        onPress={js.restart}
      />
      {blocker ? (
        <Txt variant="caption" color="muted">
          {t(`update.ota.blocked.${blocker}`)}
        </Txt>
      ) : null}
      <ErrorText>{js.restartFailed ? t('update.ota.restartError') : undefined}</ErrorText>
    </View>
  );
}
