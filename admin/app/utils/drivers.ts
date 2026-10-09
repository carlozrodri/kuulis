import type { DocumentStatus, DriverStatus } from '~/types/api'

type BadgeColor = 'neutral' | 'info' | 'success' | 'error' | 'warning' | 'primary'

export const driverStatusColor: Record<DriverStatus, BadgeColor> = {
  draft: 'neutral',
  pending_review: 'warning',
  approved: 'success',
  rejected: 'error',
  suspended: 'neutral',
}

export const documentStatusColor: Record<DocumentStatus, BadgeColor> = {
  pending: 'warning',
  approved: 'success',
  rejected: 'error',
}

export type DriverAction = 'approve' | 'reject' | 'suspend' | 'reinstate'

/** Profile transitions the API allows from each status (see docs/api/phase-1a.md). */
export const driverActions: Record<DriverStatus, DriverAction[]> = {
  draft: [],
  pending_review: ['approve', 'reject'],
  approved: ['suspend'],
  rejected: [],
  suspended: ['reinstate'],
}

/** Browsers cannot render HEIC inline, so those open in a new tab like PDFs. */
export function isPreviewableImage(contentType: string): boolean {
  return contentType.startsWith('image/') && !/hei[cf]/i.test(contentType)
}
