/**
 * Pages behind the profile, so the profile itself stays short: settings, legal, preferred payment, frequent
 * places and invites.
 */
import * as Application from 'expo-application';
import * as Haptics from 'expo-haptics';
import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Switch, View } from 'react-native';

import {
  Bell,
  ChartNoAxesColumn,
  Download,
  Gift,
  HeartHandshake,
  Info,
  LifeBuoy,
  LockKeyhole,
  LogOut,
  MapPinned,
  Moon,
  MonitorSmartphone,
  Pencil,
  ScrollText,
  Settings,
  Smartphone,
  Sun,
  UserX,
  Wallet,
} from '@/components/icons';
import { showToast } from '@/components/Toast';
import { Card, ListRow, Sheet, Skeleton, Txt } from '@/components/ui';
import { PaymentChips } from '@/features/ride/components';
import { loadSavedPayment, rideDraft, setDraftPayment } from '@/features/ride/store';
import { useSavedPlaces } from '@/hooks/useAccount';
import { useAppConfig } from '@/hooks/useDriver';
import { usePassengerStats } from '@/hooks/useRides';
import { useTrustedContacts } from '@/hooks/useSafety';
import { apiErrorMessage, SUPPORTED_LOCALES, type Locale } from '@/i18n';
import { setAnalyticsEnabled } from '@/lib/analytics';
import { usageAllowed } from '@/lib/analyticsCore';
import { api } from '@/lib/api';
import { DRIVER_KINDS, type LegalKind } from '@/lib/legal';
import { DEFAULT_PAYMENT_METHODS, shortAddress } from '@/lib/ride';
import { useStore } from '@/lib/store';
import { useAuth } from '@/providers/AuthProvider';
import { useMode } from '@/providers/ModeProvider';
import { radius, setThemePreference, space, themePreference, useTheme, type ThemePreference } from '@/theme';

import { Section, Segmented } from './components';
import { InviteCard, InviteesSection, RedeemSection } from './ReferralCard';
import { rideTo } from './SavedPlaces';
import { SubScreen } from './SubScreen';

const LANGUAGE_LABELS: Record<Locale, string> = { es: 'Español', en: 'English' };

/**
 * "Compartir datos de uso anónimos" (doc 19): on by default; the answer is saved as the consent "usage_data" and
 * applies on this phone at once (the queued events are dropped when it is switched off).
 */
function useUsageData() {
  const { t } = useTranslation();
  const theme = useTheme();
  const { user, refreshUser } = useAuth();
  // The answer being saved, shown until the refreshed user carries it.
  const [saving, setSaving] = useState<boolean | null>(null);
  const value = saving ?? usageAllowed(user?.consents, !!user);
  const busy = saving !== null;

  async function toggle(next: boolean) {
    if (busy) return;
    void Haptics.selectionAsync().catch(() => undefined);
    setSaving(next);
    try {
      await api('/users/me/consents', { method: 'PUT', body: { kind: 'usage_data', granted: next } });
      await setAnalyticsEnabled(next);
      await refreshUser();
      showToast(next ? t('privacy.usage.on') : t('privacy.usage.off'), 'success');
    } catch (e) {
      showToast(apiErrorMessage(e), 'danger');
    } finally {
      setSaving(null);
    }
  }
  return { value, busy, toggle, theme };
}

/** Perfil → Ajustes: everything that is not about trips in one page (account, preferences, security, privacy, help and legal). */
export function SettingsScreen() {
  const { t, i18n } = useTranslation();
  const { user, signOut, refreshUser } = useAuth();
  const preference = useStore(themePreference);
  const contactCount = useTrustedContacts(!!user).data?.length ?? 0;
  const [confirm, setConfirm] = useState(false);
  const usage = useUsageData();

  async function changeLanguage(locale: Locale) {
    if (locale === i18n.language) return;
    await i18n.changeLanguage(locale);
    try {
      await api('/users/me', { method: 'PATCH', body: { locale } });
      await refreshUser();
    } catch (e) {
      showToast(apiErrorMessage(e), 'danger');
    }
  }

  async function logoutEverywhere() {
    try {
      await api('/auth/logout-all', { method: 'POST' });
    } catch (e) {
      showToast(apiErrorMessage(e), 'danger');
      return;
    }
    await signOut();
  }

  return (
    <SubScreen icon={Settings} tone="primary" title={t('profile.menu.settings')} subtitle={t('profile.menu.settingsHint')}>
      <Section title={t('profile.account')}>
        <Card style={{ paddingVertical: space.xxs }}>
          <ListRow icon={Pencil} title={t('profile.edit.title')} subtitle={t('profile.edit.hint')} divider onPress={() => router.push('/profile/edit')} />
          <ListRow icon={LockKeyhole} title={t('profile.password.title')} subtitle={t('profile.password.hint')} onPress={() => router.push('/profile/password')} />
        </Card>
      </Section>
      <Section title={t('profile.preferences')}>
        <Card style={{ gap: space.lg }}>
          <View style={{ gap: space.xs }}>
            <Txt variant="label" color="muted">
              {t('profile.language')}
            </Txt>
            <Segmented
              label={t('profile.language')}
              value={(SUPPORTED_LOCALES.includes(i18n.language as Locale) ? i18n.language : 'es') as Locale}
              onChange={(locale) => void changeLanguage(locale)}
              options={SUPPORTED_LOCALES.map((locale) => ({ value: locale, label: LANGUAGE_LABELS[locale] }))}
            />
          </View>
          <View style={{ gap: space.xs }}>
            <Txt variant="label" color="muted">
              {t('profile.appearance.title')}
            </Txt>
            <Segmented<ThemePreference>
              label={t('profile.appearance.title')}
              value={preference}
              onChange={(value) => {
                void Haptics.selectionAsync().catch(() => undefined);
                setThemePreference(value);
              }}
              options={[
                { value: 'system', label: t('profile.appearance.system') },
                { value: 'light', label: t('profile.appearance.light'), icon: Sun },
                { value: 'dark', label: t('profile.appearance.dark'), icon: Moon },
              ]}
            />
          </View>
        </Card>
        <Card style={{ paddingVertical: space.xxs }}>
          <ListRow
            icon={Bell}
            title={t('notifications.settings.title')}
            subtitle={t('notifications.settings.rowHint')}
            onPress={() => router.push('/profile/notifications')}
          />
        </Card>
      </Section>
      <Section title={t('profile.security')}>
        <Card style={{ paddingVertical: space.xxs }}>
          <ListRow
            icon={HeartHandshake}
            iconTone="accent"
            title={t('profile.contact.title')}
            subtitle={contactCount ? t('profile.contact.current', { count: contactCount }) : t('profile.contact.rowHint')}
            divider
            onPress={() => router.push('/profile/contact')}
          />
          <ListRow
            icon={Smartphone}
            iconTone="neutral"
            title={t('profile.sessions.title')}
            subtitle={t('profile.sessions.rowHint')}
            divider
            onPress={() => router.push('/profile/sessions')}
          />
          <ListRow
            icon={MonitorSmartphone}
            iconTone="neutral"
            title={t('profile.logoutAll.title')}
            subtitle={t('profile.logoutAll.hint')}
            onPress={() => setConfirm(true)}
          />
        </Card>
      </Section>
      <Section title={t('profile.menu.privacy')}>
        <Card style={{ paddingVertical: space.xxs }}>
          <ListRow
            icon={ChartNoAxesColumn}
            iconTone="neutral"
            title={t('privacy.usage.title')}
            subtitle={t('privacy.usage.hint')}
            chevron={false}
            divider
            accessibilityHint={t('privacy.usage.hint')}
            accessibilityRole="switch"
            accessibilityState={{ checked: usage.value, disabled: usage.busy }}
            onPress={() => usage.toggle(!usage.value)}
            right={
              <View importantForAccessibility="no-hide-descendants" accessibilityElementsHidden>
                <Switch
                  value={usage.value}
                  onValueChange={usage.toggle}
                  disabled={usage.busy}
                  trackColor={{ false: usage.theme.muted, true: usage.theme.primary }}
                  thumbColor={usage.theme.surface}
                  ios_backgroundColor={usage.theme.muted}
                />
              </View>
            }
          />
          <ListRow
            icon={Download}
            iconTone="neutral"
            title={t('privacy.export.title')}
            subtitle={t('privacy.export.rowHint')}
            divider
            onPress={() => router.push('/profile/data')}
          />
          <ListRow
            icon={UserX}
            iconTone="danger"
            title={t('profile.deactivate.title')}
            subtitle={t('profile.deactivate.hint')}
            onPress={() => router.push('/profile/delete')}
          />
        </Card>
      </Section>
      <Section title={t('profile.menu.helpLegal')}>
        <Card style={{ paddingVertical: space.xxs }}>
          <ListRow icon={LifeBuoy} title={t('profile.help')} subtitle={t('profile.helpHint')} divider onPress={() => router.push('/help')} />
          <ListRow
            icon={ScrollText}
            iconTone="neutral"
            title={t('legal.title')}
            subtitle={t('profile.menu.legalHint')}
            divider
            onPress={() => router.push('/profile/legal')}
          />
          <ListRow
            icon={Info}
            iconTone="neutral"
            title={t('about.title')}
            subtitle={t('about.rowHint', { version: Application.nativeApplicationVersion ?? 'dev' })}
            onPress={() => router.push('/profile/about')}
          />
        </Card>
      </Section>
      <Sheet
        visible={confirm}
        title={t('profile.logoutAll.confirmTitle')}
        subtitle={t('profile.logoutAll.confirmBody')}
        onClose={() => setConfirm(false)}
        options={[{ label: t('profile.logoutAll.confirm'), icon: LogOut, destructive: true, onPress: () => void logoutEverywhere() }]}
      />
    </SubScreen>
  );
}

/** Perfil → Legal: the texts in force (the driver ones only in driver mode). */
export function LegalScreen() {
  const { t } = useTranslation();
  const { mode } = useMode();
  const kinds: LegalKind[] = ['terms', 'privacy', 'community', ...(mode === 'driver' ? DRIVER_KINDS : [])];
  return (
    <SubScreen icon={ScrollText} title={t('legal.title')} subtitle={t('profile.menu.legalHint')}>
      <Card style={{ paddingVertical: space.xxs }}>
        {kinds.map((kind, index) => (
          <ListRow
            key={kind}
            icon={ScrollText}
            iconTone="neutral"
            title={t(`legal.kinds.${kind}`)}
            divider={index < kinds.length - 1}
            onPress={() => router.push({ pathname: '/legal/[kind]', params: { kind } })}
          />
        ))}
      </Card>
    </SubScreen>
  );
}

/** Perfil → Pago preferido (passenger): picked for them when asking for a ride. */
export function PaymentScreen() {
  const { t } = useTranslation();
  const { config } = useAppConfig();
  const draft = useStore(rideDraft);
  const methods = config.payment_methods?.length ? config.payment_methods : DEFAULT_PAYMENT_METHODS;

  useEffect(() => {
    void loadSavedPayment();
  }, []);

  return (
    <SubScreen icon={Wallet} tone="primary" title={t('profile.payment.title')} subtitle={t('profile.payment.body')}>
      <Card style={{ gap: space.sm }}>
        <PaymentChips methods={methods} value={draft.paymentMethod} onChange={setDraftPayment} />
      </Card>
    </SubScreen>
  );
}

/** Within ~150 m: a frequent place that is already saved is not listed twice. */
const near = (a: { lat: number; lng: number }, b: { lat: number; lng: number }) => Math.abs(a.lat - b.lat) < 0.0015 && Math.abs(a.lng - b.lng) < 0.0015;

/** Perfil → Lugares frecuentes (passenger): where they go most, one tap to ask for a moto there. */
export function FrequentPlacesScreen() {
  const { t } = useTranslation();
  const stats = usePassengerStats(true);
  const saved = useSavedPlaces().data ?? [];
  const places = (stats.data?.frequent_places ?? []).filter((place) => !saved.some((s) => near(s, place)));

  return (
    <SubScreen icon={MapPinned} tone="accent" title={t('profile.places.title')} subtitle={t('profile.places.emptyBody')}>
      <Card style={{ paddingVertical: space.xxs }}>
        {stats.isPending ? (
          <View style={{ gap: space.xs, paddingVertical: space.sm }}>
            <Skeleton height={44} radius={radius.tile} />
            <Skeleton height={44} radius={radius.tile} />
          </View>
        ) : places.length ? (
          places.map((place, index) => (
            <ListRow
              key={place.address}
              icon={MapPinned}
              iconTone={index === 0 ? 'accent' : 'primary'}
              title={shortAddress(place.address)}
              subtitle={t('profile.places.visits', { count: place.rides })}
              accessibilityHint={t('profile.places.goHint')}
              divider={index < places.length - 1}
              onPress={() => rideTo(place)}
            />
          ))
        ) : (
          <ListRow icon={MapPinned} iconTone="neutral" title={t('profile.places.empty')} />
        )}
      </Card>
    </SubScreen>
  );
}

/** Perfil → Invita y gana (driver): their code and, before the first trip, the code of who invited them. */
export function InviteScreen() {
  const { t } = useTranslation();
  return (
    <SubScreen icon={Gift} tone="accent" title={t('profile.invite.section')}>
      <InviteCard />
      <InviteesSection />
      <RedeemSection />
    </SubScreen>
  );
}
