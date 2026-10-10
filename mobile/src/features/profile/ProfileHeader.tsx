import { router } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { StyleSheet, useWindowDimensions, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Circle, Path } from 'react-native-svg';

import { BadgeCheck, Bike, Calendar, MapPin, Pencil, Star } from '@/components/icons';
import { IconButton, Txt } from '@/components/ui';
import { memberSince } from '@/lib/profile';
import { useAuth } from '@/providers/AuthProvider';
import { type AppMode } from '@/providers/ModeProvider';
import { space, useTheme } from '@/theme';

import { HeroPill, ProfileAvatar } from './components';
import { useAvatarPicker } from './useAvatarPicker';

/** The overlap of the stats card over the green header. */
export const HEADER_OVERLAP = 44;

/** Verde Ávila header: photo (tap to change), name, email and badges. */
export function ProfileHeader({ mode, rating }: { mode: AppMode; rating: number | null }) {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const { width } = useWindowDimensions();
  const { user } = useAuth();
  const avatar = useAvatarPicker();

  const since = memberSince(user?.created_at, i18n.language);

  return (
    <View style={[styles.hero, { backgroundColor: theme.hero, paddingTop: insets.top + space.sm }]}>
      <Svg width={width} height={150} viewBox="0 0 390 150" preserveAspectRatio="none" style={styles.mountains} pointerEvents="none">
        <Path
          d="M0 150 L0 92 C40 70 70 42 110 58 C150 76 170 26 215 28 C260 30 280 74 320 64 C350 58 370 46 390 50 L390 150 Z"
          fill={theme.heroShade}
        />
        <Path
          d="M0 150 L0 120 C60 102 110 112 160 98 C210 84 250 106 300 100 C340 96 365 104 390 98 L390 150 Z"
          fill={theme.heroShade}
          opacity={0.6}
        />
      </Svg>
      <Svg width={160} height={160} style={styles.sun} pointerEvents="none">
        <Circle cx={80} cy={80} r={64} fill={theme.accent} opacity={0.1} />
        <Circle cx={80} cy={80} r={34} fill={theme.accent} opacity={0.18} />
      </Svg>

      <View style={styles.topBar}>
        <Txt variant="subtitle" style={{ color: theme.onHero }} accessibilityRole="header">
          {t('tabs.profile')}
        </Txt>
        <IconButton icon={Pencil} label={t('profile.edit.title')} tone="onHero" size={40} onPress={() => router.push('/profile/edit')} />
      </View>

      <View style={styles.identity}>
        <ProfileAvatar
          name={user?.full_name}
          email={user?.email}
          photoUrl={user?.avatar_url}
          busy={avatar.busy}
          onEdit={avatar.open}
          editLabel={t('profile.photo.change')}
        />
        <View style={{ alignItems: 'center', gap: 2, marginTop: space.sm }}>
          <Txt variant="title" align="center" numberOfLines={2} style={{ color: theme.onHero }}>
            {user?.full_name || t('profile.noName')}
          </Txt>
          <Txt align="center" numberOfLines={1} style={{ color: theme.onHero, opacity: 0.85 }}>
            {user?.email}
          </Txt>
        </View>
        <View style={styles.pills}>
          <HeroPill
            icon={mode === 'driver' ? Bike : MapPin}
            label={t(`mode.${mode}.title`)}
          />
          {rating != null ? (
            <HeroPill icon={Star} label={rating.toFixed(1)} accent />
          ) : null}
          {user?.is_verified ? <HeroPill icon={BadgeCheck} label={t('profile.verifiedShort')} /> : null}
          {since ? <HeroPill icon={Calendar} label={t('profile.since', { date: since })} /> : null}
        </View>
      </View>

      {avatar.sheet}
    </View>
  );
}

const styles = StyleSheet.create({
  hero: { paddingHorizontal: space.lg, paddingBottom: space.xl + HEADER_OVERLAP, overflow: 'hidden' },
  mountains: { position: 'absolute', left: 0, bottom: 0 },
  sun: { position: 'absolute', right: -40, top: 10 },
  topBar: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', minHeight: 44 },
  identity: { alignItems: 'center', marginTop: space.xs },
  pills: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center', gap: space.xs, marginTop: space.md },
});
