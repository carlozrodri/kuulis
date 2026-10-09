import { Bike, FileText, type Icon, IdCard, ScanFace, ShieldCheck } from '@/components/icons';
import type { Tone } from '@/components/ui';
import type { DocumentState, DriverStep } from '@/lib/driver';
import type { DocumentKind } from '@/lib/types';

export const DOCUMENT_ICONS: Record<DocumentKind, Icon> = {
  id_card: IdCard,
  rif: FileText,
  drivers_license: IdCard,
  medical_certificate: ShieldCheck,
  vehicle_registration: FileText,
  selfie: ScanFace,
  vehicle_photo: Bike,
};

export const DOCUMENT_STATE_TONE: Record<DocumentState, Tone> = {
  missing: 'neutral',
  partial: 'warning',
  pending: 'primary',
  approved: 'success',
  rejected: 'danger',
};

export const STEP_HREF = {
  personal: '/driver/personal',
  vehicle: '/driver/vehicle',
  documents: '/driver/documents',
  review: '/driver/review',
} as const satisfies Record<DriverStep, string>;

export const STEP_NUMBER: Record<DriverStep, number> = { personal: 1, vehicle: 2, documents: 3, review: 4 };
