import { router } from 'expo-router';
import type { PropsWithChildren } from 'react';
import { View } from 'react-native';
import { useTranslation } from 'react-i18next';

import { ChevronLeft, type Icon } from '@/components/icons';
import { IconButton, IconTile, Row, Screen, type Tone, Txt } from '@/components/ui';
import { space } from '@/theme';

const back = () => (router.canGoBack() ? router.back() : router.replace('/profile'));

/** A page opened from the profile menu: back button, big icon, title and a short line. */
export function SubScreen({
  icon,
  tone = 'neutral',
  title,
  subtitle,
  children,
}: PropsWithChildren<{ icon: Icon; tone?: Tone; title: string; subtitle?: string }>) {
  const { t } = useTranslation();
  return (
    <Screen
      header={
        <Row style={{ paddingTop: space.xs, paddingBottom: space.md }}>
          <IconButton icon={ChevronLeft} label={t('common.back')} onPress={back} />
        </Row>
      }>
      <View style={{ alignItems: 'flex-start', gap: space.sm, marginBottom: space.lg }}>
        <IconTile icon={icon} tone={tone} size={56} />
        <Txt variant="title" accessibilityRole="header">
          {title}
        </Txt>
        {subtitle ? <Txt color="muted">{subtitle}</Txt> : null}
      </View>
      <View style={{ gap: space.lg, paddingBottom: space.xl }}>{children}</View>
    </Screen>
  );
}
