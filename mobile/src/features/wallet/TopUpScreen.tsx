import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ActivityIndicator, Pressable, StyleSheet, View } from "react-native";

import {
  Bitcoin,
  CircleCheck,
  CircleX,
  Hash,
  Pencil,
  Receipt,
  ShieldCheck,
  Zap,
} from "@/components/icons";
import { showToast } from "@/components/Toast";
import {
  Button,
  Card,
  EmptyState,
  ErrorText,
  Field,
  IconTile,
  Notice,
  Screen,
  Skeleton,
  StatusPill,
  type Tone,
  Txt,
} from "@/components/ui";
import {
  useNotifyTopUp,
  useSaveBinancePayId,
  useTopUpInfo,
  useTopUps,
  useWallet,
} from "@/hooks/useWallet";
import { apiErrorMessage, apiFormErrors } from "@/i18n";
import { confirmHaptic } from "@/lib/feedback";
import { formatAmount } from "@/lib/money";
import type { TopUp, TopUpInfo, TopUpStatus } from "@/lib/types";
import {
  isValidBinancePayId,
  normalizeBinancePayId,
  normalizeOrderReference,
  parseAmountInput,
  sanitizeAmountInput,
  topUpAmountError,
} from "@/lib/wallet";
import { radius, space, useTheme } from "@/theme";

import { CopyValue, FlowHeader, leaveFlow, Steps } from "./components";
import { useWalletFormat } from "./format";

type Step = "binance" | "pay" | "notify" | "sent";

const STATUS_TONE: Record<TopUpStatus, Tone> = {
  pending: "warning",
  completed: "success",
  rejected: "danger",
  unmatched: "info",
};

/**
 * Recargar (docs/api/phase-1d.md): the driver registers their Binance Pay ID, sends USDT to Kuulis' Pay ID
 * and tells us with "Ya pagué". Payments are matched automatically by the payer's Pay ID when Kuulis has
 * Binance API credentials (`automatic`), otherwise an admin confirms them.
 */
export function TopUpScreen() {
  const { t } = useTranslation();
  const wallet = useWallet();
  const info = useTopUpInfo();
  const [editingId, setEditingId] = useState(false);
  const [step, setStep] = useState<Exclude<Step, "binance">>("pay");

  const loading = wallet.isPending || info.isPending;
  const error = wallet.error ?? info.error;
  const payerId = wallet.data?.binance_pay_id ?? null;
  const current: Step = !payerId || editingId ? "binance" : step;

  if (loading || error || !wallet.data || !info.data) {
    return (
      <Screen header={<FlowHeader title={t("topUp.title")} />}>
        {loading ? (
          <View style={{ gap: space.md }}>
            <Skeleton height={120} radius={radius.card} />
            <Skeleton height={52} />
            <Skeleton height={180} radius={radius.card} />
          </View>
        ) : (
          <>
            <EmptyState
              icon={CircleX}
              title={t("common.error")}
              body={apiErrorMessage(error)}
            />
            <Button
              title={t("common.retry")}
              variant="secondary"
              onPress={() => {
                void wallet.refetch();
                void info.refetch();
              }}
            />
          </>
        )}
      </Screen>
    );
  }

  if (current === "binance") {
    return (
      <BinanceIdStep
        initial={payerId ?? ""}
        automatic={info.data.automatic}
        editing={!!payerId}
        onCancel={() => setEditingId(false)}
        onSaved={() => {
          setEditingId(false);
          setStep("pay");
        }}
      />
    );
  }
  if (current === "notify") {
    return (
      <NotifyStep
        info={info.data}
        onBack={() => setStep("pay")}
        onSent={() => setStep("sent")}
      />
    );
  }
  if (current === "sent") {
    return (
      <SentStep automatic={info.data.automatic} onMore={() => setStep("pay")} />
    );
  }
  return (
    <PayStep
      info={info.data}
      payerId={payerId ?? ""}
      onChangeId={() => setEditingId(true)}
      onNotify={() => setStep("notify")}
    />
  );
}

// ── Step 1: the driver's Binance Pay ID ──

function BinanceIdStep({
  initial,
  automatic,
  editing,
  onCancel,
  onSaved,
}: {
  initial: string;
  automatic: boolean;
  editing: boolean;
  onCancel: () => void;
  onSaved: () => void;
}) {
  const { t } = useTranslation();
  const save = useSaveBinancePayId();
  const [value, setValue] = useState(initial);
  const [error, setError] = useState<string>();
  const [formError, setFormError] = useState<string>();

  const submit = () => {
    setFormError(undefined);
    const id = normalizeBinancePayId(value);
    if (!isValidBinancePayId(id)) {
      setError(t("topUp.binance.invalid"));
      return;
    }
    if (id === initial) {
      onSaved();
      return;
    }
    setError(undefined);
    save.mutate(id, {
      onSuccess: () => {
        confirmHaptic();
        showToast(t("topUp.binance.saved"), "success");
        onSaved();
      },
      onError: (e) => {
        const { fields, message } = apiFormErrors<"binance_pay_id">(e, {
          binance_pay_id_taken: "binance_pay_id",
        });
        setError(fields.binance_pay_id);
        setFormError(message);
      },
    });
  };

  return (
    <Screen
      header={
        <FlowHeader
          title={t("topUp.binance.title")}
          subtitle={
            automatic
              ? t("topUp.binance.subtitleAuto")
              : t("topUp.binance.subtitleManual")
          }
          onBack={editing ? onCancel : leaveFlow}
        />
      }
      footer={
        <Button
          title={editing ? t("common.save") : t("topUp.binance.continue")}
          loading={save.isPending}
          disabled={!normalizeBinancePayId(value)}
          onPress={submit}
        />
      }
    >
      <Field
        label={t("topUp.binance.label")}
        icon={Hash}
        value={value}
        onChangeText={(text) => {
          setValue(text.replace(/[^\d\s-]/g, ""));
          setError(undefined);
        }}
        placeholder="123456789"
        keyboardType="number-pad"
        autoComplete="off"
        autoCorrect={false}
        maxLength={24}
        returnKeyType="done"
        onSubmitEditing={submit}
        error={error}
        hint={t("topUp.binance.hint")}
      />
      <ErrorText>{formError}</ErrorText>
      <Card style={{ gap: space.md, marginTop: space.xs }}>
        <View style={styles.row}>
          <IconTile icon={Bitcoin} tone="accent" size={40} />
          <Txt variant="subtitle" style={{ flex: 1 }}>
            {t("topUp.binance.whereTitle")}
          </Txt>
        </View>
        <Steps
          items={[
            t("topUp.binance.where1"),
            t("topUp.binance.where2"),
            t("topUp.binance.where3"),
          ]}
        />
        <Txt variant="caption" color="muted">
          {t("topUp.binance.whereNote")}
        </Txt>
      </Card>
      <Notice tone="info" icon={ShieldCheck} style={{ marginTop: space.md }}>
        {t("topUp.binance.privacy")}
      </Notice>
    </Screen>
  );
}

// ── Step 2: how to pay ──

function PayStep({
  info,
  payerId,
  onChangeId,
  onNotify,
}: {
  info: TopUpInfo;
  payerId: string;
  onChangeId: () => void;
  onNotify: () => void;
}) {
  const { t } = useTranslation();
  const theme = useTheme();
  const available = !!info.pay_id;
  const min = formatAmount(info.min_amount);

  return (
    <Screen
      header={
        <FlowHeader title={t("topUp.title")} subtitle={t("topUp.subtitle")} />
      }
      footer={
        available ? (
          <Button
            title={t("topUp.paid")}
            icon={CircleCheck}
            onPress={onNotify}
            accessibilityHint={t("topUp.paidHint")}
          />
        ) : null
      }
    >
      {available ? (
        <Card elevated style={{ gap: space.md }}>
          <CopyValue
            label={t("topUp.kuulisPayId")}
            value={info.pay_id}
            copiedMessage={t("topUp.copied")}
          />
          <View style={{ gap: space.xxs }}>
            <Txt variant="caption" color="muted">
              {t("topUp.accountName")}
            </Txt>
            <Txt variant="bodyStrong">{info.account_name}</Txt>
          </View>
          <View style={styles.row}>
            <StatusPill
              label={t("topUp.minimum", { amount: min })}
              tone="accent"
            />
            <StatusPill label={t("topUp.onlyUsdt")} tone="neutral" />
          </View>
        </Card>
      ) : (
        <Notice tone="warning" title={t("topUp.unavailableTitle")}>
          {t("topUp.unavailable")}
        </Notice>
      )}

      <Txt
        variant="overline"
        color="muted"
        style={{ marginTop: space.xl, marginBottom: space.sm }}
      >
        {t("topUp.howTo")}
      </Txt>
      <Steps
        items={[
          t("topUp.step1"),
          t("topUp.step2", {
            payId: info.pay_id || "—",
            name: info.account_name,
          }),
          t("topUp.step3", { min, payerId }),
          info.automatic ? t("topUp.step4Auto") : t("topUp.step4Manual"),
        ]}
      />

      <Notice
        tone={info.automatic ? "success" : "info"}
        icon={info.automatic ? Zap : ShieldCheck}
        title={info.automatic ? t("topUp.autoTitle") : t("topUp.manualTitle")}
        style={{ marginTop: space.lg }}
      >
        {info.automatic
          ? t("topUp.autoBody", { payerId })
          : t("topUp.manualBody")}
      </Notice>

      <Pressable
        accessibilityRole="button"
        accessibilityLabel={t("topUp.yourIdA11y", { id: payerId })}
        accessibilityHint={t("topUp.changeId")}
        onPress={onChangeId}
        style={({ pressed }) => [
          styles.idRow,
          { backgroundColor: theme.surface, opacity: pressed ? 0.7 : 1 },
        ]}
      >
        <View style={{ flex: 1 }}>
          <Txt variant="caption" color="muted">
            {t("topUp.yourId")}
          </Txt>
          <Txt variant="bodyStrong" tabular>
            {payerId}
          </Txt>
        </View>
        <Pencil size={16} color={theme.primary} strokeWidth={2.2} />
        <Txt variant="label" style={{ color: theme.primary }}>
          {t("topUp.changeId")}
        </Txt>
      </Pressable>

      <TopUpHistory />
    </Screen>
  );
}

function TopUpHistory() {
  const { t } = useTranslation();
  const theme = useTheme();
  const format = useWalletFormat();
  const topUps = useTopUps();
  const items = topUps.data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <View style={{ marginTop: space.xl }}>
      <Txt variant="subtitle" accessibilityRole="header">
        {t("topUp.history")}
      </Txt>
      {topUps.isPending ? (
        <View style={{ gap: space.sm, marginTop: space.sm }}>
          <Skeleton height={56} />
          <Skeleton height={56} />
        </View>
      ) : topUps.isError ? (
        <View style={{ marginTop: space.sm }}>
          <ErrorText>{apiErrorMessage(topUps.error)}</ErrorText>
          <Button
            title={t("common.retry")}
            variant="secondary"
            size="sm"
            onPress={() => void topUps.refetch()}
          />
        </View>
      ) : !items.length ? (
        <Txt color="muted" style={{ marginTop: space.xs }}>
          {t("topUp.historyEmpty")}
        </Txt>
      ) : (
        <View style={{ marginTop: space.xs }}>
          {items.map((item, index) => (
            <TopUpRow
              key={item.id}
              item={item}
              divider={index < items.length - 1}
              date={format.shortDate(item.completed_at ?? item.created_at)}
            />
          ))}
          {topUps.hasNextPage ? (
            topUps.isFetchingNextPage ? (
              <ActivityIndicator
                color={theme.primary}
                style={{ margin: space.sm }}
              />
            ) : (
              <Button
                title={t("topUp.more")}
                variant="ghost"
                size="sm"
                onPress={() => void topUps.fetchNextPage()}
              />
            )
          ) : null}
        </View>
      )}
    </View>
  );
}

function TopUpRow({
  item,
  date,
  divider,
}: {
  item: TopUp;
  date: string;
  divider: boolean;
}) {
  const { t } = useTranslation();
  const theme = useTheme();
  const status = t(`topUp.status.${item.status}`);
  const detail =
    item.status === "rejected" && item.rejection_reason
      ? item.rejection_reason
      : item.reference
        ? t("wallet.kind.top_up.reference", { reference: item.reference })
        : t(`topUp.statusHint.${item.status}`);
  return (
    <View
      accessible
      accessibilityLabel={`${formatAmount(item.amount)} USDT, ${status}, ${date}. ${detail}`}
      style={[
        styles.topUp,
        divider && { borderBottomWidth: 1, borderBottomColor: theme.border },
      ]}
    >
      <IconTile icon={Receipt} tone={STATUS_TONE[item.status]} size={40} />
      <View style={{ flex: 1, gap: 2 }}>
        <Txt variant="bodyStrong" tabular>
          {formatAmount(item.amount)} USDT
        </Txt>
        <Txt variant="caption" color="muted" numberOfLines={2}>
          {`${detail} · ${date}`}
        </Txt>
      </View>
      <StatusPill label={status} tone={STATUS_TONE[item.status]} />
    </View>
  );
}

// ── Step 3: "Ya pagué" ──

function NotifyStep({
  info,
  onBack,
  onSent,
}: {
  info: TopUpInfo;
  onBack: () => void;
  onSent: () => void;
}) {
  const { t } = useTranslation();
  const notify = useNotifyTopUp();
  const [amount, setAmount] = useState("");
  const [reference, setReference] = useState("");
  const [amountError, setAmountError] = useState<string>();
  const [formError, setFormError] = useState<string>();
  const min = formatAmount(info.min_amount);

  const submit = () => {
    setFormError(undefined);
    const problem = topUpAmountError(amount, info.min_amount);
    if (problem) {
      setAmountError(
        problem === "below_minimum"
          ? t("topUp.notify.belowMin", { amount: min })
          : t("topUp.notify.amountInvalid"),
      );
      return;
    }
    const value = parseAmountInput(amount) as number;
    const ref = normalizeOrderReference(reference);
    notify.mutate(
      { amount: value.toFixed(2), ...(ref ? { reference: ref } : {}) },
      {
        onSuccess: () => {
          confirmHaptic();
          onSent();
        },
        onError: (e) => {
          const { fields, message } = apiFormErrors<"amount">(e);
          setAmountError(fields.amount);
          setFormError(message);
        },
      },
    );
  };

  return (
    <Screen
      header={
        <FlowHeader
          title={t("topUp.notify.title")}
          subtitle={t("topUp.notify.subtitle")}
          onBack={onBack}
        />
      }
      footer={
        <Button
          title={t("topUp.notify.submit")}
          loading={notify.isPending}
          disabled={!amount}
          onPress={submit}
        />
      }
    >
      <Field
        label={t("topUp.notify.amount")}
        value={amount}
        onChangeText={(text) => {
          setAmount(sanitizeAmountInput(text));
          setAmountError(undefined);
        }}
        placeholder={min}
        keyboardType="decimal-pad"
        error={amountError}
        hint={t("topUp.notify.amountHint", { amount: min })}
        autoFocus
      />
      <Field
        label={t("topUp.notify.reference")}
        icon={Hash}
        value={reference}
        onChangeText={(text) => setReference(normalizeOrderReference(text))}
        placeholder={t("topUp.notify.referencePlaceholder")}
        autoCapitalize="none"
        autoCorrect={false}
        maxLength={64}
        hint={t("topUp.notify.referenceHint")}
        returnKeyType="done"
        onSubmitEditing={submit}
      />
      <ErrorText>{formError}</ErrorText>
      <Notice tone="info">
        {info.automatic
          ? t("topUp.notify.noteAuto")
          : t("topUp.notify.noteManual")}
      </Notice>
    </Screen>
  );
}

// ── Step 4: sent ──

function SentStep({
  automatic,
  onMore,
}: {
  automatic: boolean;
  onMore: () => void;
}) {
  const { t } = useTranslation();
  const theme = useTheme();
  return (
    <Screen
      footer={
        <>
          <Button title={t("topUp.sent.done")} onPress={leaveFlow} />
          <Button
            title={t("topUp.sent.history")}
            variant="ghost"
            onPress={onMore}
          />
        </>
      }
    >
      <View style={styles.sent}>
        <View style={[styles.sentRing, { backgroundColor: theme.successSoft }]}>
          <CircleCheck size={48} color={theme.success} strokeWidth={2} />
        </View>
        <Txt variant="title" align="center" accessibilityRole="header">
          {t("topUp.sent.title")}
        </Txt>
        <Txt color="muted" align="center">
          {automatic ? t("topUp.sent.bodyAuto") : t("topUp.sent.bodyManual")}
        </Txt>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.sm,
    flexWrap: "wrap",
  },
  idRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.xs,
    borderRadius: radius.tile,
    padding: space.md,
    marginTop: space.md,
  },
  topUp: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.sm,
    paddingVertical: space.sm,
    minHeight: 64,
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
