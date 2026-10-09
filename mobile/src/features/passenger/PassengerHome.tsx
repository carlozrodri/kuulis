import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { StyleSheet, View } from 'react-native';

import { Bike, Mail, Search, ShieldCheck, Wallet } from '@/components/icons';
import { MapSheetLayout } from '@/components/MapSheetLayout';
import { Button, Card, ListRow, Notice, StatusPill, Txt, Wordmark } from '@/components/ui';
import { api } from '@/lib/api';
import { useAuth } from '@/providers/AuthProvider';
import { elevation, radius, space, useTheme } from '@/theme';

export function greetingKey(date = new Date()) {
  const hour = date.getHours();
  if (hour < 12) return 'home.goodMorning';
  if (hour < 19) return 'home.goodAfternoon';
  return 'home.goodEvening';
}

export function firstName(fullName: string | null | undefined) {
  return fullName?.trim().split(/\s+/)[0] ?? '';
}

/** Passenger home. Requesting a ride (map, search, price) arrives in a later phase. */
export function PassengerHome() {
  const { t } = useTranslation();
  const theme = useTheme();
  const { user } = useAuth();
  const [sent, setSent] = useState(false);
  const name = firstName(user?.full_name);

  return (
    <MapSheetLayout
      variant="passenger"
      topBar={
        <View style={[styles.brand, { backgroundColor: theme.surface }, elevation(theme)]}>
          <Wordmark size={22} />
        </View>
      }>
      <Txt variant="title" accessibilityRole="header">
        {name ? t('home.greetingName', { greeting: t(greetingKey()), name }) : t(greetingKey())}
      </Txt>

      <View
        accessible
        accessibilityRole="search"
        accessibilityLabel={`${t('home.whereTo')}. ${t('common.comingSoon')}`}
        accessibilityState={{ disabled: true }}
        style={[styles.search, { backgroundColor: theme.background }]}>
        <Search size={22} color={theme.primary} strokeWidth={2.2} />
        <Txt variant="bodyStrong" color="muted" style={{ flex: 1, fontSize: 16 }}>
          {t('home.whereTo')}
        </Txt>
        <StatusPill label={t('common.comingSoon')} tone="accent" />
      </View>

      {!user?.is_verified ? (
        <Notice tone="warning" icon={Mail} title={t('home.verifyTitle')}>
          <Txt variant="caption" style={{ fontSize: 14, lineHeight: 20 }}>
            {sent ? t('home.verifySent') : t('home.verifyEmail')}
          </Txt>
          {!sent ? (
            <Button
              title={t('home.resend')}
              variant="secondary"
              size="sm"
              style={{ alignSelf: 'flex-start' }}
              onPress={() =>
                api('/auth/verify-email/resend', { method: 'POST' })
                  .then(() => setSent(true))
                  .catch(() => setSent(true))
              }
            />
          ) : null}
        </Notice>
      ) : null}

      <Card tone="tint" style={{ paddingVertical: space.xs }}>
        <Txt variant="overline" color="muted" style={{ marginTop: space.sm }}>
          {t('home.howItWorks')}
        </Txt>
        <ListRow icon={Wallet} title={t('home.how.price.title')} subtitle={t('home.how.price.body')} divider />
        <ListRow icon={Bike} title={t('home.how.pay.title')} subtitle={t('home.how.pay.body')} divider />
        <ListRow icon={ShieldCheck} title={t('home.how.safe.title')} subtitle={t('home.how.safe.body')} />
      </Card>
    </MapSheetLayout>
  );
}

const styles = StyleSheet.create({
  brand: { alignSelf: 'flex-start', borderRadius: radius.pill, paddingHorizontal: space.md, paddingVertical: space.xs },
  search: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.sm,
    height: 60,
    borderRadius: 18,
    paddingHorizontal: space.md,
    opacity: 0.9,
  },
});
