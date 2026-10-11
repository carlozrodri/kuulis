import { router } from 'expo-router';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { ChevronLeft, Hash, Info, RotateCcw, Smartphone } from '@/components/icons';
import { Button, Card, ErrorText, IconButton, IconTile, ListRow, Notice, Row, Screen, Txt, Wordmark } from '@/components/ui';
import { useAppUpdate } from '@/hooks/useAppUpdate';
import { apiErrorMessage } from '@/i18n';
import { appVersion, formatMegabytes } from '@/lib/appVersion';
import { space } from '@/theme';

import { InstallControls } from './UpdateControls';

const back = () => (router.canGoBack() ? router.back() : router.replace('/profile'));

/** Perfil → Acerca de: which build this is and "Buscar actualizaciones" (doc 09). */
export function AboutScreen() {
  const { t } = useTranslation();
  const update = useAppUpdate();
  const [checking, setChecking] = useState(false);
  const [checked, setChecked] = useState(false);
  const [error, setError] = useState<string>();

  async function check() {
    setChecking(true);
    setError(undefined);
    const result = await update.query.refetch();
    if (result.error) setError(apiErrorMessage(result.error));
    setChecked(true);
    setChecking(false);
  }

  const latest = update.latest;
  return (
    <Screen
      header={
        <Row style={{ paddingTop: space.xs, paddingBottom: space.md }}>
          <IconButton icon={ChevronLeft} label={t('common.back')} onPress={back} />
        </Row>
      }>
      <View style={{ alignItems: 'flex-start', gap: space.sm, marginBottom: space.lg }}>
        <IconTile icon={Info} tone="primary" size={56} />
        <Txt variant="title" accessibilityRole="header">
          {t('about.title')}
        </Txt>
        <Wordmark size={28} />
      </View>

      <Card style={{ paddingVertical: space.xxs }}>
        <ListRow icon={Smartphone} iconTone="neutral" title={t('about.version')} subtitle={appVersion.version || 'dev'} divider />
        <ListRow icon={Hash} iconTone="neutral" title={t('about.build')} subtitle={appVersion.build ? String(appVersion.build) : '—'} divider />
        <ListRow icon={RotateCcw} iconTone="neutral" title={t('about.channel')} subtitle={t(`about.channels.${appVersion.channel}`)} />
      </Card>

      <View style={{ marginTop: space.xl, gap: space.md }}>
        {!update.enabled ? (
          <Notice tone="info">{t('about.unsupported')}</Notice>
        ) : update.available && latest ? (
          <Notice tone={update.required ? 'warning' : 'info'} title={t('about.available', { version: latest.version })}>
            <Txt variant="caption" style={{ fontSize: 14, lineHeight: 20 }}>
              {latest.notes || t('about.availableBody', { size: formatMegabytes(latest.size) })}
            </Txt>
          </Notice>
        ) : checked && !error ? (
          <Notice tone="success">{t('about.upToDate')}</Notice>
        ) : null}
        <ErrorText>{error}</ErrorText>
        {update.enabled && update.available && latest ? (
          <InstallControls />
        ) : (
          <Button
            title={t('about.check')}
            variant="secondary"
            icon={RotateCcw}
            loading={checking}
            disabled={!update.enabled}
            onPress={() => void check()}
          />
        )}
      </View>
    </Screen>
  );
}
