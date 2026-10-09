import * as Haptics from 'expo-haptics';
import { router } from 'expo-router';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { CircleCheck, Hourglass, Pencil } from '@/components/icons';
import { Button, Card, ErrorText, ListRow, Notice, StatusPill, Txt } from '@/components/ui';
import { StepScreen } from '@/features/driver/StepScreen';
import { useAppConfig, useDriverProfile, useSubmitDriver } from '@/hooks/useDriver';
import { apiErrorMessage } from '@/i18n';
import { formatPhoneLocal, isDocumentDone, isoToDisplayDate, requirementChecklist } from '@/lib/driver';
import { space } from '@/theme';

function Section({ title, onEdit, children }: { title: string; onEdit: () => void; children: React.ReactNode }) {
  const { t } = useTranslation();
  return (
    <Card style={{ marginBottom: space.md }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
        <Txt variant="subtitle">{title}</Txt>
        <Button
          title={t('common.edit')}
          variant="ghost"
          size="sm"
          icon={Pencil}
          style={{ marginTop: 0 }}
          accessibilityLabel={`${t('common.edit')}: ${title}`}
          onPress={onEdit}
        />
      </View>
      <View style={{ gap: space.xs, marginTop: space.xs }}>{children}</View>
    </Card>
  );
}

function Line({ label, value }: { label: string; value?: string | number | null }) {
  return (
    <View style={{ flexDirection: 'row', justifyContent: 'space-between', gap: space.md }}>
      <Txt color="muted">{label}</Txt>
      <Txt variant="bodyStrong" style={{ flexShrink: 1, textAlign: 'right' }}>
        {value ?? '—'}
      </Txt>
    </View>
  );
}

export default function ReviewStep() {
  const { t } = useTranslation();
  const { data: profile } = useDriverProfile();
  const { config } = useAppConfig();
  const submit = useSubmitDriver();
  const [error, setError] = useState<string>();

  const checklist = requirementChecklist(profile, config);
  const docsDone = checklist.documents.filter(isDocumentDone).length;
  const canSubmit = !!profile?.requirements.can_submit;
  const minYear = config.vehicle_min_year[profile?.vehicle?.type ?? 'moto'];

  async function send() {
    setError(undefined);
    try {
      await submit.mutateAsync();
      void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => undefined);
      router.dismissTo('/');
    } catch (e) {
      setError(apiErrorMessage(e));
    }
  }

  const edit = (pathname: '/driver/personal' | '/driver/vehicle' | '/driver/documents') =>
    router.push({ pathname, params: { from: 'review' } });

  return (
    <StepScreen
      step="review"
      title={t('driver.review.title')}
      subtitle={t('driver.review.subtitle')}
      footer={<Button title={t('driver.review.submit')} onPress={send} loading={submit.isPending} disabled={!canSubmit} />}>
      <Section title={t('driver.personal.title')} onEdit={() => edit('/driver/personal')}>
        <Line label={t('driver.personal.birthDate')} value={isoToDisplayDate(profile?.birth_date)} />
        <Line label={t('driver.personal.nationalId')} value={profile?.national_id} />
        <Line label={t('driver.personal.rif')} value={profile?.rif} />
        <Line label={t('driver.personal.phone')} value={formatPhoneLocal(profile?.phone)} />
      </Section>

      <Section title={t('driver.vehicle.title')} onEdit={() => edit('/driver/vehicle')}>
        {profile?.vehicle ? (
          <>
            <Line label={t('driver.vehicle.brand')} value={`${profile.vehicle.brand} ${profile.vehicle.model}`} />
            <Line label={t('driver.vehicle.year')} value={profile.vehicle.year} />
            <Line label={t('driver.vehicle.plate')} value={profile.vehicle.plate} />
            <Line label={t('driver.vehicle.color')} value={profile.vehicle.color} />
          </>
        ) : (
          <Txt color="muted">{t('driver.review.missingVehicle')}</Txt>
        )}
      </Section>

      <Section title={t('driver.documents.title')} onEdit={() => edit('/driver/documents')}>
        <StatusPill
          label={t('driver.documents.progress', { done: docsDone, total: checklist.documents.length })}
          tone={docsDone === checklist.documents.length ? 'success' : 'warning'}
          dot
        />
      </Section>

      <Txt variant="overline" color="muted" style={{ marginTop: space.xs, marginBottom: space.xs }}>
        {t('driver.intro.requirements')}
      </Txt>
      <Card style={{ paddingVertical: space.xxs, marginBottom: space.md }}>
        {checklist.items.map((item, index) => (
          <ListRow
            key={item.key}
            title={t(`driver.requirement.${item.key}`, { age: config.driver_min_age, year: minYear })}
            icon={item.done ? CircleCheck : Hourglass}
            iconTone={item.done ? 'success' : 'warning'}
            chevron={false}
            divider={index < checklist.items.length - 1}
          />
        ))}
      </Card>

      {!canSubmit ? <Notice tone="warning">{t('driver.review.incomplete')}</Notice> : <Notice tone="info">{t('driver.review.declaration')}</Notice>}
      <View style={{ marginTop: space.sm }}>
        <ErrorText>{error}</ErrorText>
      </View>
    </StepScreen>
  );
}
