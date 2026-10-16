import type { Ride, User } from '@/lib/types';

export const PASSENGER_ID = 'p-1';
export const DRIVER_ID = 'd-1';

export function makeRide(fields: Partial<Ride> = {}): Ride {
  return {
    id: 'r-1',
    status: 'driver_assigned',
    vehicle_type: 'moto',
    pickup: { lat: 10.49, lng: -66.88, address: 'Plaza Altamira' },
    dropoff: { lat: 10.5, lng: -66.85, address: 'Los Dos Caminos' },
    distance_m: 3200,
    duration_s: 600,
    fare: '2.50',
    surge_multiplier: '1.00',
    payment_method: 'cash_usd',
    polyline: null,
    passenger: { id: PASSENGER_ID, first_name: 'Ana', rating: '4.9' },
    driver: {
      id: DRIVER_ID,
      first_name: 'Luis',
      rating: '4.8',
      photo_url: null,
      vehicle: { brand: 'Yamaha', model: 'YBR 125', color: 'Negra', plate: 'AB123CD' },
    },
    driver_location: null,
    requested_at: '2026-10-16T12:00:00Z',
    assigned_at: '2026-10-16T12:01:00Z',
    arrived_at: null,
    started_at: null,
    completed_at: null,
    cancelled_at: null,
    cancel_reason: null,
    my_rating: null,
    ...fields,
  } as Ride;
}

export function makeUser(fields: Partial<User> = {}): User {
  return { id: PASSENGER_ID, email: 'ana@example.com', full_name: 'Ana Pérez', locale: 'es', pending_legal: [], ...fields } as User;
}
