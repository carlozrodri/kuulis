import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Pressable, StyleSheet, TextInput, View } from "react-native";

import {
  CircleCheck,
  CircleX,
  Info,
  MessageCircle,
  TriangleAlert,
  UserSearch,
} from "@/components/icons";
import {
  Button,
  Card,
  Chip,
  EmptyState,
  ErrorText,
  Field,
  Notice,
  ProgressSteps,
  Screen,
  Skeleton,
  Txt,
} from "@/components/ui";
import { Avatar } from "@/features/ride/components";
import { useDriverProfile } from "@/hooks/useDriver";
import {
  useFindRecipient,
  useTransfer,
  useWallet,
  walletKeys,
} from "@/hooks/useWallet";
import { apiErrorMessage } from "@/i18n";
import { ApiError } from "@/lib/api";
import { confirmHaptic, heavyHaptic } from "@/lib/feedback";
import { formatAmount } from "@/lib/money";
import type { Recipient, TransferAllowance } from "@/lib/types";
import {
  maxTransfer,
  parseAmountInput,
  parseRecipientQuery,
  sanitizeAmountInput,
  toCents,
  transferAmountError,
} from "@/lib/wallet";
import { useAuth } from "@/providers/AuthProvider";
import { fonts, radius, space, useTheme } from "@/theme";

import { goToTopUp } from "./SubscriptionCard";
import { FlowHeader, leaveFlow, SummaryRow } from "./components";

type Step = "recipient" | "amount" | "confirm" | "done";
const STEPS: Step[] = ["recipient", "amount", "confirm"];
const NOTE_MAX = 140;

/**
 * Transferir: find another driver by email or phone, choose the amount (within the balance and the monthly
 * limit, which counts only what is sent), confirm and send. Transfers are instant and final.
 */
export function TransferScreen() {
  const { t } = useTranslation();
  const theme = useTheme();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const profile = useDriverProfile();
  const wallet = useWallet();
  const find = useFindRecipient();
  const transfer = useTransfer();

  const [step, setStep] = useState<Step>("recipient");
  const [query, setQuery] = useState("");
  const [queryError, setQueryError] = useState<string>();
  const [recipient, setRecipient] = useState<Recipient | null>(null);
  const [amount, setAmount] = useState("");
  const [amountError, setAmountError] = useState<string>();
  const [note, setNote] = useState("");
  const [submitError, setSubmitError] = useState<string>();

  const balance = wallet.data?.balance;
  const allowance = wallet.data?.transfer ?? null;
  const max = maxTransfer({ balance, available: allowance?.available });
  const value = parseAmountInput(amount);

  const amountMessage = (code: ReturnType<typeof transferAmountError>) => {
    if (code === "invalid") return t("transfer.amountInvalid");
    if (code === "insufficient_balance")
      return t("transfer.amountOverBalance", {
        balance: formatAmount(balance),
      });
    if (code === "transfer_limit_exceeded")
      return t("transfer.amountOverLimit", {
        available: formatAmount(allowance?.available),
      });
    return undefined;
  };

  const search = () => {
    const parsed = parseRecipientQuery(query);
    if (!parsed) {
      setQueryError(t("transfer.queryInvalid"));
      return;
    }
    const ownEmail = user?.email?.trim().toLowerCase();
    if (
      (parsed.type === "email" && parsed.value === ownEmail) ||
      (parsed.type === "phone" && parsed.value === profile.data?.phone)
    ) {
      setQueryError(t("errors.transfer_to_self"));
      return;
    }
    setQueryError(undefined);
    find.mutate(parsed.value, {
      onSuccess: (found) => {
        if (found.user_id === user?.id) {
          setQueryError(t("errors.transfer_to_self"));
          return;
        }
        setRecipient(found);
        setStep("amount");
      },
      onError: (e) => setQueryError(apiErrorMessage(e)),
    });
  };

  const review = () => {
    const problem = transferAmountError(amount, {
      balance,
      available: allowance?.available,
    });
    setAmountError(amountMessage(problem));
    if (!problem) {
      setSubmitError(undefined);
      setStep("confirm");
    }
  };

  const send = () => {
    if (!recipient || value === null) return;
    heavyHaptic();
    setSubmitError(undefined);
    transfer.mutate(
      {
        to_user_id: recipient.user_id,
        amount: value.toFixed(2),
        ...(note.trim() ? { note: note.trim() } : {}),
      },
      {
        onSuccess: () => {
          confirmHaptic();
          setStep("done");
        },
        onError: (e) => {
          const code = e instanceof ApiError ? e.code : null;
          if (code === "recipient_not_found" || code === "transfer_to_self") {
            setRecipient(null);
            setQueryError(apiErrorMessage(e));
            setStep("recipient");
          } else if (
            code === "insufficient_balance" ||
            code === "transfer_limit_exceeded"
          ) {
            if (code === "transfer_limit_exceeded" && e instanceof ApiError) {
              // The error carries the up-to-date allowance: use it right away.
              const details = e.details as TransferAllowance | undefined;
              if (details?.available !== undefined)
                queryClient.setQueryData(
                  walletKeys.me,
                  (current: typeof wallet.data) =>
                    current ? { ...current, transfer: details } : current,
                );
            }
            setAmountError(apiErrorMessage(e));
            setStep("amount");
          } else {
            setSubmitError(apiErrorMessage(e));
          }
        },
      },
    );
  };

  const back = () => {
    if (step === "amount") setStep("recipient");
    else if (step === "confirm") setStep("amount");
    else leaveFlow();
  };

  const header = (
    <View>
      <FlowHeader
        title={
          step === "recipient"
            ? t("transfer.title")
            : step === "amount"
              ? t("transfer.amountTitle")
              : t("transfer.confirmTitle")
        }
        subtitle={step === "recipient" ? t("transfer.subtitle") : null}
        step={
          step === "done"
            ? null
            : t("driver.step.counter", {
                current: STEPS.indexOf(step) + 1,
                total: STEPS.length,
              })
        }
        onBack={back}
      />
      {step !== "done" ? (
        <View style={{ marginTop: -space.xs, marginBottom: space.md }}>
          <ProgressSteps
            total={STEPS.length}
            current={STEPS.indexOf(step) + 1}
          />
        </View>
      ) : null}
    </View>
  );

  if (wallet.isPending || wallet.isError) {
    return (
      <Screen header={<FlowHeader title={t("transfer.title")} />}>
        {wallet.isPending ? (
          <View style={{ gap: space.md }}>
            <Skeleton height={110} radius={radius.card} />
            <Skeleton height={52} />
          </View>
        ) : (
          <>
            <EmptyState
              icon={CircleX}
              title={t("common.error")}
              body={apiErrorMessage(wallet.error)}
            />
            <Button
              title={t("common.retry")}
              variant="secondary"
              onPress={() => void wallet.refetch()}
            />
          </>
        )}
      </Screen>
    );
  }

  if (step === "done" && recipient && value !== null) {
    return (
      <Screen footer={<Button title={t("common.done")} onPress={leaveFlow} />}>
        <View style={styles.done}>
          <View
            style={[styles.doneRing, { backgroundColor: theme.successSoft }]}
          >
            <CircleCheck size={48} color={theme.success} strokeWidth={2} />
          </View>
          <Txt variant="title" align="center" accessibilityRole="header">
            {t("transfer.doneTitle")}
          </Txt>
          <Txt color="muted" align="center">
            {t("transfer.doneBody", {
              amount: formatAmount(value),
              name: recipient.name,
            })}
          </Txt>
        </View>
      </Screen>
    );
  }

  // ── Step 1: recipient ──
  if (step === "recipient" || !recipient) {
    const noBalance = (toCents(balance) ?? 0) <= 0;
    const limitReached =
      !noBalance && allowance && (toCents(allowance.available) ?? 0) <= 0;
    return (
      <Screen
        header={header}
        footer={
          <Button
            title={t("transfer.search")}
            icon={UserSearch}
            loading={find.isPending}
            disabled={!query.trim() || max <= 0}
            onPress={search}
          />
        }
      >
        <AllowanceCard balance={balance} allowance={allowance} max={max} />
        {noBalance ? (
          <Notice
            tone="warning"
            title={t("transfer.noBalanceTitle")}
            style={{ marginTop: space.md }}
          >
            <View style={{ gap: space.xs }}>
              <Txt variant="caption" style={{ fontSize: 14, lineHeight: 20 }}>
                {t("transfer.noBalance")}
              </Txt>
              <Button
                title={t("wallet.topUp")}
                variant="accent"
                size="sm"
                onPress={goToTopUp}
                style={{ alignSelf: "flex-start" }}
              />
            </View>
          </Notice>
        ) : limitReached ? (
          <Notice
            tone="warning"
            title={t("transfer.limitReachedTitle")}
            style={{ marginTop: space.md }}
          >
            {t("transfer.limitReached", {
              limit: formatAmount(allowance?.limit),
            })}
          </Notice>
        ) : null}
        <View style={{ marginTop: space.lg }}>
          <Field
            label={t("transfer.query")}
            icon={UserSearch}
            value={query}
            onChangeText={(text) => {
              setQuery(text);
              setQueryError(undefined);
            }}
            placeholder={t("transfer.queryPlaceholder")}
            autoCapitalize="none"
            autoCorrect={false}
            autoComplete="off"
            keyboardType="email-address"
            returnKeyType="search"
            onSubmitEditing={search}
            editable={max > 0}
            error={queryError}
            hint={t("transfer.queryHint")}
          />
        </View>
      </Screen>
    );
  }

  // ── Step 2: amount and note ──
  if (step === "amount") {
    return (
      <Screen
        header={header}
        footer={
          <Button
            title={t("common.continue")}
            disabled={!amount}
            onPress={review}
          />
        }
      >
        <RecipientCard
          recipient={recipient}
          query={query}
          onChange={() => setStep("recipient")}
        />
        <View
          style={[
            styles.amountBox,
            {
              backgroundColor: theme.surface,
              borderColor: amountError ? theme.danger : theme.border,
            },
          ]}
        >
          <Txt variant="label" color="muted">
            {t("transfer.amount")}
          </Txt>
          <View style={styles.amountRow}>
            <AmountInput
              value={amount}
              onChange={(text) => {
                setAmount(sanitizeAmountInput(text));
                setAmountError(undefined);
              }}
              label={t("transfer.amount")}
            />
            <Txt variant="subtitle" color="muted">
              USDT
            </Txt>
          </View>
          <View style={styles.chips}>
            {[1, 2, 5]
              .filter((n) => n < max)
              .map((n) => (
                <Chip
                  key={n}
                  label={formatAmount(n)}
                  selected={value === n}
                  onPress={() => {
                    setAmount(String(n));
                    setAmountError(undefined);
                  }}
                />
              ))}
            <Chip
              label={t("transfer.max", { amount: formatAmount(max) })}
              selected={
                value !== null &&
                Math.round(value * 100) === Math.round(max * 100)
              }
              onPress={() => {
                setAmount(max.toFixed(2));
                setAmountError(undefined);
              }}
            />
          </View>
        </View>
        {amountError ? (
          <Txt variant="caption" color="danger" style={{ marginTop: space.xs }}>
            {amountError}
          </Txt>
        ) : (
          <Txt variant="caption" color="muted" style={{ marginTop: space.xs }}>
            {allowance
              ? t("transfer.availableHint", {
                  max: formatAmount(max),
                  balance: formatAmount(balance),
                  available: formatAmount(allowance.available),
                })
              : t("transfer.balanceHint", { balance: formatAmount(balance) })}
          </Txt>
        )}
        <View style={{ marginTop: space.lg }}>
          <Field
            label={t("transfer.note")}
            icon={MessageCircle}
            value={note}
            onChangeText={(text) => setNote(text.slice(0, NOTE_MAX))}
            placeholder={t("transfer.notePlaceholder")}
            maxLength={NOTE_MAX}
            returnKeyType="done"
            hint={t("transfer.noteHint", { count: NOTE_MAX - note.length })}
          />
        </View>
      </Screen>
    );
  }

  // ── Step 3: confirm ──
  const after =
    Math.max(0, (toCents(balance) ?? 0) - Math.round((value ?? 0) * 100)) / 100;
  const leftThisMonth = allowance
    ? Math.max(
        0,
        (toCents(allowance.available) ?? 0) - Math.round((value ?? 0) * 100),
      ) / 100
    : null;
  return (
    <Screen
      header={header}
      footer={
        <>
          <Button
            title={t("transfer.send", { amount: formatAmount(value) })}
            size="lg"
            loading={transfer.isPending}
            onPress={send}
          />
          <Button
            title={t("common.back")}
            variant="ghost"
            disabled={transfer.isPending}
            onPress={() => setStep("amount")}
          />
        </>
      }
    >
      <Card elevated style={{ gap: space.md }}>
        <View style={{ alignItems: "center", gap: space.xs }}>
          <Avatar name={recipient.name} size={64} />
          <Txt color="muted">{t("transfer.youSend")}</Txt>
          <Txt style={[styles.bigAmount, { color: theme.text }]} tabular>
            {formatAmount(value)}{" "}
            <Txt style={[styles.bigCurrency, { color: theme.muted }]}>USDT</Txt>
          </Txt>
          <Txt variant="subtitle" align="center">
            {t("transfer.to", { name: recipient.name })}
          </Txt>
          {note.trim() ? (
            <Txt color="muted" align="center">
              “{note.trim()}”
            </Txt>
          ) : null}
        </View>
        <View style={[styles.hr, { backgroundColor: theme.divider }]} />
        <SummaryRow
          label={t("transfer.balanceAfter")}
          value={`${formatAmount(after)} USDT`}
        />
        {leftThisMonth !== null ? (
          <SummaryRow
            label={t("transfer.leftThisMonth")}
            value={`${formatAmount(leftThisMonth)} USDT`}
          />
        ) : null}
      </Card>
      <Notice
        tone="warning"
        icon={TriangleAlert}
        style={{ marginTop: space.md }}
      >
        {t("transfer.final")}
      </Notice>
      <ErrorText>{submitError}</ErrorText>
    </Screen>
  );
}

/** "Puedes enviar hasta 47.00 USDT" with the monthly limit bar. */
function AllowanceCard({
  balance,
  allowance,
  max,
}: {
  balance: string | undefined;
  allowance: TransferAllowance | null;
  max: number;
}) {
  const { t } = useTranslation();
  const theme = useTheme();
  const limit = toCents(allowance?.limit) ?? 0;
  const sent = toCents(allowance?.sent_this_month) ?? 0;
  const ratio = limit > 0 ? Math.min(1, sent / limit) : 0;
  return (
    <Card tone="tint" style={{ gap: space.sm }}>
      <View>
        <Txt variant="label" color="muted">
          {t("transfer.canSend")}
        </Txt>
        <Txt style={[styles.allowance, { color: theme.text }]} tabular>
          {formatAmount(max)}{" "}
          <Txt variant="subtitle" color="muted">
            USDT
          </Txt>
        </Txt>
      </View>
      {allowance ? (
        <View
          accessible
          accessibilityRole="progressbar"
          accessibilityLabel={t("transfer.limitUsed", {
            sent: formatAmount(allowance.sent_this_month),
            limit: formatAmount(allowance.limit),
          })}
          accessibilityValue={{
            min: 0,
            max: 100,
            now: Math.round(ratio * 100),
          }}
          style={{ gap: 6 }}
        >
          <View style={[styles.bar, { backgroundColor: theme.border }]}>
            <View
              style={[
                styles.barFill,
                {
                  width: `${ratio * 100}%`,
                  backgroundColor: ratio >= 1 ? theme.warning : theme.primary,
                },
              ]}
            />
          </View>
          <Txt variant="caption" color="muted">
            {t("transfer.limitUsed", {
              sent: formatAmount(allowance.sent_this_month),
              limit: formatAmount(allowance.limit),
            })}
          </Txt>
        </View>
      ) : null}
      <View style={styles.infoRow}>
        <Info size={16} color={theme.muted} strokeWidth={2} />
        <Txt variant="caption" color="muted" style={{ flex: 1 }}>
          {t("transfer.balanceLine", { balance: formatAmount(balance) })}
        </Txt>
      </View>
    </Card>
  );
}

function RecipientCard({
  recipient,
  query,
  onChange,
}: {
  recipient: Recipient;
  query: string;
  onChange: () => void;
}) {
  const { t } = useTranslation();
  const theme = useTheme();
  return (
    <View style={[styles.recipient, { backgroundColor: theme.surface }]}>
      <Avatar name={recipient.name} size={48} />
      <View style={{ flex: 1 }}>
        <Txt variant="micro" color="muted">
          {t("transfer.recipient")}
        </Txt>
        <Txt variant="subtitle" numberOfLines={1}>
          {recipient.name}
        </Txt>
        <Txt variant="caption" color="muted" numberOfLines={1}>
          {query.trim()}
        </Txt>
      </View>
      <Pressable accessibilityRole="button" onPress={onChange} hitSlop={10}>
        <Txt variant="label" style={{ color: theme.primary }}>
          {t("transfer.change")}
        </Txt>
      </Pressable>
    </View>
  );
}

/** Big amount input ("0.00"), as on the price screens. */
function AmountInput({
  value,
  onChange,
  label,
}: {
  value: string;
  onChange: (text: string) => void;
  label: string;
}) {
  const theme = useTheme();
  return (
    <TextInput
      accessibilityLabel={label}
      value={value}
      onChangeText={onChange}
      placeholder="0.00"
      placeholderTextColor={theme.muted}
      keyboardType="decimal-pad"
      selectionColor={theme.primary}
      cursorColor={theme.primary}
      autoFocus
      maxFontSizeMultiplier={1.3}
      style={[styles.amountInput, { color: theme.text }]}
    />
  );
}

const styles = StyleSheet.create({
  allowance: {
    fontFamily: fonts.extrabold,
    fontSize: 30,
    lineHeight: 36,
    letterSpacing: -0.5,
  },
  bar: { height: 8, borderRadius: 4, overflow: "hidden" },
  barFill: { height: 8, borderRadius: 4 },
  infoRow: { flexDirection: "row", alignItems: "center", gap: space.xs },
  recipient: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.sm,
    borderRadius: radius.card,
    padding: space.md,
  },
  amountBox: {
    marginTop: space.md,
    borderRadius: radius.card,
    borderWidth: 1.5,
    padding: space.md,
    gap: space.xs,
  },
  amountRow: { flexDirection: "row", alignItems: "center", gap: space.xs },
  amountInput: {
    flex: 1,
    fontFamily: fonts.extrabold,
    fontSize: 40,
    paddingVertical: 4,
    fontVariant: ["tabular-nums"],
  },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: space.xs },
  bigAmount: {
    fontFamily: fonts.extrabold,
    fontSize: 40,
    lineHeight: 48,
    letterSpacing: -0.8,
  },
  bigCurrency: { fontFamily: fonts.extrabold, fontSize: 18 },
  hr: { height: 1 },
  done: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: space.sm,
    paddingVertical: space.xxl,
  },
  doneRing: {
    width: 112,
    height: 112,
    borderRadius: 56,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: space.sm,
  },
});
