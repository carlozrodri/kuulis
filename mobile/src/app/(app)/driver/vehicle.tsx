import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { Bike, Calendar, Hash, Palette } from '@/components/icons';
import { Button, Chip, ErrorText, Field, Txt } from '@/components/ui';
import { goBack, StepScreen } from '@/features/driver/StepScreen';
import { useAppConfig, useDriverProfile, useSaveVehicle } from '@/hooks/useDriver';
import { apiFormErrors } from '@/i18n';
import { isValidPlate, isValidVehicleYear, normalizePlate, vehicleYearRange } from '@/lib/driver';
import type { Vehicle, VehicleType } from '@/lib/types';
import { space } from '@/theme';

type Errors = Partial<Record<'type' | 'brand' | 'model' | 'year' | 'plate' | 'color', string>>;

/** Common motorcycle brands in Caracas, offered as shortcuts (free text is still allowed). */
const BRANDS = ['Bera', 'Empire Keeway', 'Yamaha', 'Suzuki', 'Honda', 'Haojue', 'MD', 'Skygo'];
const COLORS = ['black', 'white', 'red', 'blue', 'gray', 'silver'] as const;

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

  const [type, setType] = useState<VehicleType>(vehicle?.type ?? config.enabled_vehicle_types[0] ?? 'moto');
  const [brand, setBrand] = useState(vehicle?.brand ?? '');
  const [model, setModel] = useState(vehicle?.model ?? '');
  const [year, setYear] = useState(vehicle ? String(vehicle.year) : '');
  const [plate, setPlate] = useState(vehicle?.plate ?? '');
  const [color, setColor] = useState(vehicle?.color ?? '');
  const [errors, setErrors] = useState<Errors>({});
  const [error, setError] = useState<string>();

  const range = vehicleYearRange(config, type);

  async function submit() {
    const yearNumber = Number(year);
    const next: Errors = {
      brand: brand.trim() ? undefined : t('validation.required'),
      model: model.trim() ? undefined : t('validation.required'),
      year: isValidVehicleYear(yearNumber, config, type)
        ? undefined
        : t('driver.vehicle.yearInvalid', { min: range.min, max: range.max }),
      plate: isValidPlate(plate) ? undefined : t('driver.vehicle.plateInvalid'),
      color: color.trim() ? undefined : t('validation.required'),
    };
    setErrors(next);
    setError(undefined);
    if (Object.values(next).some(Boolean)) return;
    try {
      await save.mutateAsync({
        type,
        brand: brand.trim(),
        model: model.trim(),
        year: yearNumber,
        plate: normalizePlate(plate),
        color: color.trim(),
      });
      if (from === 'review') goBack();
      else router.push('/driver/documents');
    } catch (e) {
      const { fields, message } = apiFormErrors<keyof Errors>(e, {
        plate_taken: 'plate',
        vehicle_too_old: 'year',
        vehicle_year_invalid: 'year',
        vehicle_type_not_enabled: 'type',
      });
      setErrors(fields);
      setError(message ?? fields.type);
    }
  }

  return (
    <StepScreen
      step="vehicle"
      title={t('driver.vehicle.title')}
      subtitle={t('driver.vehicle.subtitle', { year: range.min })}
      footer={<Button title={from === 'review' ? t('common.save') : t('common.continue')} onPress={submit} loading={save.isPending} />}>
      {config.enabled_vehicle_types.length > 1 ? (
        <View style={{ marginBottom: space.md }}>
          <Txt variant="label" color="muted" style={{ marginBottom: 6 }}>
            {t('driver.vehicle.type')}
          </Txt>
          <View style={{ flexDirection: 'row', gap: space.xs }}>
            {config.enabled_vehicle_types.map((option) => (
              <Chip key={option} label={t(`driver.vehicleType.${option}`)} selected={type === option} onPress={() => setType(option)} />
            ))}
          </View>
        </View>
      ) : null}

      <Field
        label={t('driver.vehicle.brand')}
        icon={Bike}
        value={brand}
        onChangeText={setBrand}
        autoCapitalize="words"
        error={errors.brand}
      />
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: space.xs, marginTop: -space.xs, marginBottom: space.md }}>
        {BRANDS.map((option) => (
          <Chip key={option} label={option} selected={brand === option} onPress={() => setBrand(option)} />
        ))}
      </View>
      <Field
        label={t('driver.vehicle.model')}
        value={model}
        onChangeText={setModel}
        placeholder={t('driver.vehicle.modelPlaceholder')}
        autoCapitalize="words"
        error={errors.model}
      />
      <View style={{ flexDirection: 'row', gap: space.sm }}>
        <View style={{ flex: 1 }}>
          <Field
            label={t('driver.vehicle.year')}
            icon={Calendar}
            value={year}
            onChangeText={(v) => setYear(v.replace(/\D/g, '').slice(0, 4))}
            placeholder={String(range.max - 1)}
            keyboardType="number-pad"
            maxLength={4}
            error={errors.year}
          />
        </View>
        <View style={{ flex: 1.2 }}>
          <Field
            label={t('driver.vehicle.plate')}
            icon={Hash}
            value={plate}
            onChangeText={(v) => setPlate(v.toUpperCase())}
            onBlur={() => setPlate(normalizePlate(plate))}
            placeholder="AB2C34D"
            autoCapitalize="characters"
            autoCorrect={false}
            maxLength={10}
            error={errors.plate}
          />
        </View>
      </View>
      <Field
        label={t('driver.vehicle.color')}
        icon={Palette}
        value={color}
        onChangeText={setColor}
        autoCapitalize="sentences"
        error={errors.color}
      />
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: space.xs, marginTop: -space.xs }}>
        {COLORS.map((option) => {
          const label = t(`driver.colors.${option}`);
          return <Chip key={option} label={label} selected={color === label} onPress={() => setColor(label)} />;
        })}
      </View>
      <ErrorText>{error}</ErrorText>
    </StepScreen>
  );
}
