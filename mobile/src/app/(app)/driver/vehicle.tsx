import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Button, ErrorText } from '@/components/ui';
import { goBack, StepScreen } from '@/features/driver/StepScreen';
import { VEHICLE_ERROR_FIELDS, VehicleFields, useVehicleForm } from '@/features/driver/VehicleFields';
import { useAppConfig, useDriverProfile, useSaveVehicle } from '@/hooks/useDriver';
import { apiFormErrors } from '@/i18n';
import type { Vehicle, VehicleInput } from '@/lib/types';

export default function VehicleStep() {
  const { t } = useTranslation();
  const { data: profile, isPending } = useDriverProfile();
  if (isPending) return <StepScreen step="vehicle" title={t('driver.vehicle.title')} />;
  return <VehicleForm vehicle={profile?.vehicle ?? null} />;
}

function VehicleForm({ vehicle }: { vehicle: Vehicle | null }) {
  const { t } = useTranslation();
  const { from } = useLocalSearchParams<{ from?: string }>();
  const { config } = useAppConfig();
  const save = useSaveVehicle();
  const form = useVehicleForm(vehicle, config);
  const [error, setError] = useState<string>();

  async function submit() {
    setError(undefined);
    const input = form.validate();
    if (!input) return;
    try {
      await save.mutateAsync(input);
      if (from === 'review') goBack();
      else router.push('/driver/documents');
    } catch (e) {
      const { fields, message } = apiFormErrors<keyof VehicleInput>(e, VEHICLE_ERROR_FIELDS);
      form.setErrors(fields);
      setError(message ?? fields.type);
    }
  }

  return (
    <StepScreen
      step="vehicle"
      title={t('driver.vehicle.title')}
      subtitle={t('driver.vehicle.subtitle', { year: form.range.min })}
      footer={<Button title={from === 'review' ? t('common.save') : t('common.continue')} onPress={submit} loading={save.isPending} />}>
      <VehicleFields form={form} config={config} />
      <ErrorText>{error}</ErrorText>
    </StepScreen>
  );
}
