import { router, useFocusEffect, useLocalSearchParams } from "expo-router";
import { useCallback, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  ActivityIndicator,
  FlatList,
  Image,
  KeyboardAvoidingView,
  Linking,
  Platform,
  Pressable,
  StyleSheet,
  TextInput,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { ErrorState } from "@/components/ErrorState";
import {
  ChevronLeft,
  Lock,
  MessagesSquare,
  Paperclip,
  Send,
  Star,
} from "@/components/icons";
import { showToast } from "@/components/Toast";
import {
  Button,
  EmptyState,
  IconButton,
  IconTile,
  Skeleton,
  StatusPill,
  Txt,
} from "@/components/ui";
import { useAppConfig } from "@/hooks/useDriver";
import {
  useRateReport,
  useReport,
  useReportMessages,
  useSendReportMessage,
} from "@/hooks/useReports";
import { useRide } from "@/hooks/useRides";
import { apiErrorMessage } from "@/i18n";
import { ApiError } from "@/lib/api";
import { confirmHaptic, selectionHaptic } from "@/lib/feedback";
import { isUrgentCategory } from "@/lib/reports";
import {
  canRate,
  canReply,
  conversationState,
  CSAT_COMMENT_MAX,
  MESSAGE_MAX,
  messageProblem,
  responsePromise,
} from "@/lib/support";
import type { Report, ReportMessage } from "@/lib/types";
import { fonts, radius, space, useTheme } from "@/theme";

import {
  CATEGORY_ICONS,
  ReportStatusPill,
  RideContextCard,
  UrgentNote,
} from "./components";
import {
  PhotoStrip,
  uploadErrorMessage,
  usePhotoAttachments,
} from "./PhotoAttachments";

function leave() {
  if (router.canGoBack()) router.back();
  else router.replace("/reports");
}

/**
 * One conversation with the team (doc 13): the thread (the first message is what the user reported), a reply
 * box with up to 4 photos while it can take replies, and the 1–5 rating once it is closed.
 */
export function ReportDetailScreen() {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const { id } = useLocalSearchParams<{ id: string }>();
  const report = useReport(id);
  const data = report.data;
  const messages = useReportMessages(id, data);
  const ride = useRide(data?.ride_id ?? undefined);
  const { config } = useAppConfig();
  const listRef = useRef<FlatList<ReportMessage>>(null);
  const count = useRef(0);

  // Back on screen (from the notification, another app): read the thread again.
  const refetchReport = report.refetch;
  const refetchMessages = messages.refetch;
  useFocusEffect(
    useCallback(() => {
      void refetchReport();
      void refetchMessages();
    }, [refetchReport, refetchMessages]),
  );

  const header = (
    <View
      style={[
        styles.header,
        {
          paddingTop: insets.top + space.xs,
          backgroundColor: theme.surface,
          borderBottomColor: theme.border,
        },
      ]}
    >
      <IconButton
        icon={ChevronLeft}
        label={t("common.back")}
        tone="plain"
        onPress={leave}
      />
      {data ? (
        <IconTile
          icon={CATEGORY_ICONS[data.category]}
          tone={isUrgentCategory(data.category) ? "danger" : "primary"}
          size={40}
        />
      ) : null}
      <View style={{ flex: 1 }}>
        <Txt variant="subtitle" numberOfLines={1} accessibilityRole="header">
          {data
            ? t(`report.category.${data.category}.title`)
            : t("reports.detailTitle")}
        </Txt>
        {data ? <HeaderStatus report={data} /> : null}
      </View>
    </View>
  );

  if (!data) {
    return (
      <View style={{ flex: 1, backgroundColor: theme.background }}>
        {header}
        <View style={{ padding: space.lg, gap: space.sm }}>
          {report.isError ? (
            <ErrorState error={report.error} onRetry={() => report.refetch()} />
          ) : (
            <>
              <Skeleton height={72} radius={radius.card} />
              <Skeleton height={90} width="70%" radius={radius.card} />
              <Skeleton height={60} width="60%" radius={radius.card} style={{ alignSelf: "flex-end" }} />
            </>
          )}
        </View>
      </View>
    );
  }

  const urgent = isUrgentCategory(data.category);
  const state = conversationState(data);
  const replyable = canReply(data) && !messages.data?.legacy;
  const items = messages.data?.messages ?? [];

  return (
    <KeyboardAvoidingView
      style={{ flex: 1, backgroundColor: theme.background }}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      {header}
      <FlatList
        ref={listRef}
        data={items}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => <MessageBubble message={item} />}
        contentContainerStyle={{ padding: space.md, gap: space.sm, flexGrow: 1 }}
        keyboardShouldPersistTaps="handled"
        onContentSizeChange={() => {
          // Jump to the newest message when one arrives (not on every re-render).
          if (items.length !== count.current) {
            count.current = items.length;
            listRef.current?.scrollToEnd({ animated: count.current > 0 });
          }
        }}
        ListHeaderComponent={
          <View style={{ gap: space.sm, marginBottom: space.xs }}>
            {data.ride_id && !ride.isError ? (
              <RideContextCard ride={ride.data} />
            ) : null}
            {urgent && state !== "closed" ? <UrgentNote compact /> : null}
            {state === "waiting" ? (
              <Txt variant="caption" color="muted" align="center">
                {responsePromise(config, i18n.language)}
              </Txt>
            ) : null}
          </View>
        }
        ListEmptyComponent={
          messages.isPending ? (
            <ActivityIndicator color={theme.primary} style={{ marginTop: space.xl }} />
          ) : messages.isError ? (
            <ErrorState error={messages.error} onRetry={() => messages.refetch()} />
          ) : (
            <EmptyState icon={MessagesSquare} title={t("support.thread.empty")} />
          )
        }
        ListFooterComponent={
          state === "closed" || !replyable ? (
            <View style={{ gap: space.sm, marginTop: space.sm }}>
              {canRate(data) ? <CsatCard report={data} /> : null}
              {data.csat ? (
                <Txt variant="caption" color="muted" align="center">
                  {t("support.csat.given", { score: data.csat })}
                </Txt>
              ) : null}
            </View>
          ) : undefined
        }
      />
      {replyable ? (
        <Composer report={data} />
      ) : !canReply(data) ? (
        <ClosedBar report={data} />
      ) : null}
    </KeyboardAvoidingView>
  );
}

/** "Te respondimos" / "Esperando respuesta del equipo" or the closed status. */
function HeaderStatus({ report }: { report: Report }) {
  const { t } = useTranslation();
  const state = conversationState(report);
  return (
    <View style={styles.pills}>
      {state === "closed" ? (
        <ReportStatusPill status={report.status} />
      ) : (
        <StatusPill
          label={t(`reports.state.${state}`)}
          tone={state === "replied" ? "primary" : "info"}
          dot
        />
      )}
      {report.priority === "urgent" && state !== "closed" ? (
        <StatusPill label={t("reports.priority")} tone="danger" />
      ) : null}
    </View>
  );
}

function MessageBubble({ message }: { message: ReportMessage }) {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const time = new Date(message.created_at).toLocaleString(i18n.language, {
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
  });

  if (message.author_kind === "system") {
    return (
      <View style={[styles.system, { backgroundColor: theme.surfaceAlt }]}>
        <Txt variant="caption" color="muted" align="center">
          {message.body}
        </Txt>
        <Txt variant="micro" color="muted" align="center">
          {time}
        </Txt>
      </View>
    );
  }

  const mine = message.mine;
  const author = mine
    ? t("support.thread.you")
    : message.author_name
      ? t("support.thread.staffNamed", { name: message.author_name })
      : t("support.thread.staff");
  const fg = mine ? theme.onPrimary : theme.text;
  return (
    <View
      style={{ alignItems: mine ? "flex-end" : "flex-start" }}
      accessible
      accessibilityLabel={`${author}, ${time}: ${message.body}${
        message.attachments.length
          ? `. ${t("support.thread.photos", { count: message.attachments.length })}`
          : ""
      }`}
    >
      {!mine ? (
        <Txt variant="micro" color="muted" style={{ marginBottom: 2, marginLeft: space.xs }}>
          {author}
        </Txt>
      ) : null}
      <View
        style={[
          styles.bubble,
          mine
            ? { backgroundColor: theme.primary, borderBottomRightRadius: 6 }
            : { backgroundColor: theme.surface, borderBottomLeftRadius: 6 },
        ]}
      >
        {message.body ? <Txt style={{ color: fg }}>{message.body}</Txt> : null}
        {message.attachments.length ? (
          <View style={styles.attachments}>
            {message.attachments.map((file, index) => (
              <Pressable
                key={file.key}
                accessibilityRole="imagebutton"
                accessibilityLabel={t("support.thread.openPhoto", { n: index + 1 })}
                onPress={() => void Linking.openURL(file.url).catch(() => undefined)}
              >
                <Image
                  source={{ uri: file.url }}
                  style={[styles.attachment, { backgroundColor: theme.surfaceAlt }]}
                  accessibilityIgnoresInvertColors
                />
              </Pressable>
            ))}
          </View>
        ) : null}
        <Txt
          variant="micro"
          style={{ color: mine ? theme.onPrimary : theme.muted, opacity: 0.75, alignSelf: "flex-end" }}
        >
          {time}
        </Txt>
      </View>
    </View>
  );
}

/** Reply box: text, up to 4 photos and send. */
function Composer({ report }: { report: Report }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const send = useSendReportMessage(report.id);
  const reportQuery = useReport(report.id);
  const photos = usePhotoAttachments();
  const [text, setText] = useState("");
  const [uploading, setUploading] = useState(false);
  const busy = uploading || send.isPending;
  const problem = messageProblem(text);
  const ready = !problem && !busy;

  const submit = async () => {
    if (!ready) return;
    selectionHaptic();
    let attachments: string[] = [];
    if (photos.photos.length) {
      setUploading(true);
      try {
        attachments = await photos.upload();
      } catch (error) {
        showToast(uploadErrorMessage(error, t), "danger");
        return;
      } finally {
        setUploading(false);
      }
    }
    send.mutate(
      { body: text.trim(), ...(attachments.length ? { attachments } : {}) },
      {
        onSuccess: () => {
          setText("");
          photos.clear();
        },
        onError: (error) => {
          showToast(apiErrorMessage(error), "danger");
          if (error instanceof ApiError && error.code === "report_closed")
            void reportQuery.refetch();
        },
      },
    );
  };

  return (
    <View
      style={[
        styles.composer,
        {
          backgroundColor: theme.surface,
          borderTopColor: theme.border,
          paddingBottom: Math.max(insets.bottom, space.sm),
        },
      ]}
    >
      {photos.sheet}
      <PhotoStrip photos={photos.photos} onRemove={photos.remove} disabled={busy} />
      <View style={styles.inputRow}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={t("support.photos.add")}
          accessibilityState={{ disabled: busy || photos.full }}
          disabled={busy}
          onPress={photos.open}
          style={({ pressed }) => [
            styles.round,
            { backgroundColor: theme.background, opacity: pressed || photos.full ? 0.6 : 1 },
          ]}
        >
          <Paperclip size={20} color={theme.text} strokeWidth={2.2} />
        </Pressable>
        <TextInput
          value={text}
          onChangeText={setText}
          placeholder={t("support.thread.placeholder")}
          placeholderTextColor={theme.muted}
          accessibilityLabel={t("support.thread.placeholder")}
          multiline
          maxLength={MESSAGE_MAX}
          selectionColor={theme.primary}
          cursorColor={theme.primary}
          maxFontSizeMultiplier={1.5}
          style={[styles.input, { color: theme.text, backgroundColor: theme.background }]}
        />
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={t("support.thread.send")}
          accessibilityState={{ disabled: !ready, busy }}
          disabled={!ready}
          onPress={() => void submit()}
          style={({ pressed }) => [
            styles.round,
            { backgroundColor: ready ? theme.primary : theme.disabled, opacity: pressed ? 0.8 : 1 },
          ]}
        >
          {busy ? (
            <ActivityIndicator color={theme.onPrimary} size="small" />
          ) : (
            <Send size={20} color={ready ? theme.onPrimary : theme.onDisabled} strokeWidth={2.4} />
          )}
        </Pressable>
      </View>
    </View>
  );
}

/** "Esta conversación está cerrada" and a way to start a new one. */
function ClosedBar({ report }: { report: Report }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  return (
    <View
      style={[
        styles.composer,
        {
          backgroundColor: theme.surface,
          borderTopColor: theme.border,
          paddingBottom: Math.max(insets.bottom, space.sm),
        },
      ]}
    >
      <View style={styles.closedRow}>
        <Lock size={18} color={theme.muted} strokeWidth={2.2} />
        <Txt variant="caption" color="muted" style={{ flex: 1 }}>
          {t("support.thread.closed")}
        </Txt>
      </View>
      <Button
        title={t("support.thread.newConversation")}
        variant="secondary"
        size="sm"
        onPress={() =>
          router.push({
            pathname: "/report",
            params: report.ride_id ? { ride_id: report.ride_id } : {},
          })
        }
      />
    </View>
  );
}

/** "¿Cómo te atendimos?": 1 to 5 stars and an optional comment. */
function CsatCard({ report }: { report: Report }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const rate = useRateReport(report.id);
  const [score, setScore] = useState(0);
  const [comment, setComment] = useState("");

  const submit = () => {
    if (!score) return;
    const text = comment.trim();
    rate.mutate(
      { score, ...(text ? { comment: text.slice(0, CSAT_COMMENT_MAX) } : {}) },
      {
        onSuccess: () => {
          confirmHaptic();
          showToast(t("support.csat.thanks"), "success");
        },
        onError: (error) => showToast(apiErrorMessage(error), "danger"),
      },
    );
  };

  return (
    <View style={[styles.csat, { backgroundColor: theme.surface }]}>
      <Txt variant="subtitle" align="center">
        {t("support.csat.title")}
      </Txt>
      <Txt variant="caption" color="muted" align="center">
        {t("support.csat.body")}
      </Txt>
      <View style={styles.stars} accessibilityRole="radiogroup">
        {[1, 2, 3, 4, 5].map((n) => (
          <Pressable
            key={n}
            accessibilityRole="radio"
            accessibilityLabel={t("support.csat.star", { count: n })}
            accessibilityState={{ checked: score === n }}
            hitSlop={6}
            onPress={() => {
              selectionHaptic();
              setScore(n);
            }}
          >
            <Star
              size={36}
              color={theme.accent}
              fill={n <= score ? theme.accent : "transparent"}
              strokeWidth={2}
            />
          </Pressable>
        ))}
      </View>
      {score ? (
        <>
          <TextInput
            value={comment}
            onChangeText={setComment}
            placeholder={t("support.csat.comment")}
            placeholderTextColor={theme.muted}
            accessibilityLabel={t("support.csat.comment")}
            multiline
            maxLength={CSAT_COMMENT_MAX}
            selectionColor={theme.primary}
            cursorColor={theme.primary}
            maxFontSizeMultiplier={1.5}
            textAlignVertical="top"
            style={[
              styles.comment,
              { color: theme.text, backgroundColor: theme.background, borderColor: theme.border },
            ]}
          />
          <Button title={t("support.csat.submit")} loading={rate.isPending} onPress={submit} />
        </>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  header: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.sm,
    paddingHorizontal: space.sm,
    paddingBottom: space.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  pills: { flexDirection: "row", flexWrap: "wrap", gap: 6, marginTop: 2 },
  system: {
    alignSelf: "center",
    maxWidth: "90%",
    borderRadius: radius.tile,
    paddingHorizontal: space.md,
    paddingVertical: space.xs,
    gap: 2,
  },
  bubble: {
    maxWidth: "84%",
    borderRadius: 18,
    paddingHorizontal: 14,
    paddingVertical: 10,
    gap: 4,
  },
  attachments: { flexDirection: "row", flexWrap: "wrap", gap: 6, marginTop: 2 },
  attachment: { width: 96, height: 96, borderRadius: radius.field },
  composer: {
    borderTopWidth: StyleSheet.hairlineWidth,
    paddingTop: space.xs,
    paddingHorizontal: space.md,
    gap: space.xs,
  },
  inputRow: { flexDirection: "row", alignItems: "flex-end", gap: space.xs },
  input: {
    flex: 1,
    minHeight: 48,
    maxHeight: 140,
    borderRadius: 24,
    paddingHorizontal: space.md,
    paddingTop: 13,
    paddingBottom: 13,
    fontFamily: fonts.medium,
    fontSize: 16,
  },
  round: {
    width: 48,
    height: 48,
    borderRadius: 24,
    alignItems: "center",
    justifyContent: "center",
  },
  closedRow: { flexDirection: "row", alignItems: "center", gap: space.xs },
  csat: { borderRadius: radius.card, padding: space.md, gap: space.sm },
  stars: { flexDirection: "row", justifyContent: "center", gap: space.xs },
  comment: {
    minHeight: 88,
    borderWidth: 1.5,
    borderRadius: radius.field,
    paddingHorizontal: 14,
    paddingTop: 12,
    paddingBottom: 12,
    fontFamily: fonts.medium,
    fontSize: 15,
  },
});
