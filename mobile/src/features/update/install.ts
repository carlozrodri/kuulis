import * as Application from 'expo-application';
import { File, Paths } from 'expo-file-system';
import { ActivityAction, startActivityAsync } from 'expo-intent-launcher';

import { checksumMatches, downloadFraction } from '@/lib/appVersion';
import { createStore } from '@/lib/store';
import type { AppRelease } from '@/lib/types';

const APK_MIME = 'application/vnd.android.package-archive';
const ACTION_VIEW = 'android.intent.action.VIEW';
/** Intent.FLAG_GRANT_READ_URI_PERMISSION: the installer may read our content:// URI. */
const FLAG_GRANT_READ_URI_PERMISSION = 1;

export type InstallFailure = 'no_release' | 'download' | 'checksum' | 'installer';

export class InstallError extends Error {
  constructor(public reason: InstallFailure) {
    super(reason);
  }
}

export type InstallState =
  | { step: 'idle' }
  | { step: 'downloading'; progress: number }
  | { step: 'verifying' }
  | { step: 'installing' }
  /** The installer closed without updating: cancelled, or blocked by "install unknown apps". */
  | { step: 'returned' }
  | { step: 'error'; reason: InstallFailure };

/** Shared by the banner, the blocking screen and Acerca de, so a download started in one shows in all. */
export const installState = createStore<InstallState>({ step: 'idle' });

const busy = (state: InstallState) =>
  state.step === 'downloading' || state.step === 'verifying' || state.step === 'installing';

/**
 * Downloads the APK into the cache, checks size and MD5 against the published release and opens the
 * Android installer. A file that does not match is deleted and never offered to the installer.
 * Never throws: progress and failures are reported through `installState`.
 */
export async function downloadAndInstall(release: AppRelease): Promise<void> {
  if (busy(installState.get())) return;
  if (!release.download_url) {
    installState.set({ step: 'error', reason: 'no_release' });
    return;
  }
  installState.set({ step: 'downloading', progress: 0 });
  const destination = new File(Paths.cache, `kuulis-${release.build}.apk`);
  try {
    let file: File | null;
    try {
      if (destination.exists) destination.delete();
      const task = File.createDownloadTask(release.download_url, destination, {
        onProgress: ({ bytesWritten, totalBytes }) =>
          installState.set({ step: 'downloading', progress: downloadFraction(bytesWritten, totalBytes, release.size) }),
      });
      file = await task.downloadAsync();
    } catch {
      throw new InstallError('download');
    }
    if (!file) throw new InstallError('download');

    installState.set({ step: 'verifying' });
    const info = file.info({ md5: true });
    if (!checksumMatches(info, release)) {
      safeDelete(file);
      throw new InstallError('checksum');
    }

    installState.set({ step: 'installing' });
    try {
      await startActivityAsync(ACTION_VIEW, {
        data: file.contentUri,
        flags: FLAG_GRANT_READ_URI_PERMISSION,
        type: APK_MIME,
      });
    } catch {
      throw new InstallError('installer');
    }
    // An installed update replaces the app, so getting here means it was not installed.
    installState.set({ step: 'returned' });
  } catch (error) {
    const reason = error instanceof InstallError ? error.reason : 'download';
    if (reason !== 'installer') safeDelete(destination);
    installState.set({ step: 'error', reason });
  }
}

/** Ajustes → Instalar apps desconocidas → Kuulis (Android 8+ asks once per app that installs APKs). */
export async function openUnknownSourcesSettings(): Promise<void> {
  await startActivityAsync(ActivityAction.MANAGE_UNKNOWN_APP_SOURCES, {
    data: `package:${Application.applicationId ?? ''}`,
  }).catch(() => startActivityAsync(ActivityAction.SECURITY_SETTINGS).catch(() => undefined));
}

function safeDelete(file: File) {
  try {
    if (file.exists) file.delete();
  } catch {
    // Cache files are cleaned by the system anyway.
  }
}
