import { useNetInfo } from '@react-native-community/netinfo';

/** True only when the phone says it has no network (unknown counts as online, doc 20). */
export function useIsOffline(): boolean {
  const net = useNetInfo();
  return net.isConnected === false || net.isInternetReachable === false;
}
