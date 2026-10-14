import { router, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { StyleSheet, TextInput, View } from "react-native";

import {
  CircleCheck,
  Hash,
  MessagesSquare,
  Paperclip,
  Receipt,
  TriangleAlert,
} from "@/components/icons";
import {
  Button,
  Card,
  ErrorText,
  Field,
  IconTile,
  Notice,
  Screen,
  StatusPill,
  Txt,
} from "@/components/ui";
import {
  PhotoStrip,
  uploadErrorMessage,
  usePhotoAttachments,
} from "@/features/reports/PhotoAttachments";
import { useDisputeTopUp, useTopUpInfo, useTopUps } from "@/hooks/useWallet";
import { apiErrorMessage } from "@/i18n";
import { confirmHaptic } from "@/lib/feedback";
import { formatAmount } from "@/lib/money";
import type { TopUp } from "@/lib/types";
import {
  DISPUTE_MAX_PHOTOS,
  DISPUTE_NOTE_MAX,
  type DisputeError,
  disputeError,
  isValidTransactionId,
  normalizeTransactionId,
  parseAmountInput,
  sanitizeAmountInput,
  TRANSACTION_ID_MAX,
  topUpAmountError,
} from "@/lib/wallet";
import { fonts, radius, space, useTheme } from "@/theme";

import { BinanceDownNotice } from "./BinanceDownNotice";
import { FlowHeader, leaveFlow } from "./components";
import { useWalletFormat } from "./format";

type FormError = DisputeError & { message: string };

const openConversation = (reportId: string) =>
  router.replace({ pathname: "/reports/[id]", params: { id: reportId } });

/**
 * "No me llegó mi recarga" (doc 17): the Binance transaction id, a screenshot of the payment and an optional
 * note. It opens an urgent support ticket the driver follows in Ayuda → Mis reportes. Opened for a pending
 * or rejected top-up (`top_up_id`) or without one: then the amount is asked too and the top-up is created
 * first, as "Ya pagué" would.
 */
export function DisputeScreen() {
  const { t } = useTranslation();
  const theme = useTheme();
  const params = useLocalSearchParams<{ top_up_id?: string }>();
  const info = useTopUpInfo();
  const topUps = useTopUps();
  const dispute = useDisputeTopUp();
  const photos = usePhotoAttachments(DISPUTE_MAX_PHOTOS);
  const format = useWalletFormat();

  // A top-up created by a previous attempt whose claim failed: retries reuse it.
  const [created, setCreated] = useState<TopUp | null>(null);
  const topUpId = params.top_up_id || created?.id || null;
  const topUp =
    created ??
    topUps.data?.pages
      .flatMap((page) => page.items)
      .find((item) => item.id === params.top_up_id) ??
    null;

  const [amount, setAmount] = useState("");
  const [transactionId, setTransactionId] = useState("");
  const [note, setNote] = useState("");
  const [touched, setTouched] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<FormError | null>(null);
  const [sent, setSent] = useState<TopUp | null>(null);

  const min = formatAmount(info.data?.min_amount);
  const needsAmount = !topUpId;
  const amountProblem = needsAmount
    ? topUpAmountError(amount, info.data?.min_amount)
    : null;
  const idProblem = !isValidTransactionId(transactionId);
  const photoProblem = !photos.photos.length;
  const busy = uploading || dispute.isPending;

  const submit = async () => {
    setTouched(true);
    if (amountProblem || idProblem || photoProblem || busy) return;
    setError(null);
    let attachments: string[];
    setUploading(true);
    try {
      attachments = await photos.upload();
    } catch (e) {
      setError({ kind: "attachment", message: uploadErrorMessage(e, t) });
      return;
    } finally {
      setUploading(false);
    }
    const trimmed = note.trim();
    dispute.mutate(
      {
        topUpId,
        ...(needsAmount
          ? { amount: (parseAmountInput(amount) as number).toFixed(2) }
          : {}),
        transaction_id: normalizeTransactionId(transactionId),
        attachments,
        ...(trimmed ? { note: trimmed.slice(0, DISPUTE_NOTE_MAX) } : {}),
        onCreated: setCreated,
      },
      {
        onSuccess: (result) => {
          confirmHaptic();
          setSent(result);
        },
        onError: (e) => setError({ ...disputeError(e), message: apiErrorMessage(e) }),
      },
    );
  };

  if (sent) {
    const reportId = sent.dispute_report_id ?? null;
    return (
      <Screen
        footer={
          <>
            {reportId ? (
              <Button
                title={t("topUp.dispute.sent.open")}
                icon={MessagesSquare}
                onPress={() => openConversation(reportId)}
              />
            ) : null}
            <Button
              title={t("topUp.sent.done")}
              variant={reportId ? "ghost" : "primary"}
              onPress={leaveFlow}
            />
          </>
        }
      >
        <View style={styles.sent}>
          <View
            style={[styles.sentRing, { backgroundColor: theme.successSoft }]}
          >
            <CircleCheck size={48} color={theme.success} strokeWidth={2} />
          </View>
          <Txt variant="title" align="center" accessibilityRole="header">
            {t("topUp.dispute.sent.title")}
          </Txt>
          <Txt color="muted" align="center">
            {t("topUp.dispute.sent.body")}
          </Txt>
        </View>
      </Screen>
    );
  }

  return (
    <Screen
      header={
        <FlowHeader
          title={t("topUp.dispute.title")}
          subtitle={t("topUp.dispute.subtitle")}
        />
      }
      footer={
        <Button
          title={t("topUp.dispute.submit")}
          loading={busy}
          disabled={touched && (!!amountProblem || idProblem || photoProblem)}
          onPress={() => void submit()}
        />
      }
    >
      {photos.sheet}
      <View style={{ gap: space.md }}>
        <BinanceDownNotice info={info.data} />

        {topUp ? (
          <Card style={styles.topUp}>
            <IconTile icon={Receipt} tone="warning" size={40} />
            <View style={{ flex: 1, gap: 2 }}>
              <Txt variant="bodyStrong" tabular>
                {formatAmount(topUp.amount)} USDT
              </Txt>
              <Txt variant="caption" color="muted">
                {format.shortDate(topUp.created_at)}
              </Txt>
            </View>
            <StatusPill
              label={t(`topUp.status.${topUp.status}`)}
              tone={topUp.status === "rejected" ? "danger" : "warning"}
            />
          </Card>
        ) : null}

        {needsAmount ? (
          <Field
            label={t("topUp.notify.amount")}
            value={amount}
            onChangeText={(text) => setAmount(sanitizeAmountInput(text))}
            placeholder={min}
            keyboardType="decimal-pad"
            error={
              touched && amountProblem
                ? amountProblem === "below_minimum"
                  ? t("topUp.notify.belowMin", { amount: min })
                  : t("topUp.notify.amountInvalid")
                : undefined
            }
            hint={t("topUp.notify.amountHint", { amount: min })}
          />
        ) : null}

        <Field
          label={t("topUp.dispute.transactionId")}
          icon={Hash}
          value={transactionId}
          onChangeText={(text) => setTransactionId(normalizeTransactionId(text))}
          placeholder={t("topUp.notify.referencePlaceholder")}
          autoCapitalize="none"
          autoCorrect={false}
          maxLength={TRANSACTION_ID_MAX}
          error={touched && idProblem ? t("topUp.dispute.transactionIdInvalid") : undefined}
          hint={t("topUp.dispute.transactionIdHint")}
        />

        <View style={{ gap: space.xs }}>
          <Txt variant="label" color="muted">
            {t("topUp.dispute.screenshot", { max: DISPUTE_MAX_PHOTOS })}
          </Txt>
          <PhotoStrip photos={photos.photos} onRemove={photos.remove} disabled={busy} />
          {!photos.full ? (
            <Button
              title={t("support.photos.add")}
              variant="secondary"
              size="sm"
              icon={Paperclip}
              style={{ alignSelf: "flex-start" }}
              onPress={photos.open}
            />
          ) : null}
          <Txt
            variant="caption"
            style={{ color: touched && photoProblem ? theme.danger : theme.muted }}
          >
            {touched && photoProblem
              ? t("topUp.dispute.screenshotRequired")
              : t("topUp.dispute.screenshotHint")}
          </Txt>
        </View>

        <View>
          <Txt variant="label" color="muted" style={{ marginBottom: 6 }}>
            {t("topUp.dispute.note")}
          </Txt>
          <TextInput
            accessibilityLabel={t("topUp.dispute.note")}
            value={note}
            onChangeText={setNote}
            placeholder={t("topUp.dispute.notePlaceholder")}
            placeholderTextColor={theme.muted}
            selectionColor={theme.primary}
            cursorColor={theme.primary}
            multiline
            maxLength={DISPUTE_NOTE_MAX}
            maxFontSizeMultiplier={1.6}
            textAlignVertical="top"
            style={[
              styles.textarea,
              {
                color: theme.text,
                backgroundColor: theme.surface,
                borderColor: theme.border,
              },
            ]}
          />
        </View>

        {error ? <DisputeErrorNotice error={error} /> : null}
      </View>
    </Screen>
  );
}

function DisputeErrorNotice({ error }: { error: FormError }) {
  const { t } = useTranslation();
  if (error.kind === "open") {
    const reportId = error.reportId;
    return (
      <Notice tone="info" title={t("topUp.dispute.openTitle")}>
        <Txt variant="caption" style={{ fontSize: 14, lineHeight: 20 }}>
          {t("errors.top_up_dispute_open")}
        </Txt>
        {reportId ? (
          <Button
            title={t("topUp.dispute.sent.open")}
            variant="secondary"
            size="sm"
            style={{ alignSelf: "flex-start" }}
            onPress={() => openConversation(reportId)}
          />
        ) : null}
      </Notice>
    );
  }
  if (error.kind === "not_allowed" || error.kind === "not_found") {
    return (
      <Notice tone="warning" icon={TriangleAlert}>
        <Txt variant="caption" style={{ fontSize: 14, lineHeight: 20 }}>
          {error.message}
        </Txt>
        <Button
          title={t("topUp.sent.done")}
          variant="secondary"
          size="sm"
          style={{ alignSelf: "flex-start" }}
          onPress={leaveFlow}
        />
      </Notice>
    );
  }
  return <ErrorText>{error.message}</ErrorText>;
}

const styles = StyleSheet.create({
  topUp: { flexDirection: "row", alignItems: "center", gap: space.sm },
  textarea: {
    minHeight: 96,
    maxHeight: 200,
    borderWidth: 1.5,
    borderRadius: radius.field,
    paddingHorizontal: 14,
    paddingTop: 12,
    paddingBottom: 12,
    fontFamily: fonts.medium,
    fontSize: 16,
    lineHeight: 22,
  },
  sent: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: space.sm,
    paddingVertical: space.xxl,
  },
  sentRing: {
    width: 112,
    height: 112,
    borderRadius: 56,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: space.sm,
  },
});
