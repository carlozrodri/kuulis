import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { MapPin } from '@/components/icons';
import { Button, Card, IconTile, Txt } from '@/components/ui';
import { useUserLocation } from '@/hooks/useLocation';
import { space } from '@/theme';

/** Explains why we need the location before the system prompt (and links to settings when blocked). */
export function LocationPrompt({ variant = 'passenger' }: { variant?: 'passenger' | 'driver' }) {
  const { t } = useTranslation();
  const { permission, request } = useUserLocation({ watch: false });
  if (permission === 'granted') return null;
  const blocked = permission === 'blocked';
  return (
    <Card tone="tint" style={{ gap: space.sm, padding: space.md }}>
      <View style={{ flexDirection: 'row', gap: space.sm, alignItems: 'center' }}>
        <IconTile icon={MapPin} tone="primary" />
        <View style={{ flex: 1 }}>
          <Txt variant="bodyStrong">{t('location.title')}</Txt>
          <Txt variant="caption" color="muted">
            {blocked ? t('location.blockedBody') : variant === 'driver' ? t('location.driverBody') : t('location.body')}
          </Txt>
        </View>
      </View>
      <Button
        title={blocked ? t('common.openSettings') : t('location.allow')}
        variant="secondary"
        size="sm"
        onPress={() => void request()}
      />
    </Card>
  );
}
