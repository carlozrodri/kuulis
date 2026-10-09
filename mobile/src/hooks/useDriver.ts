import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { ApiError, api } from '@/lib/api';
import { DEFAULT_APP_CONFIG } from '@/lib/driver';
import type { AppConfig, DocumentKind, DriverPersonalInput, DriverProfile, VehicleInput } from '@/lib/types';
import { type LocalFile, uploadDriverDocument } from '@/lib/upload';

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

export const useSaveVehicle = () =>
  useProfileMutation((input: VehicleInput) => api<DriverProfile>('/drivers/me/vehicle', { method: 'PUT', body: input }));

export const useUploadDocument = () =>
  useProfileMutation(({ kind, file }: { kind: DocumentKind; file: LocalFile }) => uploadDriverDocument(kind, file));

export const useDeleteDocument = () =>
  useProfileMutation((id: string) => api<DriverProfile>(`/drivers/me/documents/${id}`, { method: 'DELETE' }));

export const useSubmitDriver = () =>
  useProfileMutation(() => api<DriverProfile>('/drivers/me/submit', { method: 'POST' }));
