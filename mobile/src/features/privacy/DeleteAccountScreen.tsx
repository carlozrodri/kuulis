import { router } from 'expo-router';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { Archive, ChevronLeft, Trash, UserX, Wallet } from '@/components/icons';
import { showToast } from '@/components/Toast';
import { Button, Card, ErrorText, IconButton, IconTile, Notice, Row, Screen, Txt } from '@/components/ui';
import { CheckRow } from '@/features/legal/CheckRow';
import { useWallet } from '@/hooks/useWallet';
import { apiErrorMessage } from '@/i18n';
import { api } from '@/lib/api';
import { formatAmount, parseAmount } from '@/lib/money';
import { useAuth } from '@/providers/AuthProvider';
import { space } from '@/theme';

const back = () => (router.canGoBack() ? router.back() : router.replace('/profile'));

/**
 * Perfil → Seguridad → Eliminar mi cuenta: what is erased, what Kuulis keeps without naming the person, the
 * wallet balance that is lost and the 30 days to change one's mind. The API refuses while there is an active
 * ride, an open report about the user or an unpaid fee, and the message says which.
 */
export function DeleteAccountScreen() {
  const { t } = useTranslation();
  const { signOut } = useAuth();
  const wallet = useWallet();
  const balance = parseAmount(wallet.data?.balance) ?? 0;
  const [understood, setUnderstood] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string>();

  async function remove() {
    setSaving(true);
    setError(undefined);
    try {
      await api('/users/me', { method: 'DELETE' });
    } catch (err) {
      setError(apiErrorMessage(err));
      setSaving(false);
      return;
    }
    showToast(t('profile.deactivate.done'), 'info');
    await signOut();
  }

  return (
    <Screen
      header={
        <Row style={{ paddingTop: space.xs, paddingBottom: space.md }}>
          <IconButton icon={ChevronLeft} label={t('common.back')} onPress={back} />
        </Row>
      }
      footer={
        <View style={{ gap: space.xs }}>
          <ErrorText>{error}</ErrorText>
          <Button
            title={t('profile.deactivate.confirm')}
            variant="danger"
            icon={UserX}
            loading={saving}
            disabled={!understood}
            onPress={() => void remove()}
          />
        </View>
      }>
      <View style={{ alignItems: 'flex-start', gap: space.sm, marginBottom: space.lg }}>
        <IconTile icon={UserX} tone="danger" size={56} />
        <Txt variant="title" accessibilityRole="header">
          {t('profile.deactivate.confirmTitle')}
        </Txt>
        <Txt color="muted">{t('privacy.delete.intro')}</Txt>
      </View>

      <View style={{ gap: space.md }}>
        <Explain icon={Trash} title={t('privacy.delete.erasedTitle')} body={t('privacy.delete.erasedBody')} />
        <Explain icon={Archive} title={t('privacy.delete.keptTitle')} body={t('privacy.delete.keptBody')} />
        {balance > 0 ? (
          <Notice tone="warning" icon={Wallet} title={t('privacy.delete.balanceTitle', { amount: formatAmount(balance) })}>
            {t('privacy.delete.balanceBody')}
          </Notice>
        ) : null}
        <Notice tone="info">{t('privacy.delete.blocks')}</Notice>
        <CheckRow checked={understood} onChange={setUnderstood}>
          {t('privacy.delete.check')}
        </CheckRow>
      </View>
    </Screen>
  );
}

function Explain({ icon, title, body }: { icon: typeof Trash; title: string; body: string }) {
  return (
    <Card style={{ flexDirection: 'row', gap: space.md, alignItems: 'flex-start' }}>
      <IconTile icon={icon} tone="neutral" />
      <View style={{ flex: 1, gap: 2 }}>
        <Txt variant="bodyStrong">{title}</Txt>
        <Txt variant="caption" color="muted">
          {body}
        </Txt>
      </View>
    </Card>
  );
}
