import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { ApiError, api } from '@/lib/api';
import { DEFAULT_APP_CONFIG } from '@/lib/driver';
import type {
  AppConfig,
  DocumentKind,
  DriverCheck,
  DriverPersonalInput,
  DriverProfile,
  VehicleInput,
} from '@/lib/types';
import { type CheckFileKind, type LocalFile, uploadCheckFile, uploadDriverDocument } from '@/lib/upload';

export const DRIVER_QUERY_KEY = ['drivers', 'me'] as const;
export const CONFIG_QUERY_KEY = ['config', 'public'] as const;

/** Push data is {type: "driver_status" | "driver_document", ...}; inbox events wrap it in `data`. */
export function isDriverNotification(payload: unknown): boolean {
  const record = payload as { type?: unknown; data?: { type?: unknown } } | null | undefined;
  const typeValue = record?.type ?? record?.data?.type;
  return typeof typeValue === 'string' && typeValue.startsWith('driver_');
}

/** Admin-editable rules (minimum age, vehicle year, required documents). Falls back to the documented defaults. */
export function useAppConfig() {
  const query = useQuery({
    queryKey: CONFIG_QUERY_KEY,
    queryFn: () => api<AppConfig>('/config/public', { auth: false }),
    staleTime: 10 * 60_000,
  });
  return { ...query, config: query.data ?? DEFAULT_APP_CONFIG };
}

/** The signed-in user's driver profile, or null when they have not started (404 driver_not_found). */
export function useDriverProfile(enabled = true) {
  return useQuery({
    queryKey: DRIVER_QUERY_KEY,
    enabled,
    queryFn: async () => {
      try {
        return await api<DriverProfile>('/drivers/me');
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) return null;
        throw error;
      }
    },
  });
}

function useProfileMutation<TInput>(mutationFn: (input: TInput) => Promise<DriverProfile>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: (profile) => {
      if (profile) queryClient.setQueryData(DRIVER_QUERY_KEY, profile);
      else void queryClient.invalidateQueries({ queryKey: DRIVER_QUERY_KEY });
    },
    onError: () => void queryClient.invalidateQueries({ queryKey: DRIVER_QUERY_KEY }),
  });
}

export const useSavePersonal = () =>
  useProfileMutation((input: DriverPersonalInput) => api<DriverProfile>('/drivers/me', { method: 'PUT', body: input }));

/** Driver switches (PATCH /drivers/me/preferences), e.g. hiding their trips from "Caracas en movimiento". */
export const useSavePreferences = () =>
  useProfileMutation((input: { hide_from_public_activity?: boolean }) =>
    api<DriverProfile>('/drivers/me/preferences', { method: 'PATCH', body: input }),
  );

export const useSaveVehicle = () =>
  useProfileMutation((input: VehicleInput) => api<DriverProfile>('/drivers/me/vehicle', { method: 'PUT', body: input }));

export const useUploadDocument = () =>
  useProfileMutation(({ kind, file, expiresOn }: { kind: DocumentKind; file: LocalFile; expiresOn?: string | null }) =>
    uploadDriverDocument(kind, file, expiresOn),
  );

/** Doc 12: the expiry of an approved document that has none ("Indicar fecha"). */
export const useSetDocumentExpiry = () =>
  useProfileMutation(({ id, expiresOn }: { id: string; expiresOn: string }) =>
    api<DriverProfile>(`/drivers/me/documents/${id}`, { method: 'PATCH', body: { expires_on: expiresOn } }),
  );

/** Uploads files one by one, reporting "n of total" so long uploads on mobile data show progress. */
async function uploadAll(
  files: { kind: CheckFileKind; file: LocalFile }[],
  onProgress?: (done: number, total: number) => void,
) {
  const keys: { kind: CheckFileKind; key: string }[] = [];
  onProgress?.(0, files.length);
  for (const { kind, file } of files) {
    keys.push({ kind, key: await uploadCheckFile(kind, file) });
    onProgress?.(keys.length, files.length);
  }
  return keys;
}

/** Doc 12: sends the live selfie (and moto photos for a re-verification) asked for; going online works right after. */
export function useSubmitCheck() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      checkId,
      files,
      onProgress,
    }: {
      checkId: string;
      files: { kind: CheckFileKind; file: LocalFile }[];
      onProgress?: (done: number, total: number) => void;
    }) => {
      const keys = await uploadAll(files, onProgress);
      return api<DriverCheck>(`/drivers/me/checks/${checkId}/submit`, { method: 'POST', body: { files: keys } });
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: DRIVER_QUERY_KEY }),
  });
}

/** Doc 12: a new moto for review; the current one keeps working until it is approved. */
export const useChangeVehicle = () =>
  useProfileMutation(
    async ({
      vehicle,
      registration,
      expiresOn,
      photos,
      onProgress,
    }: {
      vehicle: VehicleInput;
      registration: LocalFile;
      expiresOn: string;
      photos: LocalFile[];
      onProgress?: (done: number, total: number) => void;
    }) => {
      const keys = await uploadAll(
        [
          { kind: 'vehicle_registration', file: registration },
          ...photos.map((file) => ({ kind: 'vehicle_photo' as const, file })),
        ],
        onProgress,
      );
      return api<DriverProfile>('/drivers/me/vehicles', {
        method: 'POST',
        body: {
          vehicle,
          registration_key: keys[0].key,
          registration_expires_on: expiresOn,
          photo_keys: keys.slice(1).map((item) => item.key),
        },
      });
    },
  );

export const useCancelVehicleChange = () =>
  useProfileMutation(() => api<DriverProfile>('/drivers/me/vehicles/pending', { method: 'DELETE' }));

export const useDeleteDocument = () =>
  useProfileMutation((id: string) => api<DriverProfile>(`/drivers/me/documents/${id}`, { method: 'DELETE' }));

export const useSubmitDriver = () =>
  useProfileMutation(() => api<DriverProfile>('/drivers/me/submit', { method: 'POST' }));
