import * as Haptics from 'expo-haptics';
import { useTranslation } from 'react-i18next';
import { ScrollView, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { HeroHeader, HeroSheet } from '@/components/HeroHeader';
import { Bike, ChevronRight, Gift, type Icon, MapPin } from '@/components/icons';
import { Card, IconTile, Notice, type Tone, Txt } from '@/components/ui';
import { type AppMode, useMode } from '@/providers/ModeProvider';
import { space, useTheme } from '@/theme';

function ModeCard({ mode, icon, tone }: { mode: AppMode; icon: Icon; tone: Tone }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const { setMode } = useMode();
  return (
    <Card
      elevated
      onPress={() => {
        void Haptics.selectionAsync().catch(() => undefined);
        void setMode(mode);
      }}
      accessibilityLabel={`${t(`mode.${mode}.title`)}. ${t(`mode.${mode}.body`)}`}
      style={styles.modeCard}>
      <IconTile icon={icon} tone={tone} size={64} />
      <View style={{ flex: 1, gap: 4 }}>
        <Txt variant="subtitle" style={{ fontSize: 19 }}>
          {t(`mode.${mode}.title`)}
        </Txt>
        <Txt variant="caption" color="muted" style={{ fontSize: 14, lineHeight: 20 }}>
          {t(`mode.${mode}.body`)}
        </Txt>
      </View>
      <ChevronRight size={22} color={theme.text} strokeWidth={2.2} />
    </Card>
  );
}

/** First screen after signing in: pick Pasajero or Motorizado. Can be changed later from Profile. */
export default function WelcomeScreen() {
  const { t } = useTranslation();
  const theme = useTheme();
  const insets = useSafeAreaInsets();

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: theme.background }}
      contentContainerStyle={{ flexGrow: 1, paddingBottom: insets.bottom + space.xl }}
      bounces={false}>
      <HeroHeader title={t('mode.title')} subtitle={t('mode.subtitle')} />
      <HeroSheet>
        <View style={{ gap: space.md }}>
          <ModeCard mode="passenger" icon={MapPin} tone="primary" />
          <ModeCard mode="driver" icon={Bike} tone="accent" />
          <Notice tone="accent" icon={Gift}>
            {t('mode.driverPromo')}
          </Notice>
        </View>
      </HeroSheet>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  modeCard: { flexDirection: 'row', alignItems: 'center', gap: space.md, padding: 18, borderRadius: 22 },
});
