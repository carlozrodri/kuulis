import { router } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { RefreshControl, StyleSheet, View } from 'react-native';

import {
  ChevronLeft,
  CircleCheck,
  CirclePause,
  CircleX,
  Gauge,
  type Icon,
  Percent,
  ShieldAlert,
  ShieldCheck,
  Star,
  ThumbsUp,
  Timer,
  TriangleAlert,
} from '@/components/icons';
import {
  Button,
  Card,
  EmptyState,
  IconButton,
  IconTile,
  Row,
  Screen,
  Skeleton,
  StatusPill,
  type Tone,
  toneColors,
  Txt,
} from '@/components/ui';
import { PausePanel } from '@/features/quality/PausePanel';
import { useDriverQuality, useQualityPause } from '@/hooks/useQuality';
import { apiErrorMessage } from '@/i18n';
import { cancelRateTone, formatPercent, LEVEL_TONE, meterPosition, pauseRules } from '@/lib/quality';
import { formatRating } from '@/lib/ride';
import type { DriverQuality, QualityLevel, QualityThresholds } from '@/lib/types';
import { elevation, radius, space, useTheme } from '@/theme';

const back = () => (router.canGoBack() ? router.back() : router.replace('/profile'));

const LEVEL_ICON: Record<QualityLevel, Icon> = {
  ok: CircleCheck,
  warn: TriangleAlert,
  low_priority: Gauge,
  review: ShieldAlert,
};

/**
 * "Mi calidad" (doc 15): the driver's acceptance and cancellation rates and rating over the last days, the
 * level they lead to (normal, warned, fewer rides, under review) and the rules behind it in plain words.
 */
export function QualityScreen() {
  const { t } = useTranslation();
  const quality = useDriverQuality();
  const pause = useQualityPause('driver');
  const data = quality.data;

  return (
    <Screen
      header={
        <Row style={{ paddingTop: space.xs, paddingBottom: space.md }}>
          <IconButton icon={ChevronLeft} label={t('common.back')} onPress={back} />
        </Row>
      }
      refreshControl={<RefreshControl refreshing={quality.isRefetching} onRefresh={() => void quality.refetch()} />}>
      <View style={{ alignItems: 'flex-start', gap: space.sm, marginBottom: space.lg }}>
        <IconTile icon={Gauge} tone="accent" size={56} />
        <Txt variant="title" accessibilityRole="header">
          {t('quality.title')}
        </Txt>
        <Txt color="muted">
          {data ? t('quality.subtitle', { days: data.thresholds.window_days }) : t('quality.subtitleLoading')}
        </Txt>
      </View>

      {quality.isPending ? (
        <View style={{ gap: space.sm }}>
          <Skeleton height={132} radius={radius.card} />
          <Row>
            <Skeleton height={112} radius={radius.card} style={{ flex: 1 }} />
            <Skeleton height={112} radius={radius.card} style={{ flex: 1 }} />
          </Row>
          <Row>
            <Skeleton height={112} radius={radius.card} style={{ flex: 1 }} />
            <Skeleton height={112} radius={radius.card} style={{ flex: 1 }} />
          </Row>
        </View>
      ) : !data ? (
        <>
          <EmptyState icon={CircleX} title={t('common.error')} body={apiErrorMessage(quality.error)} />
          <Button title={t('common.retry')} variant="secondary" onPress={() => void quality.refetch()} />
        </>
      ) : (
        <View style={{ gap: space.lg, paddingBottom: space.xl }}>
          {pause ? <PausePanel pause={pause} variant="driver" showQualityLink={false} /> : null}
          <LevelCard quality={data} />
          <Metrics quality={data} />
          <CancelMeter quality={data} />
          <Rules thresholds={data.thresholds} />
        </View>
      )}
    </Screen>
  );
}

/** Where the driver stands, in one sentence, with what pulls them down. */
function LevelCard({ quality }: { quality: DriverQuality }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const tone = LEVEL_TONE[quality.level];
  const colors = toneColors(theme, tone);
  const LevelIcon = LEVEL_ICON[quality.level];
  const values = {
    warn: formatPercent(quality.thresholds.cancel_warn),
    low: formatPercent(quality.thresholds.cancel_low_priority),
  };
  return (
    <Card elevated style={{ gap: space.md }}>
      <Row gap={space.md}>
        <View style={[styles.levelRing, { backgroundColor: colors.bg }]}>
          <View style={[styles.levelIcon, { backgroundColor: theme.surface }, elevation(theme)]}>
            <LevelIcon size={26} color={colors.fg} strokeWidth={2.2} />
          </View>
        </View>
        <View style={{ flex: 1, gap: 4 }}>
          <StatusPill label={t(`quality.level.${quality.level}.pill`)} tone={tone} dot />
          <Txt variant="subtitle" accessibilityRole="header">
            {t(`quality.level.${quality.level}.title`)}
          </Txt>
        </View>
      </Row>
      <Txt color="muted">{t(`quality.level.${quality.level}.body`, values)}</Txt>
      {quality.reasons.length ? (
        <View style={styles.reasons}>
          <Txt variant="label" color="muted">
            {t('quality.reasonsLabel')}
          </Txt>
          {quality.reasons.map((reason) => (
            <StatusPill key={reason} label={t(`quality.reason.${reason}`, { defaultValue: reason })} tone={tone} />
          ))}
        </View>
      ) : null}
    </Card>
  );
}

function Metrics({ quality }: { quality: DriverQuality }) {
  const { t } = useTranslation();
  const rating = formatRating(quality.rating_avg);
  const cancelTone = cancelRateTone(quality, quality.thresholds);
  return (
    <View style={{ gap: space.sm }}>
      <Row style={{ alignItems: 'stretch' }}>
        <MetricTile
          icon={ThumbsUp}
          label={t('quality.metric.acceptance')}
          value={formatPercent(quality.acceptance_rate)}
          detail={t('quality.metric.acceptanceDetail', { accepted: quality.accepted, count: quality.offers })}
        />
        <MetricTile
          icon={Percent}
          tone={cancelTone}
          label={t('quality.metric.cancellation')}
          value={formatPercent(quality.cancel_rate)}
          detail={t('quality.metric.cancellationDetail', { cancels: quality.cancels, count: quality.accepted })}
        />
      </Row>
      <Row style={{ alignItems: 'stretch' }}>
        <MetricTile
          icon={Star}
          label={t('quality.metric.rating')}
          value={rating ? `★ ${rating}` : '—'}
          detail={quality.rating_count ? t('quality.metric.ratingDetail', { count: quality.rating_count }) : t('quality.metric.noRatings')}
        />
        <MetricTile
          icon={CircleCheck}
          label={t('quality.metric.rides')}
          value={String(quality.rides)}
          detail={t('quality.metric.ridesDetail', { count: quality.completed })}
        />
      </Row>
    </View>
  );
}

function MetricTile({
  icon,
  label,
  value,
  detail,
  tone = 'neutral',
}: {
  icon: Icon;
  label: string;
  value: string;
  detail: string;
  tone?: 'success' | 'warning' | 'danger' | 'neutral';
}) {
  const theme = useTheme();
  const valueColor = tone === 'neutral' || tone === 'success' ? theme.text : toneColors(theme, tone).fg;
  return (
    <Card style={styles.tile} accessibilityLabel={`${label}: ${value}. ${detail}`}>
      <Row gap={space.xs}>
        <IconTile icon={icon} tone={tone === 'neutral' ? 'primary' : (tone as Tone)} size={32} />
        <Txt variant="label" color="muted" style={{ flex: 1 }} numberOfLines={2}>
          {label}
        </Txt>
      </Row>
      <Txt variant="heading" tabular style={{ color: valueColor }}>
        {value}
      </Txt>
      <Txt variant="caption" color="muted">
        {detail}
      </Txt>
    </Card>
  );
}

/** The cancellation rate on a bar split at the warning, fewer-rides and review thresholds. */
function CancelMeter({ quality }: { quality: DriverQuality }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const { thresholds } = quality;
  const measured = quality.cancel_rate != null && quality.accepted >= thresholds.min_rides;
  const at = (rate: number) => meterPosition(rate, thresholds);
  const marks = [thresholds.cancel_warn, thresholds.cancel_low_priority, thresholds.cancel_review];
  const segments = [
    { from: 0, to: at(thresholds.cancel_warn), color: theme.success },
    { from: at(thresholds.cancel_warn), to: at(thresholds.cancel_low_priority), color: theme.warning },
    { from: at(thresholds.cancel_low_priority), to: 1, color: theme.danger },
  ];
  const tone = cancelRateTone(quality, thresholds);
  const markerColor = tone === 'neutral' ? theme.muted : toneColors(theme, tone).fg;

  return (
    <Card style={{ gap: space.sm }}>
      <Row style={{ justifyContent: 'space-between' }}>
        <Txt variant="bodyStrong" style={{ flex: 1 }}>
          {t('quality.meter.title')}
        </Txt>
        <Txt variant="subtitle" tabular style={{ color: markerColor }}>
          {formatPercent(quality.cancel_rate)}
        </Txt>
      </Row>
      <View
        accessible
        accessibilityRole="progressbar"
        accessibilityLabel={t('quality.meter.a11y', {
          rate: formatPercent(quality.cancel_rate),
          warn: formatPercent(thresholds.cancel_warn),
          low: formatPercent(thresholds.cancel_low_priority),
        })}
        style={styles.meter}>
        <View style={styles.track}>
          {segments.map((segment, index) => (
            <View
              key={index}
              style={{ flex: Math.max(segment.to - segment.from, 0.001), backgroundColor: segment.color, opacity: 0.28 }}
            />
          ))}
        </View>
        {measured ? (
          <View
            style={[
              styles.marker,
              { left: `${at(quality.cancel_rate ?? 0) * 100}%`, backgroundColor: markerColor, borderColor: theme.surface },
            ]}
          />
        ) : null}
      </View>
      <View style={styles.marks}>
        {marks.map((rate) => (
          <Txt key={rate} variant="micro" color="muted" style={[styles.mark, { left: `${at(rate) * 100}%` }]} tabular>
            {formatPercent(rate)}
          </Txt>
        ))}
      </View>
      <Txt variant="caption" color="muted">
        {measured
          ? t('quality.meter.legend', {
              warn: formatPercent(thresholds.cancel_warn),
              low: formatPercent(thresholds.cancel_low_priority),
            })
          : t('quality.meter.notYet', { min: thresholds.min_rides, count: quality.accepted })}
      </Txt>
    </Card>
  );
}

/** The thresholds explained in plain words. */
function Rules({ thresholds }: { thresholds: QualityThresholds }) {
  const { t } = useTranslation();
  const pauses = pauseRules(thresholds);
  return (
    <View style={{ gap: space.xs }}>
      <Txt variant="overline" color="muted" accessibilityRole="header">
        {t('quality.rules.title')}
      </Txt>
      <Card style={{ paddingVertical: space.xs, paddingHorizontal: space.md }}>
        <RuleRow
          icon={Percent}
          title={t('quality.rules.cancelTitle')}
          body={t('quality.rules.cancelBody', {
            warn: formatPercent(thresholds.cancel_warn),
            low: formatPercent(thresholds.cancel_low_priority),
            review: formatPercent(thresholds.cancel_review),
            days: thresholds.window_days,
            min: thresholds.min_rides,
          })}
          divider
        />
        <RuleRow
          icon={CirclePause}
          title={t('quality.rules.pauseTitle')}
          body={t(`quality.rules.pause.${pauses.key}`, {
            declines: pauses.declines,
            cancels: pauses.cancels,
            minutes: thresholds.pause_minutes,
          })}
          divider
        />
        <RuleRow
          icon={Timer}
          title={t('quality.rules.waitTitle')}
          body={t('quality.rules.waitBody', { minutes: thresholds.pickup_wait_minutes })}
          divider
        />
        <RuleRow
          icon={Star}
          title={t('quality.rules.ratingTitle')}
          body={t('quality.rules.ratingBody', { min: thresholds.rating_review_below.toFixed(1), count: thresholds.rating_min_count })}
          divider
        />
        <RuleRow icon={ShieldCheck} title={t('quality.rules.safetyTitle')} body={t('quality.rules.safetyBody')} />
      </Card>
    </View>
  );
}

function RuleRow({ icon, title, body, divider }: { icon: Icon; title: string; body: string; divider?: boolean }) {
  const theme = useTheme();
  return (
    <View accessible style={[styles.rule, divider && { borderBottomWidth: 1, borderBottomColor: theme.divider }]}>
      <IconTile icon={icon} tone="primary" size={36} />
      <View style={{ flex: 1, gap: 2 }}>
        <Txt variant="bodyStrong">{title}</Txt>
        <Txt variant="caption" color="muted" style={{ fontSize: 14, lineHeight: 20 }}>
          {body}
        </Txt>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  levelRing: { width: 64, height: 64, borderRadius: 32, alignItems: 'center', justifyContent: 'center' },
  levelIcon: { width: 46, height: 46, borderRadius: 23, alignItems: 'center', justifyContent: 'center' },
  reasons: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: space.xs },
  tile: { flex: 1, gap: space.xs, padding: space.md },
  meter: { height: 22, justifyContent: 'center' },
  track: { flexDirection: 'row', height: 10, borderRadius: 5, overflow: 'hidden' },
  marker: { position: 'absolute', width: 22, height: 22, borderRadius: 11, borderWidth: 4, marginLeft: -11 },
  marks: { height: 16 },
  mark: { position: 'absolute', width: 40, marginLeft: -20, textAlign: 'center' },
  rule: { flexDirection: 'row', alignItems: 'flex-start', gap: space.sm, paddingVertical: space.sm },
});
