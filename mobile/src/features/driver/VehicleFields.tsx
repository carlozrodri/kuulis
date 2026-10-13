import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { Bike, Calendar, Hash, Palette } from '@/components/icons';
import { Chip, Field, Txt } from '@/components/ui';
import { isValidPlate, isValidVehicleYear, normalizePlate, vehicleYearRange } from '@/lib/driver';
import type { AppConfig, Vehicle, VehicleInput, VehicleType } from '@/lib/types';
import { space } from '@/theme';

export type VehicleErrors = Partial<Record<keyof VehicleInput, string>>;

/** Common motorcycle brands in Caracas, offered as shortcuts (free text is still allowed). */
const BRANDS = ['Bera', 'Empire Keeway', 'Yamaha', 'Suzuki', 'Honda', 'Haojue', 'MD', 'Skygo'];
const COLORS = ['black', 'white', 'red', 'blue', 'gray', 'silver'] as const;

/** API error codes that belong to a vehicle field. */
export const VEHICLE_ERROR_FIELDS: Partial<Record<string, keyof VehicleInput>> = {
  plate_taken: 'plate',
  vehicle_same_plate: 'plate',
  vehicle_too_old: 'year',
  vehicle_year_invalid: 'year',
  vehicle_type_not_enabled: 'type',
};

/** State and validation of the moto form (onboarding step 2 and "Cambiar de moto"). */
export function useVehicleForm(vehicle: Vehicle | null, config: AppConfig) {
  const { t } = useTranslation();
  const [type, setType] = useState<VehicleType>(vehicle?.type ?? config.enabled_vehicle_types[0] ?? 'moto');
  const [brand, setBrand] = useState(vehicle?.brand ?? '');
  const [model, setModel] = useState(vehicle?.model ?? '');
  const [year, setYear] = useState(vehicle ? String(vehicle.year) : '');
  const [plate, setPlate] = useState(vehicle?.plate ?? '');
  const [color, setColor] = useState(vehicle?.color ?? '');
  const [errors, setErrors] = useState<VehicleErrors>({});
  const range = vehicleYearRange(config, type);

  /** The input to send, or null after marking the fields to fix. */
  function validate(): VehicleInput | null {
    const yearNumber = Number(year);
    const next: VehicleErrors = {
      brand: brand.trim() ? undefined : t('validation.required'),
      model: model.trim() ? undefined : t('validation.required'),
      year: isValidVehicleYear(yearNumber, config, type)
        ? undefined
        : t('driver.vehicle.yearInvalid', { min: range.min, max: range.max }),
      plate: isValidPlate(plate) ? undefined : t('driver.vehicle.plateInvalid'),
      color: color.trim() ? undefined : t('validation.required'),
    };
    setErrors(next);
    if (Object.values(next).some(Boolean)) return null;
    return {
      type,
      brand: brand.trim(),
      model: model.trim(),
      year: yearNumber,
      plate: normalizePlate(plate),
      color: color.trim(),
    };
  }

  return {
    values: { type, brand, model, year, plate, color },
    set: { type: setType, brand: setBrand, model: setModel, year: setYear, plate: setPlate, color: setColor },
    errors,
    setErrors,
    range,
    validate,
  };
}

export type VehicleForm = ReturnType<typeof useVehicleForm>;

/** Type, brand, model, year, plate and color with their shortcuts. */
export function VehicleFields({ form, config }: { form: VehicleForm; config: AppConfig }) {
  const { t } = useTranslation();
  const { values, set, errors, range } = form;
  return (
    <>
      {config.enabled_vehicle_types.length > 1 ? (
        <View style={{ marginBottom: space.md }}>
          <Txt variant="label" color="muted" style={{ marginBottom: 6 }}>
            {t('driver.vehicle.type')}
          </Txt>
          <View style={{ flexDirection: 'row', gap: space.xs }}>
            {config.enabled_vehicle_types.map((option) => (
              <Chip key={option} label={t(`driver.vehicleType.${option}`)} selected={values.type === option} onPress={() => set.type(option)} />
            ))}
          </View>
        </View>
      ) : null}

      <Field
        label={t('driver.vehicle.brand')}
        icon={Bike}
        value={values.brand}
        onChangeText={set.brand}
        autoCapitalize="words"
        error={errors.brand}
      />
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: space.xs, marginTop: -space.xs, marginBottom: space.md }}>
        {BRANDS.map((option) => (
          <Chip key={option} label={option} selected={values.brand === option} onPress={() => set.brand(option)} />
        ))}
      </View>
      <Field
        label={t('driver.vehicle.model')}
        value={values.model}
        onChangeText={set.model}
        placeholder={t('driver.vehicle.modelPlaceholder')}
        autoCapitalize="words"
        error={errors.model}
      />
      <View style={{ flexDirection: 'row', gap: space.sm }}>
        <View style={{ flex: 1 }}>
          <Field
            label={t('driver.vehicle.year')}
            icon={Calendar}
            value={values.year}
            onChangeText={(v) => set.year(v.replace(/\D/g, '').slice(0, 4))}
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
            value={values.plate}
            onChangeText={(v) => set.plate(v.toUpperCase())}
            onBlur={() => set.plate(normalizePlate(values.plate))}
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
        value={values.color}
        onChangeText={set.color}
        autoCapitalize="sentences"
        error={errors.color}
      />
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: space.xs, marginTop: -space.xs }}>
        {COLORS.map((option) => {
          const label = t(`driver.colors.${option}`);
          return <Chip key={option} label={label} selected={values.color === label} onPress={() => set.color(label)} />;
        })}
      </View>
    </>
  );
}
