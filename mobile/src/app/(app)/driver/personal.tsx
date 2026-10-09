import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Calendar, Hash, IdCard, Smartphone } from '@/components/icons';
import { Button, ErrorText, Field } from '@/components/ui';
import { goBack, StepScreen } from '@/features/driver/StepScreen';
import { useAppConfig, useDriverProfile, useSavePersonal } from '@/hooks/useDriver';
import { apiFormErrors } from '@/i18n';
import {
  formatPhoneLocal,
  isOldEnough,
  isoToDisplayDate,
  isValidNationalId,
  isValidRif,
  maskDateInput,
  normalizeNationalId,
  normalizePhone,
  normalizeRif,
  parseDisplayDate,
} from '@/lib/driver';
import type { DriverProfile } from '@/lib/types';

type Errors = Partial<Record<'birth_date' | 'national_id' | 'rif' | 'phone', string>>;

export default function PersonalStep() {
  const { t } = useTranslation();
  const { data: profile, isPending } = useDriverProfile();
  if (isPending) return <StepScreen step="personal" title={t('driver.personal.title')} />;
  return <PersonalForm profile={profile ?? null} />;
}

function PersonalForm({ profile }: { profile: DriverProfile | null }) {
  const { t } = useTranslation();
  const { from } = useLocalSearchParams<{ from?: string }>();
  const { config } = useAppConfig();
  const save = useSavePersonal();

  const [birth, setBirth] = useState(isoToDisplayDate(profile?.birth_date));
  const [nationalId, setNationalId] = useState(profile?.national_id ?? '');
  const [rif, setRif] = useState(profile?.rif ?? '');
  const [phone, setPhone] = useState(formatPhoneLocal(profile?.phone));
  const [errors, setErrors] = useState<Errors>({});
  const [error, setError] = useState<string>();

  async function submit() {
    const birthIso = parseDisplayDate(birth);
    const phoneE164 = normalizePhone(phone);
    const next: Errors = {
      birth_date: !birthIso
        ? t('driver.personal.birthInvalid')
        : !isOldEnough(birthIso, config.driver_min_age)
          ? t('driver.personal.tooYoung', { age: config.driver_min_age })
          : undefined,
      national_id: isValidNationalId(nationalId) ? undefined : t('driver.personal.nationalIdInvalid'),
      rif: isValidRif(rif) ? undefined : t('driver.personal.rifInvalid'),
      phone: phoneE164 ? undefined : t('driver.personal.phoneInvalid'),
    };
    setErrors(next);
    setError(undefined);
    if (Object.values(next).some(Boolean) || !birthIso || !phoneE164) return;

    try {
      await save.mutateAsync({
        birth_date: birthIso,
        national_id: normalizeNationalId(nationalId),
        rif: normalizeRif(rif),
        phone: phoneE164,
      });
      if (from === 'review') goBack();
      else router.push('/driver/vehicle');
    } catch (e) {
      const { fields, message } = apiFormErrors(e, { national_id_taken: 'national_id' });
      setErrors(fields);
      setError(message);
    }
  }

  return (
    <StepScreen
      step="personal"
      title={t('driver.personal.title')}
      subtitle={t('driver.personal.subtitle')}
      footer={<Button title={from === 'review' ? t('common.save') : t('common.continue')} onPress={submit} loading={save.isPending} />}>
      <Field
        label={t('driver.personal.birthDate')}
        icon={Calendar}
        value={birth}
        onChangeText={(v) => setBirth(maskDateInput(v))}
        placeholder={t('driver.personal.birthPlaceholder')}
        keyboardType="number-pad"
        maxLength={10}
        error={errors.birth_date}
        hint={t('driver.personal.birthHint', { age: config.driver_min_age })}
      />
      <Field
        label={t('driver.personal.nationalId')}
        icon={IdCard}
        value={nationalId}
        onChangeText={setNationalId}
        onBlur={() => nationalId && setNationalId(normalizeNationalId(nationalId))}
        placeholder="V12345678"
        autoCapitalize="characters"
        autoCorrect={false}
        maxLength={14}
        error={errors.national_id}
      />
      <Field
        label={t('driver.personal.rif')}
        icon={Hash}
        value={rif}
        onChangeText={setRif}
        onBlur={() => rif && setRif(normalizeRif(rif))}
        placeholder="V123456789"
        autoCapitalize="characters"
        autoCorrect={false}
        maxLength={14}
        error={errors.rif}
        hint={t('driver.personal.rifHint')}
      />
      <Field
        label={t('driver.personal.phone')}
        icon={Smartphone}
        value={phone}
        onChangeText={setPhone}
        placeholder="0412 123 4567"
        keyboardType="phone-pad"
        autoComplete="tel"
        textContentType="telephoneNumber"
        maxLength={20}
        error={errors.phone}
        hint={t('driver.personal.phoneHint')}
      />
      <ErrorText>{error}</ErrorText>
    </StepScreen>
  );
}
