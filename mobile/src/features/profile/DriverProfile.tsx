import { router } from 'expo-router';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Pressable, StyleSheet, View } from 'react-native';

import { Bike, ChevronDown, ChevronRight, FileText, Gift, LockKeyhole, Receipt, TrendingUp, Wallet } from '@/components/icons';
import { Button, Card, IconTile, ListRow, Skeleton, StatusPill, type Tone, Txt } from '@/components/ui';
import { PlateBadge } from '@/features/ride/components';
import { useWalletFormat } from '@/features/wallet/format';
import { useAppConfig } from '@/hooks/useDriver';
import { useSubscription, useWallet } from '@/hooks/useWallet';
import { documentChecklist, type DocumentState } from '@/lib/driver';
import { formatFare } from '@/lib/ride';
import type { DriverProfile as Driver, DriverStats } from '@/lib/types';
import { pendingTotal, subscriptionState } from '@/lib/wallet';
import { radius, space, useTheme } from '@/theme';

import { Meter, Section } from './components';

const isActiveDriver = (driver: Driver | null | undefined) =>
  driver?.status === 'approved' || driver?.status === 'suspended';

/** Driver side of the profile: application status, or the moto, documents, fee and wallet once approved. */
export function DriverProfile({
  driver,
  loading,
  stats,
}: {
  driver: Driver | null | undefined;
  loading: boolean;
  stats: DriverStats | undefined;
}) {
  const { t } = useTranslation();

  if (loading && driver === undefined) {
    return (
      <View style={{ gap: space.sm, marginTop: space.xl }}>
        <Skeleton height={96} radius={radius.card} />
        <Skeleton height={120} radius={radius.card} />
      </View>
    );
  }
  if (!isActiveDriver(driver)) return <ApplicationCard driver={driver ?? null} />;

  return (
    <>
      {driver?.vehicle ? (
        <Section title={t('profile.driver.vehicle')}>
          <Card style={styles.vehicle}>
            <IconTile icon={Bike} tone="accent" size={52} />
            <View style={{ flex: 1, gap: 2 }}>
              <Txt variant="subtitle" numberOfLines={2}>
                {driver.vehicle.brand} {driver.vehicle.model}
              </Txt>
              <Txt variant="caption" color="muted" numberOfLines={1}>
                {[driver.vehicle.year, driver.vehicle.color].filter(Boolean).join(' · ')}
              </Txt>
            </View>
            <PlateBadge plate={driver.vehicle.plate} />
          </Card>
        </Section>
      ) : null}

      <Section title={t('profile.driver.account')}>
        <SubscriptionRow />
        <DocumentsRow driver={driver!} />
        <Card style={{ paddingVertical: space.xxs }}>
          <ListRow
            icon={TrendingUp}
            title={t('profile.driver.earnings')}
            subtitle={
              stats
                ? t('profile.driver.earningsHint', { amount: formatFare(stats.month.earnings), rides: t('stats.rides', { count: stats.month.rides }) })
                : null
            }
            onPress={() => router.push('/rides')}
          />
        </Card>
      </Section>
    </>
  );
}

/** Not approved yet: where the application stands and the way back into it. */
function ApplicationCard({ driver }: { driver: Driver | null }) {
  const { t } = useTranslation();
  const status = driver?.status ?? 'none';
  const tone: Tone = status === 'rejected' ? 'danger' : status === 'pending_review' ? 'info' : 'accent';
  return (
    <Section title={t('profile.driver.application')}>
      <Card tone={status === 'none' ? 'accent' : 'surface'} style={{ gap: space.md }}>
        <View style={styles.row}>
          <IconTile icon={status === 'none' ? Gift : Bike} tone={tone} size={52} />
          <View style={{ flex: 1, gap: 4 }}>
            <Txt variant="subtitle">{t(`profile.driver.status.${status}.title`)}</Txt>
            <Txt variant="caption" color="muted">
              {t(`profile.driver.status.${status}.body`)}
            </Txt>
          </View>
        </View>
        {status === 'pending_review' ? null : (
          <Button
            title={t(`profile.driver.status.${status}.action`)}
            size="sm"
            variant={status === 'none' ? 'accent' : 'primary'}
            onPress={() => router.push('/')}
          />
        )}
      </Card>
    </Section>
  );
}

/** This month's fee state (free months, estimate, pending or blocked) and the wallet balance. */
function SubscriptionRow() {
  const { t } = useTranslation();
  const theme = useTheme();
  const format = useWalletFormat();
  const subscription = useSubscription();
  const wallet = useWallet();
  const summary = subscription.data;
  const state = subscriptionState(summary);

  let tone: Tone = 'primary';
  let title = t('profile.driver.fee.notStarted');
  let pill: string | null = t('wallet.sub.freeMonthsPill');
  if (summary && state === 'free') {
    tone = 'accent';
    title = t('profile.driver.fee.free');
    pill = summary.free_until ? t('wallet.sub.freeUntil', { date: format.shortDate(summary.free_until) }) : pill;
  } else if (summary && state === 'active') {
    title = t('profile.driver.fee.estimated', { amount: formatFare(summary.estimated_fee), month: format.monthName(summary.month) });
    pill = null;
  } else if (summary && state === 'pending') {
    tone = 'warning';
    title = t('profile.driver.fee.pending', { amount: formatFare(pendingTotal(summary.pending)) });
    pill = null;
  } else if (state === 'blocked') {
    tone = 'danger';
    title = t('profile.driver.fee.blocked');
    pill = null;
  }

  return (
    <Card onPress={() => router.push('/wallet')} accessibilityLabel={`${title}. ${t('wallet.balance')}: ${formatFare(wallet.data?.balance)}`} style={{ gap: space.md }}>
      <View style={styles.row}>
        <IconTile icon={state === 'blocked' ? LockKeyhole : state === 'free' || state === 'not_started' || !summary ? Gift : Receipt} tone={tone} />
        <View style={{ flex: 1, gap: 4 }}>
          <Txt variant="label" color="muted">
            {t('profile.driver.fee.title')}
          </Txt>
          {subscription.isPending ? <Skeleton height={20} width="70%" /> : <Txt variant="bodyStrong">{title}</Txt>}
          {pill && !subscription.isPending ? <StatusPill label={pill} tone={tone === 'primary' ? 'accent' : tone} /> : null}
        </View>
      </View>
      <View style={[styles.balance, { backgroundColor: theme.surfaceAlt }]}>
        <Wallet size={18} color={theme.scheme === 'dark' ? theme.primary : theme.primaryPressed} strokeWidth={2.2} />
        <Txt variant="label" color="muted" style={{ flex: 1 }}>
          {t('wallet.balance')}
        </Txt>
        {wallet.isPending ? (
          <Skeleton height={18} width={60} />
        ) : (
          <Txt variant="bodyStrong" tabular>
            {formatFare(wallet.data?.balance)}
          </Txt>
        )}
        <ChevronRight size={18} color={theme.muted} strokeWidth={2.2} />
      </View>
    </Card>
  );
}

const DOC_TONE: Record<DocumentState, Tone> = {
  approved: 'success',
  pending: 'info',
  rejected: 'danger',
  missing: 'warning',
  partial: 'warning',
};

/** Approved / pending / rejected documents with a bar; tap to see each one (and fix a rejected one). */
function DocumentsRow({ driver }: { driver: Driver }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const { config } = useAppConfig();
  const [open, setOpen] = useState(false);
  const items = documentChecklist(driver, config);
  const approved = items.filter((item) => item.state === 'approved').length;
  const rejected = items.filter((item) => item.state === 'rejected').length;
  const missing = items.filter((item) => item.state === 'missing' || item.state === 'partial').length;
  const tone = rejected ? 'danger' : missing ? 'warning' : 'primary';
  const label = rejected
    ? t('profile.driver.docs.rejected', { count: rejected })
    : missing
      ? t('profile.driver.docs.missing', { count: missing })
      : approved === items.length
        ? t('profile.driver.docs.allApproved')
        : t('profile.driver.docs.inReview', { count: items.length - approved });

  return (
    <Card style={{ gap: space.sm }}>
      <Pressable
        accessibilityRole="button"
        accessibilityState={{ expanded: open }}
        accessibilityLabel={`${t('profile.driver.docs.title')}: ${label}`}
        onPress={() => setOpen((value) => !value)}
        style={({ pressed }) => ({ gap: space.sm, opacity: pressed ? 0.7 : 1 })}>
        <View style={styles.row}>
          <IconTile icon={FileText} tone={tone === 'primary' ? 'success' : tone} />
          <View style={{ flex: 1, gap: 2 }}>
            <Txt variant="bodyStrong">{t('profile.driver.docs.title')}</Txt>
            <Txt variant="caption" color={tone === 'primary' ? 'muted' : tone}>
              {label}
            </Txt>
          </View>
          <Txt variant="label" color="muted" tabular>
            {approved}/{items.length}
          </Txt>
          <ChevronDown
            size={20}
            color={theme.muted}
            strokeWidth={2.2}
            style={{ transform: [{ rotate: open ? '180deg' : '0deg' }] }}
          />
        </View>
        <Meter value={approved} total={items.length} tone={tone} />
      </Pressable>
      {open ? (
        <View style={{ marginTop: space.xs }}>
          {items.map((item, index) => (
            <View
              key={item.kind}
              style={[styles.docRow, index < items.length - 1 && { borderBottomWidth: 1, borderBottomColor: theme.divider }]}>
              <View style={{ flex: 1 }}>
                <Txt numberOfLines={1}>{t(`driver.doc.${item.kind}.title`)}</Txt>
                {item.rejectionReason ? (
                  <Txt variant="caption" color="danger">
                    {item.rejectionReason}
                  </Txt>
                ) : null}
              </View>
              <StatusPill label={t(`driver.docState.${item.state}`)} tone={DOC_TONE[item.state]} dot />
            </View>
          ))}
          {rejected ? (
            <Button
              title={t('profile.driver.docs.help')}
              size="sm"
              variant="secondary"
              onPress={() => router.push('/reports')}
              style={{ marginTop: space.sm }}
            />
          ) : null}
        </View>
      ) : null}
    </Card>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: space.md },
  docRow: { flexDirection: 'row', alignItems: 'center', gap: space.sm, minHeight: 44, paddingVertical: space.xs },
  vehicle: { flexDirection: 'row', alignItems: 'center', gap: space.md },
  balance: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.xs,
    borderRadius: radius.tile,
    paddingHorizontal: space.md,
    paddingVertical: space.sm,
  },
});
