import { router } from 'expo-router';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Linking, Pressable, type StyleProp, StyleSheet, View, type ViewStyle } from 'react-native';

import { ChevronRight, ExternalLink, Megaphone, Sparkles, TriangleAlert, X } from '@/components/icons';
import { Txt } from '@/components/ui';
import { dismissAnnouncement, useBootstrap, useDismissedAnnouncements } from '@/hooks/useBootstrap';
import { useDriverProfile } from '@/hooks/useDriver';
import { type Announcement, type AnnouncementStyle, ctaTarget, localize, visibleAnnouncements } from '@/lib/bootstrap';
import { selectionHaptic } from '@/lib/feedback';
import { useMode } from '@/providers/ModeProvider';
import { elevation, radius, space, type Theme, useTheme } from '@/theme';

/** At most this many at once, so the map stays visible; closing one shows the next. */
const MAX_BANNERS = 2;

function styleColors(theme: Theme, style: AnnouncementStyle) {
  switch (style) {
    case 'warning':
      return { bg: theme.warningSoft, fg: theme.warning, icon: TriangleAlert };
    case 'promo':
      return { bg: theme.accentSoft, fg: theme.onAccentSoft, icon: Sparkles };
    case 'info':
    default:
      return { bg: theme.infoSoft, fg: theme.info, icon: Megaphone };
  }
}

/**
 * Announcements from the bootstrap (doc 10) at the top of the passenger and driver homes. Closed ones never
 * come back: remembered on the device and told to the server.
 */
export function AnnouncementBanners({ style }: { style?: StyleProp<ViewStyle> }) {
  const { data } = useBootstrap();
  const dismissed = useDismissedAnnouncements();
  const { mode } = useMode();
  const items = useMemo(
    () =>
      // Wait until the closed list is read, so a closed banner does not flash.
      dismissed === null || !data
        ? []
        : visibleAnnouncements(data.announcements, { mode, area: data.area, dismissed }).slice(0, MAX_BANNERS),
    [data, dismissed, mode],
  );
  if (!items.length) return null;
  return (
    <View style={[{ gap: space.xs }, style]} pointerEvents="box-none">
      {items.map((item) => (
        <AnnouncementBanner key={item.id} announcement={item} />
      ))}
    </View>
  );
}

function AnnouncementBanner({ announcement }: { announcement: Announcement }) {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const { mode, setMode } = useMode();
  const driver = useDriverProfile(mode === 'driver');
  const hasWallet = driver.data?.status === 'approved' || driver.data?.status === 'suspended';
  const colors = styleColors(theme, announcement.style);
  const title = localize(announcement.title, i18n.language);
  const body = localize(announcement.body, i18n.language);
  const target = ctaTarget(announcement.cta, { mode, hasWallet });
  const label = announcement.cta ? localize(announcement.cta.label, i18n.language) || t('control.banner.open') : '';
  const BannerIcon = colors.icon;

  const open = () => {
    if (!target) return;
    selectionHaptic();
    if (target.kind === 'url') void Linking.openURL(target.url).catch(() => undefined);
    else if (target.kind === 'route') router.navigate(target.href);
    else {
      // "Hazte motorizado": driver mode shows the sign-up steps on its home.
      void setMode('driver');
      router.navigate('/');
    }
  };

  return (
    <View
      accessibilityRole="summary"
      style={[styles.banner, { backgroundColor: theme.surface, borderLeftColor: colors.fg }, elevation(theme)]}>
      <View style={[styles.icon, { backgroundColor: colors.bg }]}>
        <BannerIcon size={18} color={colors.fg} strokeWidth={2.2} />
      </View>
      <View style={{ flex: 1, gap: 2 }}>
        {title ? (
          <Txt variant="bodyStrong" numberOfLines={2}>
            {title}
          </Txt>
        ) : null}
        {body ? (
          <Txt variant="caption" color="muted" numberOfLines={4}>
            {body}
          </Txt>
        ) : null}
        {target ? (
          <Pressable
            accessibilityRole={target.kind === 'url' ? 'link' : 'button'}
            onPress={open}
            hitSlop={8}
            style={({ pressed }) => [styles.cta, { backgroundColor: colors.bg, opacity: pressed ? 0.75 : 1 }]}>
            <Txt variant="label" style={{ color: colors.fg }} numberOfLines={1}>
              {label}
            </Txt>
            {target.kind === 'url' ? (
              <ExternalLink size={14} color={colors.fg} strokeWidth={2.4} />
            ) : (
              <ChevronRight size={16} color={colors.fg} strokeWidth={2.4} />
            )}
          </Pressable>
        ) : null}
      </View>
      {announcement.dismissible ? (
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={t('control.banner.close')}
          hitSlop={10}
          onPress={() => {
            selectionHaptic();
            void dismissAnnouncement(announcement.id);
          }}
          style={({ pressed }) => [styles.close, { opacity: pressed ? 0.6 : 1 }]}>
          <X size={18} color={theme.muted} strokeWidth={2.4} />
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  banner: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: space.sm,
    borderRadius: radius.tile,
    borderLeftWidth: 4,
    padding: space.sm,
  },
  icon: { width: 34, height: 34, borderRadius: 17, alignItems: 'center', justifyContent: 'center' },
  cta: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    gap: 4,
    marginTop: space.xxs,
    borderRadius: radius.pill,
    paddingHorizontal: space.sm,
    paddingVertical: 6,
  },
  close: { width: 28, height: 28, alignItems: 'center', justifyContent: 'center' },
});
