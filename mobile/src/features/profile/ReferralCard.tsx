import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Linking, Share, StyleSheet, View } from 'react-native';

import { Copy, Gift, Ticket, UserPlus } from '@/components/icons';
import { showToast } from '@/components/Toast';
import { Button, Card, Field, IconButton, IconTile, Skeleton, StatusPill, Txt } from '@/components/ui';
import { copyText } from '@/features/wallet/format';
import { useRedeemCode, useReferrals } from '@/hooks/useAccount';
import { apiErrorMessage } from '@/i18n';
import { formatInviteCode, normalizeInviteCode, whatsappUrl } from '@/lib/profile';
import { radius, space, useTheme } from '@/theme';

import { Section } from './components';

/** Approved drivers: their invite code, how to send it and the free months it earned. */
export function InviteCard() {
  const { t } = useTranslation();
  const theme = useTheme();
  const referrals = useReferrals();
  const data = referrals.data;

  if (referrals.isPending) return <Skeleton height={180} radius={radius.card} />;
  if (!data?.code) return null;

  const code = formatInviteCode(data.code);
  const message = t('profile.invite.message', { code });

  async function sendWhatsApp() {
    try {
      await Linking.openURL(whatsappUrl(message));
    } catch {
      await Share.share({ message }).catch(() => undefined);
    }
  }

  return (
    <Card tone="accent" style={{ gap: space.md }}>
      <View style={styles.row}>
        <IconTile icon={UserPlus} tone="accent" size={52} />
        <View style={{ flex: 1, gap: 4 }}>
          <Txt variant="subtitle">{t('profile.invite.title')}</Txt>
          <Txt variant="caption" color="muted">
            {t('profile.invite.body')}
          </Txt>
        </View>
      </View>
      <View style={[styles.code, { backgroundColor: theme.surface, borderColor: theme.divider }]}>
        <View style={{ flex: 1 }}>
          <Txt variant="label" color="muted">
            {t('profile.invite.yourCode')}
          </Txt>
          <Txt variant="title" tabular>
            {code}
          </Txt>
        </View>
        <IconButton icon={Copy} label={t('profile.invite.copy')} tone="plain" onPress={() => void copyText(data.code!, t('profile.invite.copied'))} />
      </View>
      <Button title={t('profile.invite.whatsapp')} variant="accent" size="sm" onPress={() => void sendWhatsApp()} />
      <View style={styles.stats}>
        <StatusPill label={t('profile.invite.invited', { count: data.invited })} tone="info" />
        <StatusPill label={t('profile.invite.rewarded', { count: data.rewarded })} tone="success" />
        {data.free_months ? <StatusPill label={t('profile.invite.freeMonths', { count: data.free_months })} tone="accent" dot /> : null}
      </View>
    </Card>
  );
}

/** A new driver (before the first trip) types the code of whoever invited them. */
export function RedeemSection() {
  const { t } = useTranslation();
  const referrals = useReferrals();
  const redeem = useRedeemCode();
  const [code, setCode] = useState('');
  const data = referrals.data;

  if (!data) return null;
  if (data.referred_by) {
    return (
      <Section title={t('profile.invite.redeemTitle')}>
        <Card style={styles.row}>
          <IconTile icon={Gift} tone="success" />
          <Txt style={{ flex: 1 }}>{t('profile.invite.referredBy', { name: data.referred_by })}</Txt>
        </Card>
      </Section>
    );
  }
  if (!data.can_redeem) return null;

  const clean = normalizeInviteCode(code);
  const submit = () =>
    redeem.mutate(clean, {
      onSuccess: () => {
        setCode('');
        showToast(t('profile.invite.redeemed'), 'success');
      },
      onError: (error) => showToast(apiErrorMessage(error), 'danger'),
    });

  return (
    <Section title={t('profile.invite.redeemTitle')}>
      <Card style={{ gap: space.sm }}>
        <Txt variant="caption" color="muted">
          {t('profile.invite.redeemBody')}
        </Txt>
        <Field
          label={t('profile.invite.codeLabel')}
          icon={Ticket}
          value={code}
          onChangeText={setCode}
          autoCapitalize="characters"
          autoCorrect={false}
          maxLength={8}
          placeholder="AB3 K7Q"
          returnKeyType="done"
          onSubmitEditing={() => clean.length === 6 && submit()}
        />
        <Button title={t('profile.invite.redeem')} size="sm" disabled={clean.length !== 6} loading={redeem.isPending} onPress={submit} />
      </Card>
    </Section>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: space.md },
  code: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.sm,
    borderRadius: radius.tile,
    borderWidth: 1,
    paddingHorizontal: space.md,
    paddingVertical: space.sm,
  },
  stats: { flexDirection: 'row', flexWrap: 'wrap', gap: space.xs },
});
