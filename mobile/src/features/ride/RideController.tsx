import { useQueryClient } from '@tanstack/react-query';
import { activateKeepAwakeAsync, deactivateKeepAwake } from 'expo-keep-awake';
import { router, usePathname } from 'expo-router';
import { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { AppState } from 'react-native';

import { showToast } from '@/components/Toast';
import { IncomingOffer } from '@/features/driver/IncomingOffer';
import { useDriverProfile } from '@/hooks/useDriver';
import { getLastPosition, useUserLocation } from '@/hooks/useLocation';
import { useRealtimeContext, useRealtimeEvent } from '@/hooks/useRealtime';
import {
  applyDriverLocation,
  applyMessage,
  applyRide,
  rideKeys,
  setDriverOffer,
  useActiveRide,
  useDriverState,
  usePendingRating,
} from '@/hooks/useRides';
import { api } from '@/lib/api';
import { setBackgroundLocation } from '@/lib/backgroundLocation';
import { confirmHaptic, heavyHaptic, preloadRideSounds, tick } from '@/lib/feedback';
import { isActiveStatus, rideRole, rideRoleStrict } from '@/lib/ride';
import type { DriverLocationEvent, DriverState, Offer, Ride, RideMessage } from '@/lib/types';
import { useAuth } from '@/providers/AuthProvider';
import { useMode } from '@/providers/ModeProvider';

import { bumpUnread, chatOpen, routedRides } from './store';

/**
 * Keeps ride state in sync: applies WS events to the query cache, re-syncs after a reconnect or when the
 * app returns to the foreground, and announces status changes.
 */
export function RideSync() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const { generation } = useRealtimeContext();
  const { mode } = useMode();
  const modeRef = useRef(mode);
  useEffect(() => {
    modeRef.current = mode;
  }, [mode]);

  const resync = () => {
    void queryClient.invalidateQueries({ queryKey: rideKeys.all });
    void queryClient.invalidateQueries({ queryKey: rideKeys.driverState });
  };
  const resyncRef = useRef(resync);
  useEffect(() => {
    resyncRef.current = resync;
  });

  // A new socket session may have missed events: fetch the truth again.
  useEffect(() => {
    if (generation > 1) resyncRef.current();
  }, [generation]);

  useEffect(() => {
    const sub = AppState.addEventListener('change', (state) => {
      if (state === 'active') resyncRef.current();
    });
    return () => sub.remove();
  }, []);

  useRealtimeEvent<Ride>('ride.updated', (ride) => {
    if (!ride?.id) return;
    const before = queryClient.getQueryData<Ride>(rideKeys.detail(ride.id))?.status;
    applyRide(queryClient, ride);
    if (before === ride.status) return;
    const role = rideRole(ride, user?.id, modeRef.current ?? 'passenger');
    if (role === 'passenger') {
      if (ride.status === 'driver_assigned') {
        confirmHaptic();
        showToast(t('ride.toast.assigned', { name: ride.driver?.first_name ?? '' }), 'success');
      } else if (ride.status === 'driver_arrived') {
        heavyHaptic();
        showToast(t('ride.toast.arrived'), 'success');
      } else if (ride.status === 'cancelled_by_driver') {
        heavyHaptic();
        showToast(t('ride.toast.driverCancelled'), 'danger');
      } else if (ride.status === 'cancelled_by_admin') {
        heavyHaptic();
        showToast(t('ride.toast.adminCancelled'), 'danger');
      } else if (ride.status === 'no_drivers') {
        showToast(t('ride.toast.noDrivers'), 'danger');
      }
    } else if (ride.status === 'cancelled_by_passenger' || ride.status === 'cancelled_by_admin') {
      heavyHaptic();
      showToast(
        ride.status === 'cancelled_by_admin' ? t('ride.toast.adminCancelled') : t('drive.toast.passengerCancelled'),
        'danger',
      );
    }
  });

  useRealtimeEvent<DriverLocationEvent>('ride.driver_location', (event) => {
    if (event?.ride_id) applyDriverLocation(queryClient, event);
  });

  useRealtimeEvent<RideMessage>('ride.message', (message) => {
    if (!message?.id) return;
    const added = applyMessage(queryClient, message);
    if (message.sender_id === user?.id) return;
    if (!added && queryClient.getQueryData(rideKeys.messages(message.ride_id))) return;
    if (chatOpen.get() === message.ride_id) return;
    bumpUnread(message.ride_id);
    tick();
    showToast(t('chat.newMessage', { text: message.text }));
  });

  useRealtimeEvent<Offer>('ride.offer', (offer) => {
    if (offer?.ride_id) setDriverOffer(queryClient, offer);
  });

  useRealtimeEvent<{ ride_id: string }>('ride.offer_cancelled', (event) => {
    const current = queryClient.getQueryData<DriverState>(rideKeys.driverState)?.current_offer;
    if (current && current.ride_id === event?.ride_id) {
      setDriverOffer(queryClient, null);
      showToast(t('drive.toast.offerGone'));
    }
  });

  return null;
}

/**
 * Sends the user to the right screen: the mandatory rating whenever one is pending, and the live ride
 * screen once per ride (they can leave it; home shows a shortcut back).
 */
export function RideNavigator() {
  const pathname = usePathname();
  const { user } = useAuth();
  const { mode, setMode } = useMode();
  const active = useActiveRide(!!user);
  const pending = usePendingRating(!!user);
  const lastPush = useRef<{ path: string; at: number }>({ path: '', at: 0 });

  useEffect(() => {
    const go = (path: '/ride/rate' | '/ride' | '/drive', id?: string) => {
      const now = Date.now();
      if (lastPush.current.path === path && now - lastPush.current.at < 1500) return;
      lastPush.current = { path, at: now };
      if (path === '/ride/rate') router.push('/ride/rate');
      else router.push({ pathname: path, params: { id: id ?? '' } });
    };

    if (pending.data) {
      // "¿Algo salió mal? Repórtalo" opens the report flow on top of the rating; it comes back to it.
      if (pathname !== '/ride/rate' && !pathname.startsWith('/report')) go('/ride/rate');
      return;
    }
    const ride = active.data;
    if (!ride || !isActiveStatus(ride.status) || !user) return;
    const strict = rideRoleStrict(ride, user.id);
    // Only switch modes when the ride says for sure which side we are on.
    if (mode && strict && strict !== mode) {
      void setMode(strict);
      return;
    }
    const role = strict ?? mode ?? 'passenger';
    if (routedRides.has(ride.id)) return;
    routedRides.add(ride.id);
    const target = role === 'driver' ? '/drive' : '/ride';
    if (pathname === target || pathname.startsWith('/ride/chat')) return;
    go(target, ride.id);
  }, [pending.data, active.data, pathname, mode, setMode, user]);

  return null;
}

/** Sends the driver's position over the socket every ~4 s while online and the app is in the foreground. */
function useLocationBroadcast(enabled: boolean) {
  const { send, status } = useRealtimeContext();
  useUserLocation({ watch: enabled });

  useEffect(() => {
    if (!enabled || status !== 'open') return;
    const push = () => {
      if (AppState.currentState !== 'active') return;
      const position = getLastPosition();
      if (!position) return;
      send({
        type: 'location',
        lat: position.lat,
        lng: position.lng,
        ...(position.heading != null ? { heading: Math.round(position.heading) } : {}),
        ...(position.speed != null ? { speed: Math.round(position.speed * 10) / 10 } : {}),
      });
    };
    push();
    const timer = setInterval(push, 4000);
    return () => clearInterval(timer);
  }, [enabled, status, send]);
}

/**
 * Driver-mode background duties: recovers availability and the current offer on start, broadcasts the
 * location while online (foreground only: background location needs a development build), keeps the screen
 * awake and shows incoming offers full screen.
 */
export function DriverController() {
  const { user } = useAuth();
  const profile = useDriverProfile();
  const approved = profile.data?.status === 'approved';
  const state = useDriverState(approved);
  const active = useActiveRide(!!user);
  const driving = !!active.data && isActiveStatus(active.data.status) && rideRole(active.data, user?.id, 'driver') === 'driver';
  const online = approved && (!!state.data?.online || driving);
  const onlineRef = useRef({ online: false, driving: false });
  useEffect(() => {
    onlineRef.current = { online: !!state.data?.online, driving };
  }, [state.data?.online, driving]);

  useLocationBroadcast(online);

  // Keep sharing the position with the app minimized (Android foreground service) while online.
  const { t } = useTranslation();
  const bgTitle = t('drive.home.bgTitle');
  const bgBody = t('drive.home.bgBody');
  useEffect(() => {
    void setBackgroundLocation(online ? { title: bgTitle, body: bgBody } : null);
  }, [online, bgTitle, bgBody]);
  useEffect(() => () => void setBackgroundLocation(null), []);

  useEffect(() => {
    if (approved) preloadRideSounds();
  }, [approved]);

  useEffect(() => {
    if (!online) return;
    void activateKeepAwakeAsync('kuulis-driver').catch(() => undefined);
    return () => {
      void deactivateKeepAwake('kuulis-driver').catch(() => undefined);
    };
  }, [online]);

  // Leaving driver mode while online (switching to passenger) disconnects, unless a ride is in progress.
  useEffect(
    () => () => {
      if (onlineRef.current.online && !onlineRef.current.driving) {
        void api('/drivers/me/offline', { method: 'POST' }).catch(() => undefined);
      }
    },
    [],
  );

  const offer = state.data?.current_offer ?? null;
  return approved && !driving ? <IncomingOffer offer={offer} /> : null;
}
