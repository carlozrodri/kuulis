import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { RefreshControl, StyleSheet, TextInput, View } from 'react-native';

import { Backpack, Check, CircleX, MessageCircle, MessagesSquare, PackageSearch, X } from '@/components/icons';
import { showToast } from '@/components/Toast';
import { Button, EmptyState, IconTile, Notice, Screen, Skeleton, Txt } from '@/components/ui';
import { RideContextCard } from '@/features/reports/components';
import { FlowHeader } from '@/features/wallet/components';
import { useAppConfig } from '@/hooks/useDriver';
import { useAnswerLostItem, useCreateLostItem, useLostItem, useRide } from '@/hooks/useRides';
import { apiErrorMessage } from '@/i18n';
import { ApiError } from '@/lib/api';
import { confirmHaptic } from '@/lib/feedback';
import { rideRole } from '@/lib/ride';
import { LOST_ITEM_MAX, LOST_ITEM_MIN, lostItemAllowed, lostItemProblem, lostItemState } from '@/lib/support';
import type { LostItem, Ride } from '@/lib/types';
import { useAuth } from '@/providers/AuthProvider';
import { useMode } from '@/providers/ModeProvider';
import { fonts, radius, space, useTheme } from '@/theme';

function leave() {
  if (router.canGoBack()) router.back();
  else router.replace('/rides');
}

const openChat = (rideId: string) => router.push({ pathname: '/ride/chat', params: { id: rideId } });
const openConversation = (reportId: string) => router.push({ pathname: '/reports/[id]', params: { id: reportId } });

/**
 * "Olvidé un objeto" (doc 13). The passenger describes it and follows the driver's answer; when the driver has
 * it, the ride chat opens for a while to agree on the hand-over without sharing phones. The driver (opened
 * from the "Un pasajero olvidó algo" notification) answers "Lo tengo" / "No lo tengo" here.
 */
export function LostItemScreen() {
  const { t } = useTranslation();
  const theme = useTheme();
  const { user } = useAuth();
  const { mode } = useMode();
  const { id } = useLocalSearchParams<{ id: string }>();
  const ride = useRide(id);
  const item = useLostItem(id);
  const role = ride.data ? rideRole(ride.data, user?.id, mode ?? 'passenger') : null;

  const loading = ride.isPending || item.isPending;
  const error = ride.error ?? item.error;

  return (
    <Screen
      header={<FlowHeader title={role === 'driver' ? t('lostItem.driverTitle') : t('lostItem.title')} onBack={leave} />}
      refreshControl={
        <RefreshControl
          refreshing={item.isRefetching}
          onRefresh={() => {
            void item.refetch();
            void ride.refetch();
          }}
          tintColor={theme.primary}
        />
      }>
      {loading ? (
        <View style={{ gap: space.sm }}>
          <Skeleton height={120} radius={radius.card} />
          <Skeleton height={90} radius={radius.card} />
        </View>
      ) : error || !ride.data ? (
        <View>
          <EmptyState icon={CircleX} title={t('common.error')} body={apiErrorMessage(error)} />
          <Button
            title={t('common.retry')}
            variant="secondary"
            onPress={() => {
              void ride.refetch();
              void item.refetch();
            }}
          />
        </View>
      ) : (
        <View style={{ gap: space.md }}>
          <RideContextCard ride={ride.data} />
          {role === 'driver' ? (
            item.data ? (
              <DriverAnswer item={item.data} />
            ) : (
              <EmptyState icon={PackageSearch} title={t('lostItem.noneDriver')} />
            )
          ) : item.data ? (
            <PassengerStatus item={item.data} ride={ride.data} />
          ) : (
            <LostItemForm ride={ride.data} />
          )}
        </View>
      )}
    </Screen>
  );
}

/** The passenger describes the object (3 to 500 characters). */
function LostItemForm({ ride }: { ride: Ride }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const { config } = useAppConfig();
  const create = useCreateLostItem(ride.id);
  const item = useLostItem(ride.id);
  const [description, setDescription] = useState('');
  const [touched, setTouched] = useState(false);
  const problem = lostItemProblem(description);
  const allowed = lostItemAllowed(ride, config);

  const submit = () => {
    setTouched(true);
    if (problem) return;
    create.mutate(description.trim(), {
      onSuccess: () => confirmHaptic(),
      onError: (error) => {
        // Already asked (another device, a double tap): show what is there.
        if (error instanceof ApiError && error.code === 'lost_item_exists') void item.refetch();
        else showToast(apiErrorMessage(error), 'danger');
      },
    });
  };

  if (!allowed) {
    return (
      <Notice tone="warning" title={t('lostItem.tooLateTitle')}>
        <Txt variant="caption" style={{ fontSize: 14, lineHeight: 20 }}>
          {t('lostItem.tooLate')}
        </Txt>
        <Button
          title={t('help.contact')}
          variant="secondary"
          size="sm"
          style={{ alignSelf: 'flex-start' }}
          onPress={() => router.push({ pathname: '/report', params: { ride_id: ride.id, category: 'lost_item', direct: '1' } })}
        />
      </Notice>
    );
  }

  return (
    <View style={{ gap: space.sm }}>
      <View style={{ gap: space.xxs }}>
        <Txt variant="subtitle">{t('lostItem.formTitle')}</Txt>
        <Txt color="muted">{t('lostItem.formBody', { name: ride.driver?.first_name ?? '' })}</Txt>
      </View>
      <TextInput
        accessibilityLabel={t('lostItem.label')}
        accessibilityHint={t('lostItem.minHint', { min: LOST_ITEM_MIN })}
        value={description}
        onChangeText={setDescription}
        onBlur={() => setTouched(description.length > 0)}
        placeholder={t('lostItem.placeholder')}
        placeholderTextColor={theme.muted}
        selectionColor={theme.primary}
        cursorColor={theme.primary}
        multiline
        maxLength={LOST_ITEM_MAX}
        maxFontSizeMultiplier={1.6}
        textAlignVertical="top"
        style={[
          styles.textarea,
          { color: theme.text, backgroundColor: theme.surface, borderColor: touched && problem ? theme.danger : theme.border },
        ]}
      />
      {touched && problem ? (
        <Txt variant="caption" color="danger">
          {problem === 'too_long' ? t('lostItem.tooLong', { max: LOST_ITEM_MAX }) : t('lostItem.minHint', { min: LOST_ITEM_MIN })}
        </Txt>
      ) : null}
      <Button title={t('lostItem.submit')} icon={Backpack} loading={create.isPending} onPress={submit} />
      <Txt variant="caption" color="muted">
        {t('lostItem.privacy')}
      </Txt>
    </View>
  );
}

/** Waiting for the driver, "Lo tiene" (chat), or "No lo encontró". */
function PassengerStatus({ item, ride }: { item: LostItem; ride: Ride }) {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const state = lostItemState(item);
  const name = ride.driver?.first_name ?? '';
  const until = item.chat_until
    ? new Date(item.chat_until).toLocaleString(i18n.language, { weekday: 'long', hour: 'numeric', minute: '2-digit' })
    : '';
  const tone = state === 'not_found' ? 'neutral' : state === 'waiting' ? 'info' : 'success';
  const icon = state === 'not_found' ? X : state === 'waiting' ? PackageSearch : Check;

  return (
    <View style={{ gap: space.md }}>
      <View style={[styles.card, { backgroundColor: theme.surface }]}>
        <View style={styles.titleRow}>
          <IconTile icon={icon} tone={tone} size={44} />
          <Txt variant="subtitle" style={{ flex: 1 }} accessibilityRole="header">
            {t(`lostItem.state.${state}.title`, { name })}
          </Txt>
        </View>
        <Txt color="muted">{t(`lostItem.state.${state}.body`, { name, until })}</Txt>
        <View style={[styles.quote, { backgroundColor: theme.background }]}>
          <Txt variant="caption" color="muted">
            {t('lostItem.youWrote')}
          </Txt>
          <Txt>{item.description}</Txt>
        </View>
      </View>
      {state === 'chat' ? (
        <Button title={t('lostItem.openChat', { name })} icon={MessageCircle} onPress={() => openChat(ride.id)} />
      ) : null}
      {item.report_id ? (
        <Button
          title={t('lostItem.openConversation')}
          variant={state === 'chat' ? 'ghost' : 'secondary'}
          icon={MessagesSquare}
          onPress={() => openConversation(item.report_id!)}
        />
      ) : null}
    </View>
  );
}

/** "Un pasajero olvidó algo": the driver answers once. */
function DriverAnswer({ item }: { item: LostItem }) {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const answer = useAnswerLostItem(item.ride_id);
  const state = lostItemState(item);
  const until = item.chat_until
    ? new Date(item.chat_until).toLocaleString(i18n.language, { weekday: 'long', hour: 'numeric', minute: '2-digit' })
    : '';

  const reply = (hasIt: boolean) =>
    answer.mutate(hasIt, {
      onSuccess: () => confirmHaptic(),
      onError: (error) => showToast(apiErrorMessage(error), 'danger'),
    });

  return (
    <View style={{ gap: space.md }}>
      <View style={[styles.card, { backgroundColor: theme.surface }]}>
        <View style={styles.titleRow}>
          <IconTile icon={Backpack} tone="accent" size={44} />
          <Txt variant="subtitle" style={{ flex: 1 }} accessibilityRole="header">
            {t('lostItem.driver.title')}
          </Txt>
        </View>
        <View style={[styles.quote, { backgroundColor: theme.background }]}>
          <Txt variant="caption" color="muted">
            {t('lostItem.driver.theyWrote')}
          </Txt>
          <Txt>{item.description}</Txt>
        </View>
        {state === 'waiting' ? (
          <Txt color="muted">{t('lostItem.driver.ask')}</Txt>
        ) : (
          <Txt color="muted">{t(`lostItem.driver.answered.${state}`, { until })}</Txt>
        )}
      </View>
      {state === 'waiting' ? (
        <View style={styles.answers}>
          <Button
            title={t('lostItem.driver.hasIt')}
            icon={Check}
            size="lg"
            style={{ flex: 1 }}
            loading={answer.isPending && answer.variables === true}
            disabled={answer.isPending}
            onPress={() => reply(true)}
          />
          <Button
            title={t('lostItem.driver.notFound')}
            variant="secondary"
            icon={X}
            size="lg"
            style={{ flex: 1 }}
            loading={answer.isPending && answer.variables === false}
            disabled={answer.isPending}
            onPress={() => reply(false)}
          />
        </View>
      ) : null}
      {state === 'chat' ? (
        <Button title={t('lostItem.driver.openChat')} icon={MessageCircle} onPress={() => openChat(item.ride_id)} />
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: { borderRadius: radius.card, padding: space.md, gap: space.sm },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
  quote: { borderRadius: radius.field, padding: space.sm, gap: 2 },
  answers: { flexDirection: 'row', gap: space.sm },
  textarea: {
    minHeight: 120,
    maxHeight: 220,
    borderWidth: 1.5,
    borderRadius: radius.field,
    paddingHorizontal: 14,
    paddingTop: 12,
    paddingBottom: 12,
    fontFamily: fonts.medium,
    fontSize: 16,
    lineHeight: 22,
  },
});
