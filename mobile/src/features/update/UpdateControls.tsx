import * as Application from 'expo-application';
import { useTranslation } from 'react-i18next';
import { Linking, View } from 'react-native';

import { Download, Settings } from '@/components/icons';
import { Button, ErrorText, Notice, Txt } from '@/components/ui';
import { useAppUpdate } from '@/hooks/useAppUpdate';
import { fromPlayStore } from '@/lib/appVersion';
import { useStore } from '@/lib/store';
import { space } from '@/theme';

import { downloadAndInstall, installState, openUnknownSourcesSettings, type InstallState } from './install';

/** Download state shared by every update entry point, and the action that starts it. */
export function useInstaller() {
  const update = useAppUpdate();
  const state = useStore(installState);
  const busy = state.step === 'downloading' || state.step === 'verifying' || state.step === 'installing';

  async function start() {
    // The presigned link lasts about an hour: ask for a fresh one right before downloading.
    const fresh = await update.query.refetch().catch(() => null);
    const release = fresh?.data?.latest ?? update.latest;
    if (!release) {
      installState.set({ step: 'error', reason: 'no_release' });
      return;
    }
    await downloadAndInstall(release);
  }

  return { state, busy, start: () => void start() };
}

/** The app's page in Google Play, in the Play app when it is there. */
async function openPlayStore() {
  const id = Application.applicationId ?? '';
  await Linking.openURL(`market://details?id=${id}`).catch(() =>
    Linking.openURL(`https://play.google.com/store/apps/details?id=${id}`).catch(() => undefined),
  );
}

/**
 * "Actualizar" (showing the download percentage while it runs) plus what went wrong, if anything. A build from
 * Google Play opens its page in Play instead: Play installs the update.
 */
export function InstallControls({ size = 'md' }: { size?: 'sm' | 'md' }) {
  const { t } = useTranslation();
  if (fromPlayStore) {
    return (
      <Button
        title={t('update.playStore')}
        icon={Download}
        size={size}
        style={size === 'sm' ? { alignSelf: 'flex-start' } : undefined}
        onPress={() => void openPlayStore()}
      />
    );
  }
  return <ApkInstallControls size={size} />;
}

function ApkInstallControls({ size }: { size: 'sm' | 'md' }) {
  const { t } = useTranslation();
  const { state, busy, start } = useInstaller();
  const title =
    state.step === 'downloading'
      ? t('update.downloading', { percent: Math.round(state.progress * 100) })
      : state.step === 'verifying'
        ? t('update.verifying')
        : state.step === 'installing'
          ? t('update.installing')
          : t('update.button');
  return (
    <View style={{ gap: space.xs }}>
      <InstallFeedback state={state} />
      <Button
        title={title}
        icon={Download}
        size={size}
        disabled={busy}
        style={size === 'sm' ? { alignSelf: 'flex-start' } : undefined}
        onPress={start}
      />
    </View>
  );
}

/** Error text, or how to allow "install unknown apps" when the installer came back without updating. */
function InstallFeedback({ state }: { state: InstallState }) {
  const { t } = useTranslation();
  if (state.step === 'returned' || (state.step === 'error' && state.reason === 'installer')) {
    return (
      <Notice tone="warning" title={t('update.unknownSources.title')}>
        <Txt variant="caption" style={{ fontSize: 14, lineHeight: 20 }}>
          {t('update.unknownSources.body')}
        </Txt>
        <Button
          title={t('update.unknownSources.open')}
          icon={Settings}
          variant="secondary"
          size="sm"
          style={{ alignSelf: 'flex-start', marginTop: space.xs }}
          onPress={() => void openUnknownSourcesSettings()}
        />
      </Notice>
    );
  }
  if (state.step === 'error') return <ErrorText>{t(`update.error.${state.reason}`)}</ErrorText>;
  return null;
}
