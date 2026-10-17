import { router } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { StyleSheet, View } from 'react-native';

import {
  ArrowLeftRight,
  Award,
  Bike,
  ChevronRight,
  FileText,
  Gauge,
  Gift,
  Hourglass,
  LockKeyhole,
  Receipt,
  TrendingUp,
  Wallet,
} from '@/components/icons';
import { Button, Card, IconTile, ListRow, Skeleton, StatusPill, type Tone, Txt } from '@/components/ui';
import { PlateBadge } from '@/features/ride/components';
import { useWalletFormat } from '@/features/wallet/format';
import { useAppConfig } from '@/hooks/useDriver';
import { useDriverQuality, useQualityPause } from '@/hooks/useQuality';
import { useSubscription, useWallet } from '@/hooks/useWallet';
import { formatPercent, LEVEL_TONE } from '@/lib/quality';
import { formatFare } from '@/lib/ride';
import type { DriverProfile as Driver, DriverStats } from '@/lib/types';
import { documentBadge, myDocuments, needsAttention } from '@/lib/verification';
import { pendingTotal, subscriptionState } from '@/lib/wallet';
import { radius, space, useTheme } from '@/theme';

import { Section } from './components';
import { RedeemSection } from './ReferralCard';

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
  if (!isActiveDriver(driver)) {
    return (
      <>
        <ApplicationCard driver={driver ?? null} />
        {driver ? <RedeemSection /> : null}
      </>
    );
  }

  return (
    <>
      {driver?.vehicle ? (
        <Section title={t('profile.driver.vehicle')}>
          <Card style={{ gap: space.md }}>
            <View style={styles.vehicle}>
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
            </View>
            {driver.pending_vehicle ? (
              <ListRow
                icon={Hourglass}
                iconTone="info"
                title={t('verification.vehicle.pendingRow', {
                  moto: `${driver.pending_vehicle.brand} ${driver.pending_vehicle.model}`,
                })}
                subtitle={t('verification.vehicle.pendingRowHint')}
                right={<StatusPill label={t('verification.badge.in_review')} tone="info" />}
                onPress={() => router.push('/driver/vehicle-change')}
              />
            ) : driver.status === 'approved' ? (
              <Button
                title={t('verification.vehicle.title')}
                size="sm"
                variant="secondary"
                icon={ArrowLeftRight}
                style={{ marginTop: 0 }}
                onPress={() => router.push('/driver/vehicle-change')}
              />
            ) : null}
          </Card>
        </Section>
      ) : null}

      {stats?.compliments?.length ? <ComplimentsSection compliments={stats.compliments} /> : null}

      <Section title={t('profile.driver.account')}>
        <SubscriptionRow />
        <Card style={{ paddingVertical: space.xxs }}>
          <DocumentsRow driver={driver!} />
          <ListRow
            icon={TrendingUp}
            title={t('profile.driver.earnings')}
            subtitle={
              stats
                ? t('profile.driver.earningsHint', { amount: formatFare(stats.month.earnings), rides: t('stats.rides', { count: stats.month.rides }) })
                : null
            }
            divider
            onPress={() => router.push('/rides')}
          />
          <QualityRow />
          <ListRow
            icon={Gift}
            iconTone="accent"
            title={t('profile.invite.section')}
            subtitle={t('profile.menu.inviteHint')}
            onPress={() => router.push('/profile/invite')}
          />
        </Card>
      </Section>
    </>
  );
}

/** Doc 23: compliments passengers gave ("Amable", "Casco limpio"), as badges with how many times. */
function ComplimentsSection({ compliments }: { compliments: NonNullable<DriverStats['compliments']> }) {
  const { t } = useTranslation();
  const theme = useTheme();
  return (
    <Section title={t('profile.driver.compliments')}>
      <Card style={{ gap: space.sm }}>
        <View style={styles.badges}>
          {compliments.map(({ tag, count }) => (
            <View
              key={tag}
              style={[styles.badge, { backgroundColor: theme.accentSoft }]}
              accessibilityLabel={t('profile.driver.complimentA11y', { name: t(`rating.tag.${tag}`, { defaultValue: tag }), count })}>
              <Award size={16} color={theme.onAccentSoft} strokeWidth={2.4} />
              <Txt variant="label" style={{ color: theme.onAccentSoft }}>
                {t(`rating.tag.${tag}`, { defaultValue: tag })}
              </Txt>
              <Txt variant="label" tabular style={{ color: theme.text }}>
                {count}
              </Txt>
            </View>
          ))}
        </View>
        <Txt variant="caption" color="muted">
          {t('profile.driver.complimentsHint')}
        </Txt>
      </Card>
    </Section>
  );
}

/** Doc 15: "Mi calidad", with the acceptance and cancellation rates at a glance. */
function QualityRow() {
  const { t } = useTranslation();
  const quality = useDriverQuality().data;
  const pause = useQualityPause('driver');
  const tone: Tone = pause ? 'warning' : quality ? LEVEL_TONE[quality.level] : 'primary';
  const subtitle = pause
    ? t('quality.profile.paused')
    : quality
      ? t('quality.profile.hint', { acceptance: formatPercent(quality.acceptance_rate), cancellation: formatPercent(quality.cancel_rate) })
      : t('quality.profile.hintLoading');
  return (
    <ListRow
      icon={Gauge}
      iconTone={tone}
      title={t('quality.title')}
      subtitle={subtitle}
      right={quality && quality.level !== 'ok' ? <StatusPill label={t(`quality.level.${quality.level}.pill`)} tone={tone} /> : undefined}
      divider
      onPress={() => router.push('/driver/quality')}
    />
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

/** Doc 12: "Mis documentos" with what needs attention (expired, expiring, missing date, rejected renewal). */
function DocumentsRow({ driver }: { driver: Driver }) {
  const { t } = useTranslation();
  const { config } = useAppConfig();
  const items = myDocuments(driver, config);
  const attention = needsAttention(items);
  const urgent = items[0];
  const badge = urgent ? documentBadge(urgent) : null;
  const tone: Tone = !attention || !badge ? 'success' : badge.tone === 'danger' ? 'danger' : 'warning';
  const label =
    !attention || !urgent || !badge
      ? t('verification.profile.allGood')
      : attention === 1
        ? `${t(`driver.doc.${urgent.kind}.title`)}: ${t(badge.key, { count: badge.count }).toLocaleLowerCase()}`
        : t('verification.profile.attention', { count: attention });

  return (
    <ListRow
      icon={FileText}
      iconTone={tone}
      title={t('verification.myDocs.title')}
      subtitle={label}
      right={attention ? <StatusPill label={String(attention)} tone={tone} /> : undefined}
      divider
      accessibilityLabel={`${t('verification.myDocs.title')}: ${label}`}
      onPress={() => router.push('/driver/my-documents')}
    />
  );
}

const styles = StyleSheet.create({
  badges: { flexDirection: 'row', flexWrap: 'wrap', gap: space.xs },
  badge: { flexDirection: 'row', alignItems: 'center', gap: 6, borderRadius: radius.pill, paddingHorizontal: 12, paddingVertical: 6 },
  row: { flexDirection: 'row', alignItems: 'center', gap: space.md },
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
