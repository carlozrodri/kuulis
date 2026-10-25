import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { FlatList, Modal, Pressable, StyleSheet, Switch, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { ErrorState } from '@/components/ErrorState';
import {
  Bell,
  Bike,
  Check,
  Clock,
  Flame,
  type Icon,
  LifeBuoy,
  Lock,
  Mail,
  Moon,
  ShieldAlert,
  Smartphone,
  User,
  Wallet,
  X,
} from '@/components/icons';
import { showToast } from '@/components/Toast';
import { Card, IconButton, IconTile, ListRow, Row, Skeleton, Txt } from '@/components/ui';
import { Section } from '@/features/profile/components';
import { SubScreen } from '@/features/profile/SubScreen';
import { useNotificationPreferences, useUpdateNotificationPreferences } from '@/hooks/useNotifications';
import { apiErrorMessage } from '@/i18n';
import {
  defaultQuietUpdate,
  normalizeClock,
  QUIET_TIME_OPTIONS,
  quietOff,
  usesDefaultQuiet,
} from '@/lib/notificationPreferences';
import type { NotificationPreferencesUpdate } from '@/lib/types';
import { useMode } from '@/providers/ModeProvider';
import { radius, space, useTheme } from '@/theme';

/** What always arrives, whatever the user picks (only marketing can be turned off). */
const ALWAYS: { key: string; icon: Icon }[] = [
  { key: 'rides', icon: Bike },
  { key: 'wallet', icon: Wallet },
  { key: 'account', icon: User },
  { key: 'support', icon: LifeBuoy },
  { key: 'safety', icon: ShieldAlert },
];

const ROW_HEIGHT = 52;

/** Perfil → Ajustes → Notificaciones (doc 14): promotions on or off, what always arrives and quiet hours. */
export function NotificationSettingsScreen() {
  const { t } = useTranslation();
  const theme = useTheme();
  const prefs = useNotificationPreferences();
  const update = useUpdateNotificationPreferences();
  const [picking, setPicking] = useState<'quiet_start' | 'quiet_end' | null>(null);
  // Doc 21: demand alerts only matter in driver mode (and only servers that know them send the field).
  const { mode } = useMode();

  const save = (change: NotificationPreferencesUpdate) =>
    update.mutate(change, { onError: (e) => showToast(apiErrorMessage(e), 'danger') });

  const data = prefs.data;
  const start = normalizeClock(data?.quiet_start) ?? '';
  const end = normalizeClock(data?.quiet_end) ?? '';
  const defaultStart = normalizeClock(data?.default_quiet_start) ?? '';
  const defaultEnd = normalizeClock(data?.default_quiet_end) ?? '';

  return (
    <SubScreen icon={Bell} tone="primary" title={t('notifications.settings.title')} subtitle={t('notifications.settings.subtitle')}>
      {!data ? (
        prefs.isError ? (
          <ErrorState inline error={prefs.error} title={t('notifications.settings.loadError')} onRetry={() => prefs.refetch()} />
        ) : (
          <View style={{ gap: space.md }}>
            <Skeleton height={140} radius={radius.card} />
            <Skeleton height={220} radius={radius.card} />
          </View>
        )
      ) : (
        <>
          <Section title={t('notifications.settings.marketing')}>
            <Card style={{ paddingVertical: space.xxs }}>
              <ToggleRow
                icon={Smartphone}
                title={t('notifications.settings.marketingPush')}
                subtitle={t('notifications.settings.marketingPushHint')}
                value={data.marketing_push}
                onChange={(value) => save({ marketing_push: value })}
                divider
              />
              <ToggleRow
                icon={Mail}
                title={t('notifications.settings.marketingEmail')}
                subtitle={t('notifications.settings.marketingEmailHint')}
                value={data.marketing_email}
                onChange={(value) => save({ marketing_email: value })}
              />
            </Card>
          </Section>

          {mode === 'driver' && typeof data.demand_alerts === 'boolean' ? (
            <Section title={t('notifications.settings.driver')}>
              <Card style={{ paddingVertical: space.xxs }}>
                <ToggleRow
                  icon={Flame}
                  title={t('notifications.settings.demandAlerts')}
                  subtitle={t('notifications.settings.demandAlertsHint')}
                  value={data.demand_alerts}
                  onChange={(value) => save({ demand_alerts: value })}
                />
              </Card>
            </Section>
          ) : null}

          <Section title={t('notifications.settings.always')}>
            <Card style={{ paddingVertical: space.xxs }}>
              {ALWAYS.map((item, index) => (
                <ListRow
                  key={item.key}
                  icon={item.icon}
                  iconTone="neutral"
                  title={t(`notifications.settings.alwaysItems.${item.key}`)}
                  subtitle={t(`notifications.settings.alwaysItems.${item.key}Hint`)}
                  right={<Lock size={18} color={theme.muted} strokeWidth={2.2} />}
                  divider={index < ALWAYS.length - 1}
                />
              ))}
            </Card>
            <Txt variant="caption" color="muted">
              {t('notifications.settings.alwaysHint')}
            </Txt>
          </Section>

          <Section title={t('notifications.settings.quiet')}>
            <Card style={{ paddingVertical: space.xxs }}>
              <ListRow
                icon={Moon}
                iconTone="primary"
                title={t('notifications.settings.quietFrom')}
                subtitle={start}
                accessibilityLabel={`${t('notifications.settings.quietFrom')}: ${start}`}
                accessibilityHint={t('notifications.settings.changeHint')}
                divider
                onPress={() => setPicking('quiet_start')}
              />
              <ListRow
                icon={Clock}
                iconTone="primary"
                title={t('notifications.settings.quietTo')}
                subtitle={end}
                accessibilityLabel={`${t('notifications.settings.quietTo')}: ${end}`}
                accessibilityHint={t('notifications.settings.changeHint')}
                divider
                onPress={() => setPicking('quiet_end')}
              />
              <DefaultRow
                selected={usesDefaultQuiet(data)}
                label={t('notifications.settings.useDefault', { start: defaultStart, end: defaultEnd })}
                onPress={() => save(defaultQuietUpdate(data))}
              />
            </Card>
            <Txt variant="caption" color="muted">
              {quietOff(start, end)
                ? t('notifications.settings.quietOff')
                : t('notifications.settings.quietHint', { start, end })}
            </Txt>
          </Section>

          <TimeSheet
            visible={picking !== null}
            title={picking === 'quiet_end' ? t('notifications.settings.quietTo') : t('notifications.settings.quietFrom')}
            value={picking === 'quiet_end' ? end : start}
            onClose={() => setPicking(null)}
            onPick={(value) => {
              if (picking) save({ [picking]: value });
              setPicking(null);
            }}
          />
        </>
      )}
    </SubScreen>
  );
}

function ToggleRow({
  icon,
  title,
  subtitle,
  value,
  onChange,
  divider,
}: {
  icon: Icon;
  title: string;
  subtitle: string;
  value: boolean;
  onChange: (value: boolean) => void;
  divider?: boolean;
}) {
  const theme = useTheme();
  return (
    <Pressable
      accessibilityRole="switch"
      accessibilityLabel={title}
      accessibilityHint={subtitle}
      accessibilityState={{ checked: value }}
      onPress={() => onChange(!value)}
      style={({ pressed }) => [
        styles.row,
        divider && { borderBottomWidth: 1, borderBottomColor: theme.divider },
        { opacity: pressed ? 0.6 : 1 },
      ]}>
      <IconTile icon={icon} tone="primary" size={40} />
      <View style={{ flex: 1 }}>
        <Txt variant="bodyStrong">{title}</Txt>
        <Txt variant="caption" color="muted">
          {subtitle}
        </Txt>
      </View>
      <View importantForAccessibility="no-hide-descendants" accessibilityElementsHidden>
        <Switch
          value={value}
          onValueChange={onChange}
          trackColor={{ false: theme.border, true: theme.primary }}
          thumbColor={theme.surface}
          ios_backgroundColor={theme.border}
        />
      </View>
    </Pressable>
  );
}

function DefaultRow({ selected, label, onPress }: { selected: boolean; label: string; onPress: () => void }) {
  const theme = useTheme();
  return (
    <Pressable
      accessibilityRole="radio"
      accessibilityState={{ selected, checked: selected }}
      accessibilityLabel={label}
      disabled={selected}
      onPress={onPress}
      style={({ pressed }) => [styles.row, { opacity: pressed ? 0.6 : 1 }]}>
      <View
        style={[
          styles.radio,
          { borderColor: selected ? theme.primary : theme.border, backgroundColor: selected ? theme.primary : 'transparent' },
        ]}>
        {selected ? <Check size={14} color={theme.onPrimary} strokeWidth={3} /> : null}
      </View>
      <Txt style={{ flex: 1 }}>{label}</Txt>
    </Pressable>
  );
}

/** Bottom sheet with every half hour of the day (Caracas time). */
function TimeSheet({
  visible,
  title,
  value,
  onPick,
  onClose,
}: {
  visible: boolean;
  title: string;
  value: string;
  onPick: (value: string) => void;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const index = Math.max(0, QUIET_TIME_OPTIONS.indexOf(value));
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose} statusBarTranslucent>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={t('common.close')}
        style={[StyleSheet.absoluteFill, { backgroundColor: theme.backdrop }]}
        onPress={onClose}
      />
      <View style={[styles.sheet, { backgroundColor: theme.surface, paddingBottom: Math.max(insets.bottom, space.md) + space.xs }]}>
        <View style={[styles.handle, { backgroundColor: theme.border }]} />
        <Row style={{ justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <View style={{ flex: 1 }}>
            <Txt variant="heading">{title}</Txt>
            <Txt color="muted" style={{ marginTop: 4 }}>
              {t('notifications.settings.caracasTime')}
            </Txt>
          </View>
          <IconButton icon={X} label={t('common.close')} onPress={onClose} tone="plain" size={40} />
        </Row>
        <FlatList
          data={QUIET_TIME_OPTIONS}
          keyExtractor={(item) => item}
          style={{ marginTop: space.sm, maxHeight: ROW_HEIGHT * 7 }}
          initialScrollIndex={Math.max(0, index - 3)}
          getItemLayout={(_, i) => ({ length: ROW_HEIGHT, offset: ROW_HEIGHT * i, index: i })}
          renderItem={({ item }) => {
            const selected = item === value;
            return (
              <Pressable
                accessibilityRole="radio"
                accessibilityState={{ selected, checked: selected }}
                accessibilityLabel={item}
                onPress={() => onPick(item)}
                style={({ pressed }) => [
                  styles.time,
                  { backgroundColor: selected ? theme.surfaceAlt : 'transparent', opacity: pressed ? 0.6 : 1 },
                ]}>
                <Txt variant={selected ? 'bodyStrong' : 'body'} tabular style={{ flex: 1 }}>
                  {item}
                </Txt>
                {selected ? <Check size={20} color={theme.primary} strokeWidth={2.4} /> : null}
              </Pressable>
            );
          }}
        />
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 14, paddingVertical: 12, minHeight: 60 },
  radio: { width: 22, height: 22, borderRadius: 11, borderWidth: 2, alignItems: 'center', justifyContent: 'center' },
  time: {
    height: ROW_HEIGHT,
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: space.md,
    borderRadius: radius.field,
  },
  sheet: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    borderTopLeftRadius: radius.sheet,
    borderTopRightRadius: radius.sheet,
    paddingHorizontal: space.lg,
    paddingTop: 10,
  },
  handle: { width: 40, height: 5, borderRadius: 5, alignSelf: 'center', marginBottom: space.md },
});
