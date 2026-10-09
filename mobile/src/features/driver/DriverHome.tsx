import { router } from 'expo-router';
import type { ReactElement } from 'react';
import { useTranslation } from 'react-i18next';
import { RefreshControl, type RefreshControlProps, StyleSheet, View } from 'react-native';

import {
  Bike,
  Calendar,
  CircleCheck,
  CircleX,
  Gift,
  Hourglass,
  type Icon,
  Power,
  ShieldAlert,
  Sparkles,
} from '@/components/icons';
import { MapSheetLayout } from '@/components/MapSheetLayout';
import {
  Button,
  Card,
  EmptyState,
  ListRow,
  Notice,
  ProgressSteps,
  Screen,
  Skeleton,
  StatusPill,
  type Tone,
  toneColors,
  Txt,
} from '@/components/ui';
import { useAppConfig, useDriverProfile } from '@/hooks/useDriver';
import { apiErrorMessage } from '@/i18n';
import { documentChecklist, nextDriverStep, requirementChecklist } from '@/lib/driver';
import type { DriverProfile } from '@/lib/types';
import { elevation, radius, space, useTheme } from '@/theme';

import { DOCUMENT_ICONS, DOCUMENT_STATE_TONE, STEP_HREF } from './meta';

type RefreshEl = ReactElement<RefreshControlProps>;

/** Driver mode home: onboarding until approved, then the (placeholder) online/offline home. */
export function DriverHome() {
  const { t } = useTranslation();
  const profile = useDriverProfile();
  const { config } = useAppConfig();
  const refresh = <RefreshControl refreshing={profile.isRefetching} onRefresh={() => void profile.refetch()} />;

  if (profile.isPending) {
    return (
      <Screen tabBar>
        <View style={{ gap: space.md, paddingTop: space.xl }}>
          <Skeleton height={34} width="70%" />
          <Skeleton height={18} width="90%" />
          <Skeleton height={160} radius={radius.card} />
          <Skeleton height={220} radius={radius.card} />
        </View>
      </Screen>
    );
  }

  if (profile.isError) {
    return (
      <Screen tabBar refreshControl={refresh}>
        <EmptyState icon={CircleX} title={t('common.error')} body={apiErrorMessage(profile.error)} />
        <Button title={t('common.retry')} variant="secondary" onPress={() => void profile.refetch()} />
      </Screen>
    );
  }

  const data = profile.data;
  if (!data || data.status === 'draft') return <DriverIntro profile={data} refresh={refresh} />;
  if (data.status === 'approved') return <DriverOffline refresh={refresh} />;
  return <DriverStatus profile={data} refresh={refresh} config={config} />;
}

function DriverIntro({ profile, refresh }: { profile: DriverProfile | null; refresh: RefreshEl }) {
  const { t } = useTranslation();
  const { config } = useAppConfig();
  const checklist = requirementChecklist(profile, config);
  const step = nextDriverStep(profile, config);
  const started = !!profile;
  const minYear = config.vehicle_min_year[config.enabled_vehicle_types[0] ?? 'moto'];

  return (
    <Screen tabBar refreshControl={refresh}>
      <View style={{ paddingTop: space.lg, gap: space.xs }}>
        <StatusPill label={t('driver.intro.badge')} tone="accent" />
        <Txt variant="display" accessibilityRole="header" style={{ marginTop: space.xs }}>
          {started ? t('driver.intro.continueTitle') : t('driver.intro.title')}
        </Txt>
        <Txt color="muted">{t('driver.intro.subtitle')}</Txt>
      </View>

      {started ? (
        <Card elevated style={{ marginTop: space.lg, gap: space.sm }}>
          <ProgressSteps
            total={checklist.total}
            current={checklist.done}
            label={t('driver.intro.progress', { done: checklist.done, total: checklist.total })}
          />
          {checklist.items.map((item) => (
            <ListRow
              key={item.key}
              title={t(`driver.requirement.${item.key}`, { age: config.driver_min_age, year: minYear })}
              icon={item.done ? CircleCheck : Hourglass}
              iconTone={item.done ? 'success' : 'neutral'}
              chevron={false}
            />
          ))}
        </Card>
      ) : (
        <Notice tone="accent" icon={Gift} style={{ marginTop: space.lg }}>
          {t('mode.driverPromo')}
        </Notice>
      )}

      <Txt variant="overline" color="muted" style={{ marginTop: space.xl, marginBottom: space.xs }}>
        {t('driver.intro.requirements')}
      </Txt>
      <Card style={{ paddingVertical: space.xs }}>
        <ListRow icon={Calendar} title={t('driver.intro.age', { age: config.driver_min_age })} divider />
        <ListRow icon={Bike} title={t('driver.intro.vehicleYear', { year: minYear })} subtitle={t('driver.intro.vehicleOnlyMoto')} />
      </Card>

      <Txt variant="overline" color="muted" style={{ marginTop: space.xl, marginBottom: space.xs }}>
        {t('driver.intro.documents')}
      </Txt>
      <Card style={{ paddingVertical: space.xs }}>
        {config.driver_required_documents.map((kind, index) => (
          <ListRow
            key={kind}
            icon={DOCUMENT_ICONS[kind]}
            title={t(`driver.doc.${kind}.title`)}
            subtitle={
              kind === 'vehicle_photo'
                ? t('driver.doc.vehicle_photo.hintCount', { count: config.vehicle_photo_min_count })
                : t(`driver.doc.${kind}.hint`)
            }
            divider={index < config.driver_required_documents.length - 1}
          />
        ))}
      </Card>

      <Notice tone="info" style={{ marginTop: space.lg }}>
        {t('driver.intro.review')}
      </Notice>

      <Button
        title={started ? t('driver.intro.continue') : t('driver.intro.start')}
        style={{ marginTop: space.xl }}
        onPress={() => router.push(STEP_HREF[step])}
      />
    </Screen>
  );
}

function StatusHero({ icon: HeroIcon, tone, title, body }: { icon: Icon; tone: Tone; title: string; body: string }) {
  const theme = useTheme();
  const colors = toneColors(theme, tone);
  return (
    <View style={styles.statusHero}>
      <View style={[styles.statusRing, { backgroundColor: colors.bg }]}>
        <View style={[styles.statusIcon, { backgroundColor: theme.surface }, elevation(theme)]}>
          <HeroIcon size={40} color={colors.fg} strokeWidth={2} />
        </View>
      </View>
      <Txt variant="title" align="center" accessibilityRole="header">
        {title}
      </Txt>
      <Txt color="muted" align="center">
        {body}
      </Txt>
    </View>
  );
}

function DriverStatus({
  profile,
  refresh,
  config,
}: {
  profile: DriverProfile;
  refresh: RefreshEl;
  config: ReturnType<typeof useAppConfig>['config'];
}) {
  const { t, i18n } = useTranslation();
  const documents = documentChecklist(profile, config);
  const date = (iso: string | null | undefined) =>
    iso ? new Date(iso).toLocaleDateString(i18n.language, { day: 'numeric', month: 'long', year: 'numeric' }) : '';

  if (profile.status === 'suspended') {
    return (
      <Screen tabBar refreshControl={refresh}>
        <StatusHero icon={ShieldAlert} tone="danger" title={t('driver.status.suspended.title')} body={t('driver.status.suspended.body')} />
        {profile.suspension_reason || profile.rejection_reason ? (
          <Notice tone="danger" title={t('driver.status.reason')}>
            {profile.suspension_reason || profile.rejection_reason || ''}
          </Notice>
        ) : null}
      </Screen>
    );
  }

  const rejected = profile.status === 'rejected';
  return (
    <Screen tabBar refreshControl={refresh}>
      {rejected ? (
        <StatusHero icon={CircleX} tone="danger" title={t('driver.status.rejected.title')} body={t('driver.status.rejected.body')} />
      ) : (
        <StatusHero
          icon={Hourglass}
          tone="warning"
          title={t('driver.status.pending.title')}
          body={t('driver.status.pending.body')}
        />
      )}

      {rejected && profile.rejection_reason ? (
        <Notice tone="danger" title={t('driver.status.reason')}>
          {profile.rejection_reason}
        </Notice>
      ) : null}
      {!rejected && profile.submitted_at ? (
        <View style={{ alignItems: 'center' }}>
          <StatusPill label={t('driver.status.submittedAt', { date: date(profile.submitted_at) })} tone="warning" dot />
        </View>
      ) : null}

      <Txt variant="overline" color="muted" style={{ marginTop: space.xl, marginBottom: space.xs }}>
        {t('driver.intro.documents')}
      </Txt>
      <Card style={{ paddingVertical: space.xs }}>
        {documents.map((item, index) => (
          <ListRow
            key={item.kind}
            icon={DOCUMENT_ICONS[item.kind]}
            iconTone={item.state === 'rejected' ? 'danger' : 'primary'}
            title={t(`driver.doc.${item.kind}.title`)}
            subtitle={item.state === 'rejected' ? item.rejectionReason ?? t('driver.docState.rejected') : null}
            right={<StatusPill label={t(`driver.docState.${item.state}`)} tone={DOCUMENT_STATE_TONE[item.state]} />}
            divider={index < documents.length - 1}
          />
        ))}
      </Card>

      {rejected ? (
        <Button
          title={t('driver.status.rejected.cta')}
          style={{ marginTop: space.xl }}
          onPress={() => router.push(STEP_HREF[nextDriverStep(profile, config)])}
        />
      ) : (
        <Notice tone="info" style={{ marginTop: space.lg }}>
          {t('driver.status.pending.notify')}
        </Notice>
      )}
    </Screen>
  );
}

function DriverOffline({ refresh }: { refresh: RefreshEl }) {
  const { t } = useTranslation();
  const theme = useTheme();
  return (
    <MapSheetLayout
      variant="driver"
      refreshControl={refresh}
      topBar={
        <Card elevated style={{ gap: space.xs }}>
          <StatusPill label={t('driver.home.approved')} tone="success" dot />
          <Txt variant="subtitle">{t('driver.home.welcome')}</Txt>
          <Txt variant="caption" color="muted">
            {t('driver.home.freeMonths')}
          </Txt>
        </Card>
      }>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.sm }}>
        <View style={[styles.offlineDot, { backgroundColor: theme.muted, shadowColor: theme.muted }]} />
        <Txt variant="heading" accessibilityRole="header">
          {t('driver.home.offline')}
        </Txt>
      </View>
      <Txt color="muted">{t('driver.home.offlineBody')}</Txt>
      <Button
        title={t('driver.home.connect')}
        size="lg"
        icon={Power}
        disabled
        accessibilityHint={t('common.comingSoon')}
      />
      <View style={{ alignItems: 'center' }}>
        <StatusPill label={t('common.comingSoon')} tone="accent" />
      </View>
      <Notice tone="info" icon={Sparkles}>
        {t('driver.home.nextUp')}
      </Notice>
    </MapSheetLayout>
  );
}

const styles = StyleSheet.create({
  statusHero: { alignItems: 'center', gap: space.sm, paddingTop: space.xxl, paddingBottom: space.lg },
  statusRing: { width: 128, height: 128, borderRadius: 64, alignItems: 'center', justifyContent: 'center', marginBottom: space.sm },
  statusIcon: { width: 84, height: 84, borderRadius: 42, alignItems: 'center', justifyContent: 'center' },
  offlineDot: { width: 12, height: 12, borderRadius: 6 },
});
