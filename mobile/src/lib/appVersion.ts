import * as Application from 'expo-application';
import { Platform } from 'react-native';

import { config } from './config';

/** Release channel of the API's APK catalogue (doc 09). QA builds and local dev clients follow "qa". */
export type AppChannel = 'qa' | 'beta' | 'production';

export function channelFor(appEnv: string): AppChannel {
  return appEnv === 'production' ? 'production' : 'qa';
}

/** Android versionCode as a number; 0 when missing (web, Expo Go) or not numeric. */
export function parseBuild(raw: string | null | undefined): number {
  const build = Number(raw);
  return raw && Number.isInteger(build) && build > 0 ? build : 0;
}

/** What this binary is: sent on every request and used to look for a newer APK. */
export const appVersion = {
  platform: Platform.OS === 'android' || Platform.OS === 'ios' ? Platform.OS : 'web',
  version: Application.nativeApplicationVersion ?? '',
  build: Platform.OS === 'web' ? 0 : parseBuild(Application.nativeBuildVersion),
  channel: channelFor(config.appEnv),
} as const;

/** Lets the API count builds in use and refuse ride actions from builds below a mandatory release. */
export const APP_VERSION_HEADERS: Record<string, string> = {
  'X-App-Platform': appVersion.platform,
  'X-App-Version': appVersion.version,
  'X-App-Build': String(appVersion.build),
  'X-App-Channel': appVersion.channel,
};

/** Only installed Android builds can download and install an APK (dev clients report build 0 or skip). */
export const canSelfUpdate = Platform.OS === 'android' && appVersion.build > 0;

/** 12_345_678 bytes → "11.8" (MB, one decimal). */
export function formatMegabytes(bytes: number): string {
  return (bytes / 1_000_000).toFixed(1);
}

/** The downloaded APK is the published one: same size and same MD5 (hex, any case). */
export function checksumMatches(
  downloaded: { size?: number | null; md5?: string | null },
  release: { size: number; md5: string },
): boolean {
  if (!downloaded.md5 || !release.md5) return false;
  return downloaded.size === release.size && downloaded.md5.toLowerCase() === release.md5.toLowerCase();
}

/** Download progress 0..1, falling back to the release size when the server sends no Content-Length. */
export function downloadFraction(bytesWritten: number, totalBytes: number, releaseSize: number): number {
  const total = totalBytes > 0 ? totalBytes : releaseSize;
  if (total <= 0) return 0;
  return Math.min(1, Math.max(0, bytesWritten / total));
}
