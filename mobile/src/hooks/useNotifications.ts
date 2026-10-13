import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query';

import { api } from '@/lib/api';
import { withUpdate } from '@/lib/notificationPreferences';
import type { NotificationPreferences, NotificationPreferencesUpdate } from '@/lib/types';

export const NOTIFICATIONS_KEY = ['notifications'] as const;
// Own root so refreshing the inbox (on every push) does not refetch it over an unsaved change.
export const PREFERENCES_KEY = ['notification-preferences'] as const;

/** Marks one inbox item read (for a campaign it also counts as opened) and refreshes the inbox. */
export async function markNotificationRead(queryClient: QueryClient, id: string) {
  try {
    await api(`/notifications/${id}/read`, { method: 'POST' });
  } finally {
    void queryClient.invalidateQueries({ queryKey: NOTIFICATIONS_KEY, exact: true });
  }
}

/** Perfil → Ajustes → Notificaciones. */
export function useNotificationPreferences() {
  return useQuery({
    queryKey: PREFERENCES_KEY,
    queryFn: () => api<NotificationPreferences>('/notifications/preferences'),
  });
}

/** Saves a change right away: the screen shows it at once and goes back if the API says no. */
export function useUpdateNotificationPreferences() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (update: NotificationPreferencesUpdate) =>
      api<NotificationPreferences>('/notifications/preferences', { method: 'PUT', body: update }),
    onMutate: async (update) => {
      await queryClient.cancelQueries({ queryKey: PREFERENCES_KEY });
      const previous = queryClient.getQueryData<NotificationPreferences>(PREFERENCES_KEY);
      if (previous) queryClient.setQueryData(PREFERENCES_KEY, withUpdate(previous, update));
      return { previous };
    },
    onError: (_error, _update, context) => {
      if (context?.previous) queryClient.setQueryData(PREFERENCES_KEY, context.previous);
    },
    onSuccess: (saved) => queryClient.setQueryData(PREFERENCES_KEY, saved),
  });
}
