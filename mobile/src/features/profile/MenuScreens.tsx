/**
 * Pages behind the profile menu, so the profile itself stays short: account and preferences, security and
 * privacy, legal, preferred payment, frequent places and invites.
 */
import * as Haptics from 'expo-haptics';
import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import {
  Download,
  Gift,
  HeartHandshake,
  LockKeyhole,
  LogOut,
  MapPinned,
  Moon,
  MonitorSmartphone,
  Pencil,
  ScrollText,
  Settings,
  ShieldCheck,
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
import { api } from '@/lib/api';
import { DRIVER_KINDS, type LegalKind } from '@/lib/legal';
import { DEFAULT_PAYMENT_METHODS, shortAddress } from '@/lib/ride';
import { useStore } from '@/lib/store';
import { useAuth } from '@/providers/AuthProvider';
import { useMode } from '@/providers/ModeProvider';
import { radius, setThemePreference, space, themePreference, type ThemePreference } from '@/theme';

import { Section, Segmented } from './components';
import { InviteCard, RedeemSection } from './ReferralCard';
import { rideTo } from './SavedPlaces';
import { SubScreen } from './SubScreen';

const LANGUAGE_LABELS: Record<Locale, string> = { es: 'Español', en: 'English' };

/** Perfil → Cuenta y preferencias: edit the profile, password, language and appearance. */
export function AccountSettingsScreen() {
  const { t, i18n } = useTranslation();
  const { refreshUser } = useAuth();
  const preference = useStore(themePreference);

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

  return (
    <SubScreen icon={Settings} tone="primary" title={t('profile.menu.settings')} subtitle={t('profile.menu.settingsHint')}>
      <Card style={{ paddingVertical: space.xxs }}>
        <ListRow icon={Pencil} title={t('profile.edit.title')} subtitle={t('profile.edit.hint')} divider onPress={() => router.push('/profile/edit')} />
        <ListRow icon={LockKeyhole} title={t('profile.password.title')} subtitle={t('profile.password.hint')} onPress={() => router.push('/profile/password')} />
      </Card>
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
      </Section>
    </SubScreen>
  );
}

/** Perfil → Seguridad y privacidad: trusted contacts, sessions, my data and deleting the account. */
export function SecurityScreen() {
  const { t } = useTranslation();
  const { user, signOut } = useAuth();
  const contactCount = useTrustedContacts(!!user).data?.length ?? 0;
  const [confirm, setConfirm] = useState(false);

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
    <SubScreen icon={ShieldCheck} tone="accent" title={t('profile.menu.security')} subtitle={t('profile.menu.securityHint')}>
      <Card style={{ paddingVertical: space.xxs }}>
        <ListRow
          icon={HeartHandshake}
          iconTone="accent"
          title={t('profile.contact.title')}
          subtitle={contactCount ? t('profile.contact.current', { count: contactCount }) : t('profile.contact.rowHint')}
          onPress={() => router.push('/profile/contact')}
        />
      </Card>
      <Section title={t('profile.menu.sessions')}>
        <Card style={{ paddingVertical: space.xxs }}>
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
      <RedeemSection />
    </SubScreen>
  );
}
