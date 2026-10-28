import { beforeAll, describe, expect, it, jest } from '@jest/globals';
import { fireEvent, screen } from '@testing-library/react-native';

import { ActivityStrip, ActivityTripCard } from '@/features/passenger/CityActivity';
import i18n from '@/i18n';
import type { PublicActivity } from '@/lib/types';

import { renderScreen } from '../../test-utils/render';

const base: PublicActivity = {
  live: false,
  threshold: 3,
  trips_last_hour: 1,
  verified_drivers: 12,
  in_progress: [],
  recent: [],
  updated_at: '2026-10-28T20:00:00Z',
};

describe('Caracas en movimiento (doc 01-B)', () => {
  beforeAll(async () => {
    await i18n.changeLanguage('es');
  });

  it('below the threshold shows the honest message with the real verified drivers', async () => {
    await renderScreen(<ActivityStrip activity={base} />);
    expect(screen.getByText('Kuulis está arrancando en Caracas')).toBeTruthy();
    expect(screen.getByText(/Motorizados verificados hasta hoy: 12/)).toBeTruthy();
    expect(screen.queryByText('Caracas en movimiento')).toBeNull();
  });

  it('without verified drivers yet it does not invent a number', async () => {
    await renderScreen(<ActivityStrip activity={{ ...base, verified_drivers: 0 }} />);
    expect(screen.getByText(/Estamos verificando a los primeros motorizados/)).toBeTruthy();
  });

  it('live shows the recent real trips, with price and distance only', async () => {
    await renderScreen(
      <ActivityStrip
        activity={{ ...base, live: true, trips_last_hour: 7, recent: [{ minutes_ago: 10, distance_m: 3400, fare: '1.80' }] }}
      />,
    );
    expect(screen.getByText('Caracas en movimiento')).toBeTruthy();
    expect(screen.getByText('Última hora: 7 viajes')).toBeTruthy();
    expect(screen.getByText('Hace 10 min')).toBeTruthy();
    expect(screen.getByLabelText(/Viaje terminado hace 10 minutos, 3[.,]4 km, \$1\.80/)).toBeTruthy();
  });

  it('a tapped moto shows its trip and closes', async () => {
    const onClose = jest.fn();
    await renderScreen(<ActivityTripCard trip={{ id: 'abc', lat: 10.49, lng: -66.88, distance_m: 2100, fare: '1.80' }} onClose={onClose} />);
    expect(screen.getByText('Viaje en curso')).toBeTruthy();
    expect(screen.getByText(/\$1\.80/)).toBeTruthy();
    expect(screen.getByText("Todito pa'l motorizado, sin comisión")).toBeTruthy();
    await fireEvent.press(screen.getByLabelText('Cerrar'));
    expect(onClose).toHaveBeenCalled();
  });
});
