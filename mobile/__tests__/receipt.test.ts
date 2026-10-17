import { beforeAll, describe, expect, it } from '@jest/globals';

import { repeatRide, rideDraft } from '@/features/ride/store';
import { rideRequestBody } from '@/hooks/useRides';
import i18n from '@/i18n';
import { receiptText } from '@/lib/receipt';
import { riderShareMessage } from '@/lib/safety';
import type { RideReceipt } from '@/lib/types';

import { makeRide } from '../test-utils/fixtures';

const t = (key: string, values?: Record<string, unknown>) => i18n.t(key, values);

const RECEIPT: RideReceipt = {
  ride_id: 'r-1',
  number: '3F9A1C2B',
  completed_at: '2026-10-17T14:30:00Z',
  pickup_address: 'Plaza Altamira, Chacao, Caracas',
  dropoff_address: 'Sambil, Avenida Libertador, Chacao',
  distance_m: 4300,
  duration_s: 840,
  fare: '3.50',
  discount: '0.50',
  total: '3.00',
  rates: { bcv: '185.4321', binance: '240.10' },
  total_ves: { bcv: '556.30', binance: '720.30' },
  payment_method: 'pago_movil',
  passenger_name: 'María',
  driver_name: 'Luis',
  plate: 'AB123CD',
  image_url: 'https://kuulis.example/api/v1/public/rides/receipts/x.png',
};

describe('doc 23', () => {
  beforeAll(async () => {
    await i18n.changeLanguage('es');
  });

  it('receipt text: number, route, USD and Bs, payment method and "no fiscal"', () => {
    const text = receiptText(RECEIPT, t, 'es');
    expect(text).toContain('N.º 3F9A1C2B');
    expect(text).toContain('Plaza Altamira → Sambil');
    expect(text).toContain('Total: $3.00 · Bs 556,30 (BCV)');
    expect(text).toContain('Pago móvil');
    expect(text).toContain('No es una factura fiscal');
  });

  it('request body carries the note and the person riding only when set', () => {
    expect(rideRequestBody({ quote_id: 'q', payment_method: 'cash_usd', note: '  ', rider: null })).toEqual({
      quote_id: 'q',
      payment_method: 'cash_usd',
    });
    expect(
      rideRequestBody({ quote_id: 'q', payment_method: 'zelle', note: ' Portón ', rider: { name: 'Ana', phone: '+584141112233' } }),
    ).toEqual({ quote_id: 'q', payment_method: 'zelle', note: 'Portón', rider: { name: 'Ana', phone: '+584141112233' } });
  });

  it('repeat sets the same route and starts clean', () => {
    rideDraft.set((draft) => ({ ...draft, promoCode: 'X', note: 'old', rider: { name: 'A', phone: '+584141112233' } }));
    const ride = makeRide({ pickup: { lat: 1, lng: 2, address: 'A' }, dropoff: { lat: 3, lng: 4, address: 'B' } });
    repeatRide(ride);
    const draft = rideDraft.get();
    expect(draft.pickup).toEqual(ride.pickup);
    expect(draft.dropoff).toEqual(ride.dropoff);
    expect(draft.pickupIsCurrent).toBe(false);
    expect([draft.promoCode, draft.note, draft.rider]).toEqual([null, '', null]);
  });

  it('message to the person riding names them and links the live page', () => {
    const ride = makeRide({ rider_name: 'María José', dropoff: { lat: 0, lng: 0, address: 'Sambil, Chacao' } });
    const text = riderShareMessage(ride, 'https://kuulis.example/v/abc', t);
    expect(text.startsWith('María, te pedí una moto')).toBe(true);
    expect(text).toContain('https://kuulis.example/v/abc');
    expect(text).toContain('Destino: Sambil');
  });
});
