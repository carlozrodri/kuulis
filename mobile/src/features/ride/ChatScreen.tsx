import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  ActivityIndicator,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  TextInput,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { ErrorState } from '@/components/ErrorState';
import { Backpack, ChevronLeft, MessageCircle, Send } from '@/components/icons';
import { showToast } from '@/components/Toast';
import { EmptyState, IconButton, Notice, Txt } from '@/components/ui';
import { useFlag } from '@/hooks/useBootstrap';
import { useLostItem, useQueuedActions, useRide, useRideMessages, useSendMessage } from '@/hooks/useRides';
import { apiErrorMessage } from '@/i18n';
import { ApiError } from '@/lib/api';
import { selectionHaptic } from '@/lib/feedback';
import { isChatOpen, rideRole } from '@/lib/ride';
import type { RideMessage } from '@/lib/types';
import { useAuth } from '@/providers/AuthProvider';
import { useMode } from '@/providers/ModeProvider';
import { fonts, radius, space, useTheme } from '@/theme';

import { Avatar } from './components';
import { chatOpen, clearUnread } from './store';

const QUICK_REPLIES = {
  passenger: ['onMyWay', 'atEntrance', 'whereAreYou', 'thanks'],
  driver: ['onMyWay', 'arrived', 'outside', 'traffic'],
} as const;

/**
 * Ride chat (driver ⇄ passenger) with one-tap quick replies. Doc 13: after a completed ride it stays open
 * while a lost item chat is (`chat_open`), so they agree on the hand-over without sharing phones.
 */
export function ChatScreen() {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const { user } = useAuth();
  const { mode } = useMode();
  const { id } = useLocalSearchParams<{ id: string }>();
  const ride = useRide(id).data;
  const afterRide = ride?.status === 'completed';
  const lostItem = useLostItem(id, afterRide).data;
  const lostItemChat = afterRide && !!lostItem?.chat_open;
  const messages = useRideMessages(id, lostItemChat);
  const send = useSendMessage(id ?? '');
  const [text, setText] = useState('');
  const [closed, setClosed] = useState(false);
  // Switched off remotely (doc 10): the history stays readable, writing is not offered.
  const chatOn = useFlag('chat');

  useEffect(() => {
    if (!id) return;
    chatOpen.set(id);
    clearUnread(id);
    return () => {
      if (chatOpen.get() === id) chatOpen.set(null);
      clearUnread(id);
    };
  }, [id]);

  const role = ride ? rideRole(ride, user?.id, mode ?? 'passenger') : 'passenger';
  const other = role === 'passenger' ? ride?.driver : ride?.passenger;
  const canWrite = chatOn && !closed && (!ride || isChatOpen(ride.status) || lostItemChat);
  const chatUntil = lostItem?.chat_until
    ? new Date(lostItem.chat_until).toLocaleString(i18n.language, { weekday: 'long', hour: 'numeric', minute: '2-digit' })
    : null;
  // Doc 20: messages written without signal show as "Enviando…" until the queue sends them.
  const queued = useQueuedActions(id, 'message');
  const items = useMemo(() => {
    const pending: RideMessage[] = queued.map((item) => ({
      id: `queued-${item.id}`,
      ride_id: item.rideId,
      sender_id: user?.id ?? '',
      text: (item.body as { text?: string } | undefined)?.text ?? '',
      created_at: new Date(item.createdAt).toISOString(),
    }));
    return [...(messages.data ?? []), ...pending].reverse();
  }, [messages.data, queued, user?.id]);

  const submit = (value: string) => {
    const body = value.trim();
    if (!body || !id || send.isPending) return;
    selectionHaptic();
    send.mutate(body.slice(0, 500), {
      onSuccess: () => setText(''),
      onError: (error) => {
        if (error instanceof ApiError && error.code === 'chat_closed') setClosed(true);
        showToast(apiErrorMessage(error), 'danger');
      },
    });
  };

  const renderItem = ({ item }: { item: RideMessage }) => {
    const mine = item.sender_id === user?.id;
    const sending = item.id.startsWith('queued-');
    return (
      <View style={[styles.bubbleRow, { justifyContent: mine ? 'flex-end' : 'flex-start' }]}>
        <View
          style={[
            styles.bubble,
            mine
              ? { backgroundColor: theme.primary, borderBottomRightRadius: 6 }
              : { backgroundColor: theme.surface, borderBottomLeftRadius: 6 },
          ]}>
          <Txt style={{ color: mine ? theme.onPrimary : theme.text }}>{item.text}</Txt>
          <Txt variant="micro" style={{ color: mine ? theme.onPrimary : theme.muted, opacity: 0.75, alignSelf: 'flex-end' }}>
            {sending
              ? t('offline.sending')
              : new Date(item.created_at).toLocaleTimeString(i18n.language, { hour: '2-digit', minute: '2-digit' })}
          </Txt>
        </View>
      </View>
    );
  };

  return (
    <KeyboardAvoidingView
      style={{ flex: 1, backgroundColor: theme.background }}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <View style={[styles.header, { paddingTop: insets.top + space.xs, backgroundColor: theme.surface, borderBottomColor: theme.border }]}>
        <IconButton icon={ChevronLeft} label={t('common.back')} tone="plain" onPress={() => router.back()} />
        <Avatar name={other?.first_name} photoUrl={role === 'passenger' ? ride?.driver?.photo_url : null} size={40} />
        <View style={{ flex: 1 }}>
          <Txt variant="subtitle" numberOfLines={1}>
            {other?.first_name ?? t('chat.title')}
          </Txt>
          <Txt variant="caption" color="muted">
            {role === 'passenger' ? t('chat.yourDriver') : t('chat.yourPassenger')}
          </Txt>
        </View>
      </View>

      {lostItemChat ? (
        <View style={[styles.lostItem, { backgroundColor: theme.surfaceAlt }]}>
          <Backpack size={18} color={theme.primary} strokeWidth={2.2} />
          <Txt variant="caption" style={{ flex: 1 }}>
            {chatUntil ? t('lostItem.chatBanner', { until: chatUntil }) : t('lostItem.chatBannerShort')}
          </Txt>
        </View>
      ) : null}

      <FlatList
        inverted
        data={items}
        keyExtractor={(item) => item.id}
        renderItem={renderItem}
        contentContainerStyle={{ padding: space.md, gap: space.xs, flexGrow: 1 }}
        keyboardShouldPersistTaps="handled"
        ListEmptyComponent={
          messages.isPending ? (
            <ActivityIndicator color={theme.primary} style={{ marginTop: space.xl }} />
          ) : messages.isError ? (
            <View style={{ transform: [{ scaleY: -1 }] }}>
              <ErrorState error={messages.error} onRetry={() => messages.refetch()} />
            </View>
          ) : (
            // Inverted list: flip the empty state back.
            <View style={{ transform: [{ scaleY: -1 }] }}>
              <EmptyState icon={MessageCircle} title={t('chat.emptyTitle')} body={t('chat.emptyBody')} />
            </View>
          )
        }
      />

      <View style={[styles.composer, { backgroundColor: theme.surface, paddingBottom: Math.max(insets.bottom, space.sm), borderTopColor: theme.border }]}>
        {canWrite ? (
          <>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} keyboardShouldPersistTaps="handled" contentContainerStyle={styles.quick}>
              {(lostItemChat ? [] : QUICK_REPLIES[role]).map((key) => (
                <Pressable
                  key={key}
                  accessibilityRole="button"
                  onPress={() => submit(t(`chat.quick.${key}`))}
                  style={({ pressed }) => [styles.quickChip, { backgroundColor: theme.surfaceAlt, opacity: pressed ? 0.7 : 1 }]}>
                  <Txt variant="label" style={{ color: theme.scheme === 'dark' ? theme.primary : theme.primaryPressed }}>
                    {t(`chat.quick.${key}`)}
                  </Txt>
                </Pressable>
              ))}
            </ScrollView>
            <View style={styles.inputRow}>
              <TextInput
                value={text}
                onChangeText={setText}
                placeholder={t('chat.placeholder')}
                placeholderTextColor={theme.muted}
                accessibilityLabel={t('chat.placeholder')}
                multiline
                maxLength={500}
                selectionColor={theme.primary}
                cursorColor={theme.primary}
                maxFontSizeMultiplier={1.5}
                style={[styles.input, { color: theme.text, backgroundColor: theme.background }]}
              />
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={t('chat.send')}
                accessibilityState={{ disabled: !text.trim() || send.isPending }}
                disabled={!text.trim() || send.isPending}
                onPress={() => submit(text)}
                style={({ pressed }) => [
                  styles.send,
                  { backgroundColor: text.trim() ? theme.primary : theme.disabled, opacity: pressed ? 0.8 : 1 },
                ]}>
                {send.isPending ? (
                  <ActivityIndicator color={theme.onPrimary} size="small" />
                ) : (
                  <Send size={20} color={text.trim() ? theme.onPrimary : theme.onDisabled} strokeWidth={2.4} />
                )}
              </Pressable>
            </View>
          </>
        ) : (
          <Notice tone="info">{chatOn ? t('errors.chat_closed') : t('control.chatOff')}</Notice>
        )}
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.sm,
    paddingHorizontal: space.sm,
    paddingBottom: space.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  bubbleRow: { flexDirection: 'row' },
  lostItem: { flexDirection: 'row', alignItems: 'center', gap: space.xs, paddingHorizontal: space.md, paddingVertical: space.xs },
  bubble: { maxWidth: '80%', borderRadius: 18, paddingHorizontal: 14, paddingVertical: 10, gap: 2 },
  composer: { borderTopWidth: StyleSheet.hairlineWidth, paddingTop: space.xs, paddingHorizontal: space.md, gap: space.xs },
  quick: { gap: space.xs, paddingVertical: 2 },
  quickChip: { borderRadius: radius.pill, paddingHorizontal: 14, paddingVertical: 8 },
  inputRow: { flexDirection: 'row', alignItems: 'flex-end', gap: space.xs },
  input: { flex: 1, minHeight: 48, maxHeight: 120, borderRadius: 24, paddingHorizontal: space.md, paddingTop: 13, paddingBottom: 13, fontFamily: fonts.medium, fontSize: 16 },
  send: { width: 48, height: 48, borderRadius: 24, alignItems: 'center', justifyContent: 'center' },
});
