import { router } from 'expo-router';
import { type PropsWithChildren, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { ChevronLeft } from '@/components/icons';
import { Button, IconButton, Notice, ProgressSteps, Row, Screen, Skeleton, Txt } from '@/components/ui';
import { useDriverProfile } from '@/hooks/useDriver';
import { DRIVER_STEPS, type DriverStep, isEditable } from '@/lib/driver';
import { radius, space } from '@/theme';

import { STEP_NUMBER } from './meta';

export function goBack() {
  if (router.canGoBack()) router.back();
  else router.replace('/');
}

/** Shared chrome for onboarding steps: back button, "Paso n de 4", progress bar, title and sticky CTA. */
export function StepScreen({
  step,
  title,
  subtitle,
  footer,
  children,
}: PropsWithChildren<{ step: DriverStep; title: string; subtitle?: string; footer?: ReactNode }>) {
  const { t } = useTranslation();
  const profile = useDriverProfile();
  const locked = !!profile.data && !isEditable(profile.data.status);
  const current = STEP_NUMBER[step];

  return (
    <Screen
      header={
        <View style={{ gap: space.md, paddingTop: space.xs, paddingBottom: space.md }}>
          <Row>
            <IconButton icon={ChevronLeft} label={t('common.back')} onPress={goBack} />
            <Txt variant="label" color="muted">
              {t('driver.step.counter', { current, total: DRIVER_STEPS.length })}
            </Txt>
          </Row>
          <ProgressSteps total={DRIVER_STEPS.length} current={current} />
        </View>
      }
      footer={locked ? <Button title={t('common.back')} variant="secondary" onPress={goBack} /> : footer}>
      <Txt variant="title" accessibilityRole="header">
        {title}
      </Txt>
      {subtitle ? (
        <Txt color="muted" style={{ marginTop: space.xxs, marginBottom: space.lg }}>
          {subtitle}
        </Txt>
      ) : (
        <View style={{ height: space.lg }} />
      )}
      {profile.isPending ? (
        <View style={{ gap: space.md }}>
          <Skeleton height={52} />
          <Skeleton height={52} />
          <Skeleton height={52} radius={radius.field} />
        </View>
      ) : locked ? (
        <Notice tone="warning">{t('driver.step.locked')}</Notice>
      ) : (
        children
      )}
    </Screen>
  );
}
