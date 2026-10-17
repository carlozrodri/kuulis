import { useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Linking, Share, StyleSheet, View } from 'react-native';

import { Copy, Gift, Ticket, UserPlus } from '@/components/icons';
import { showToast } from '@/components/Toast';
import { Button, Card, Field, IconButton, IconTile, Skeleton, StatusPill, Txt } from '@/components/ui';
import { copyText } from '@/features/wallet/format';
import { useRedeemCode, useReferrals } from '@/hooks/useAccount';
import { apiErrorMessage } from '@/i18n';
import { formatInviteCode, inviteeProgress, inviteeStatus, normalizeInviteCode, whatsappUrl } from '@/lib/profile';
import type { ReferralInvitee } from '@/lib/types';
import { radius, space, useTheme } from '@/theme';

import { Section } from './components';

/** Approved drivers: their invite code, how to send it, what the program pays and what it earned. */
export function InviteCard() {
  const { t } = useTranslation();
  const theme = useTheme();
  const referrals = useReferrals();
  const data = referrals.data;

  if (referrals.isPending) return <Skeleton height={180} radius={radius.card} />;
  if (!data?.code) return null;

  const code = formatInviteCode(data.code);
  const program = data.program;
  const message = data.share_url ? t('profile.invite.messageLink', { code, link: data.share_url }) : t('profile.invite.message', { code });
  const earned = Number.parseFloat(data.earned_usd ?? '0');

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
          {program?.active ? (
            <>
              <Txt variant="caption" color="muted">
                {t('profile.invite.body', { amount: program.reward_usd, trips: program.required_trips, days: program.window_days })}
              </Txt>
              {program.referred_free_month ? (
                <Txt variant="caption" color="muted">
                  {t('profile.invite.bodyFreeMonth')}
                </Txt>
              ) : null}
            </>
          ) : (
            <Txt variant="caption" color="muted">
              {t('profile.invite.paused')}
            </Txt>
          )}
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
      {program?.active ? <Button title={t('profile.invite.whatsapp')} variant="accent" size="sm" onPress={() => void sendWhatsApp()} /> : null}
      <View style={styles.stats}>
        <StatusPill label={t('profile.invite.invited', { count: data.invited })} tone="info" />
        <StatusPill label={t('profile.invite.rewarded', { count: data.rewarded })} tone="success" />
        {earned > 0 ? <StatusPill label={t('profile.invite.earned', { amount: data.earned_usd })} tone="accent" dot /> : null}
        {data.free_months ? <StatusPill label={t('profile.invite.freeMonths', { count: data.free_months })} tone="accent" dot /> : null}
      </View>
    </Card>
  );
}

/** "Tus invitados": each invited driver with their progress towards the reward. */
export function InviteesSection() {
  const { t } = useTranslation();
  const data = useReferrals().data;
  if (!data?.code || !data.invitees?.length) return null;
  return (
    <Section title={t('profile.invite.invitees')}>
      <Card style={{ gap: space.md }}>
        {data.invitees.map((invitee, index) => (
          <InviteeRow key={`${invitee.joined_at}-${index}`} invitee={invitee} />
        ))}
        <Txt variant="caption" color="muted">
          {t('profile.invite.rules')}
        </Txt>
      </Card>
    </Section>
  );
}

function InviteeRow({ invitee }: { invitee: ReferralInvitee }) {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const status = inviteeStatus(invitee);
  const showProgress = invitee.status === 'pending' && invitee.approved;
  const deadline = invitee.deadline_at
    ? new Date(invitee.deadline_at).toLocaleDateString(i18n.language, { day: 'numeric', month: 'long' })
    : null;
  return (
    <View style={{ gap: space.xs }}>
      <View style={styles.row}>
        <Txt style={{ flex: 1 }} numberOfLines={1}>
          {invitee.name}
        </Txt>
        <StatusPill label={t(`profile.invite.status.${status.key}`, status.values)} tone={status.tone} />
      </View>
      {showProgress ? (
        <>
          <View
            style={[styles.track, { backgroundColor: theme.divider }]}
            accessibilityRole="progressbar"
            accessibilityValue={{ min: 0, max: invitee.required_trips, now: invitee.trips }}
          >
            <View style={[styles.fill, { backgroundColor: theme.accent, width: `${Math.round(inviteeProgress(invitee) * 100)}%` }]} />
          </View>
          {deadline ? (
            <Txt variant="caption" color="muted">
              {t('profile.invite.deadline', { date: deadline })}
            </Txt>
          ) : null}
        </>
      ) : null}
    </View>
  );
}

/** A new driver (before the first trip) types the code of whoever invited them. */
export function RedeemSection() {
  const { t } = useTranslation();
  const referrals = useReferrals();
  const redeem = useRedeemCode();
  // Opened from the web invite page (kuulis://profile/invite?code=AB3K7Q): the code comes typed.
  const params = useLocalSearchParams<{ code?: string }>();
  const [code, setCode] = useState(() => formatInviteCode(typeof params.code === 'string' ? params.code : ''));
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
          {t('profile.invite.redeemBody', { trips: data.program?.required_trips ?? 20 })}
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
  track: { height: 6, borderRadius: 3, overflow: 'hidden' },
  fill: { height: 6, borderRadius: 3 },
});
