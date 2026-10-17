import { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  ActivityIndicator,
  RefreshControl,
  ScrollView,
  StyleSheet,
  View,
} from "react-native";

import { CalendarClock, CircleX, FileText } from "@/components/icons";
import {
  Button,
  Card,
  Chip,
  EmptyState,
  Notice,
  Screen,
  Skeleton,
  StatusPill,
  type Tone,
  Txt,
} from "@/components/ui";
import { useStatement } from "@/hooks/useWallet";
import { apiErrorMessage } from "@/i18n";
import { formatAmount, formatSignedAmount, parseAmount } from "@/lib/money";
import { formatFare } from "@/lib/ride";
import type { ChargeStatus, Statement } from "@/lib/types";
import { formatTierBound, reducedFrom, toCents } from "@/lib/wallet";
import { fonts, radius, space, useTheme } from "@/theme";

import { FlowHeader, SummaryRow } from "./components";
import { useWalletFormat } from "./format";

const CHARGE_TONE: Record<ChargeStatus, Tone> = {
  paid: "success",
  pending: "warning",
  waived: "neutral",
};

/**
 * "Estado de cuenta" (doc 17): one month of the driver's wallet — what they earned, the trips, the tier and
 * the fee (an estimate while the month is open), the money that moved and the opening and closing balance.
 * The same statement goes by email on the 1st, once fees are charged.
 */
export function StatementScreen() {
  const { t } = useTranslation();
  const theme = useTheme();
  const format = useWalletFormat();
  // null: the API's default month (last month, or the only one).
  const [month, setMonth] = useState<string | null>(null);
  const statement = useStatement(month);
  const data = statement.data;
  const current = data?.month ?? month;

  return (
    <Screen
      header={
        <FlowHeader
          title={t("wallet.statement.title")}
          subtitle={t("wallet.statement.subtitle")}
        />
      }
      refreshControl={
        <RefreshControl
          refreshing={statement.isRefetching && !statement.isPlaceholderData}
          onRefresh={() => void statement.refetch()}
          tintColor={theme.primary}
        />
      }
    >
      {data && data.months.length > 1 ? (
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.months}
          accessibilityLabel={t("wallet.statement.pickMonth")}
          style={{ marginBottom: space.md, flexGrow: 0 }}
        >
          {data.months.map((value) => (
            <Chip
              key={value}
              label={format.monthTitle(value)}
              selected={value === current}
              onPress={() => setMonth(value)}
            />
          ))}
        </ScrollView>
      ) : null}

      {statement.isPending ? (
        <View style={{ gap: space.md }}>
          <Skeleton height={120} radius={radius.card} />
          <Skeleton height={140} radius={radius.card} />
          <Skeleton height={220} radius={radius.card} />
        </View>
      ) : !data ? (
        <>
          <EmptyState
            icon={CircleX}
            title={t("common.error")}
            body={apiErrorMessage(statement.error)}
          />
          <Button
            title={t("common.retry")}
            variant="secondary"
            onPress={() => void statement.refetch()}
          />
        </>
      ) : (
        <View
          style={{
            gap: space.md,
            opacity: statement.isPlaceholderData ? 0.5 : 1,
          }}
        >
          {statement.isPlaceholderData ? (
            <ActivityIndicator color={theme.primary} />
          ) : null}
          {statement.isError ? (
            <Notice tone="danger">{apiErrorMessage(statement.error)}</Notice>
          ) : null}
          <EarningsCard statement={data} />
          <FeeCard statement={data} />
          <MovementsCard statement={data} />
          <Notice tone="info" icon={FileText}>
            {t("wallet.statement.emailNote")}
          </Notice>
        </View>
      )}
    </Screen>
  );
}

function EarningsCard({ statement }: { statement: Statement }) {
  const { t } = useTranslation();
  const format = useWalletFormat();
  const differs = toCents(statement.earned) !== toCents(statement.counted);
  return (
    <Card style={{ gap: space.xxs }}>
      <Txt variant="overline" color="muted">
        {format.monthTitle(statement.month)}
      </Txt>
      <SummaryRow
        label={t("wallet.statement.earned")}
        value={formatFare(statement.earned)}
        strong
      />
      <SummaryRow
        label={t("wallet.statement.counted")}
        value={formatFare(statement.counted)}
      />
      <SummaryRow
        label={t("wallet.statement.trips")}
        value={String(statement.trips)}
      />
      {differs ? (
        <Txt variant="caption" color="muted">
          {t("wallet.statement.countedNote")}
        </Txt>
      ) : null}
    </Card>
  );
}

function FeeCard({ statement }: { statement: Statement }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const format = useWalletFormat();
  const charge = statement.charge;
  const original = reducedFrom(charge);
  const above = statement.tier ? parseAmount(statement.tier.above) : null;

  let detail: string | null = null;
  if (statement.estimated)
    detail = t("wallet.statement.estimateNote", {
      date: format.chargeDay(statement.month),
    });
  else if (charge?.status === "pending")
    detail = charge.due_at
      ? t("charges.dueOn", { date: format.dayMonth(charge.due_at) })
      : t("charges.statusHint.pending");
  else if (charge?.status === "paid")
    detail = charge.paid_at
      ? t("charges.paidOn", { date: format.dayMonth(charge.paid_at) })
      : t("charges.statusHint.paid");
  else if (charge?.status === "waived")
    detail = charge.free_period
      ? t("charges.freePeriod")
      : charge.waived_reason
        ? t("charges.waivedReason", { reason: charge.waived_reason })
        : t("charges.statusHint.waived");

  return (
    <Card style={{ gap: space.xs }}>
      <View style={styles.feeTop}>
        <View style={{ flex: 1, gap: 4 }}>
          <Txt variant="bodyStrong">
            {t("wallet.statement.fee", {
              month: format.monthName(statement.month),
            })}
          </Txt>
          <View style={styles.pills}>
            {statement.estimated ? (
              <StatusPill label={t("wallet.statement.estimated")} tone="info" />
            ) : null}
            {charge ? (
              <StatusPill
                label={t(`charges.status.${charge.status}`)}
                tone={CHARGE_TONE[charge.status]}
                dot
              />
            ) : null}
          </View>
        </View>
        <View style={{ alignItems: "flex-end" }}>
          <Txt style={[styles.fee, { color: theme.text }]} tabular>
            {statement.estimated ? "≈ " : ""}
            {formatFare(statement.fee)}
          </Txt>
          {original !== null ? (
            <Txt
              variant="caption"
              color="muted"
              tabular
              style={{ textDecorationLine: "line-through" }}
            >
              {formatFare(original)}
            </Txt>
          ) : null}
        </View>
      </View>
      {above !== null ? (
        <Txt variant="caption" color="muted">
          {t("wallet.statement.tier", { from: formatTierBound(above) })}
        </Txt>
      ) : (
        <Txt variant="caption" color="muted">
          {t("wallet.statement.noTier")}
        </Txt>
      )}
      {original !== null ? (
        <Txt variant="caption" color="muted">
          {t("wallet.statement.originalFee", { fee: formatFare(original) })}
        </Txt>
      ) : null}
      {detail ? (
        <View style={styles.detail}>
          <CalendarClock size={16} color={theme.muted} strokeWidth={2} />
          <Txt variant="label" color="muted" style={{ flex: 1 }}>
            {detail}
          </Txt>
        </View>
      ) : null}
    </Card>
  );
}

function MovementsCard({ statement }: { statement: Statement }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const moved = statement.movements;
  const negative = (value: string) => -(parseAmount(value) ?? 0);
  const rows: { key: string; value: number | string }[] = [
    { key: "top_ups", value: moved.top_ups },
    { key: "promo_credits", value: moved.promo_credits },
    { key: "referral_bonuses", value: moved.referral_bonuses ?? "0" },
    { key: "transfers_in", value: moved.transfers_in },
    { key: "transfers_out", value: negative(moved.transfers_out) },
    { key: "fees", value: negative(moved.fees) },
    { key: "adjustments", value: moved.adjustments },
  ];
  const shown = rows.filter((row) => (toCents(row.value) ?? 0) !== 0);
  return (
    <Card style={{ gap: space.xxs }}>
      <Txt variant="subtitle" accessibilityRole="header">
        {t("wallet.statement.movements")}
      </Txt>
      <SummaryRow
        label={t("wallet.statement.opening")}
        value={`${formatAmount(statement.opening_balance)} USDT`}
      />
      <View style={[styles.rule, { backgroundColor: theme.divider }]} />
      {shown.length ? (
        shown.map((row) => (
          <SummaryRow
            key={row.key}
            label={t(`wallet.statement.kind.${row.key}`)}
            value={formatSignedAmount(row.value)}
          />
        ))
      ) : (
        <Txt color="muted" style={{ paddingVertical: space.xs }}>
          {t("wallet.statement.noMovements")}
        </Txt>
      )}
      <View style={[styles.rule, { backgroundColor: theme.divider }]} />
      <SummaryRow
        label={t("wallet.statement.closing")}
        value={`${formatAmount(statement.closing_balance)} USDT`}
        strong
      />
    </Card>
  );
}

const styles = StyleSheet.create({
  months: { gap: space.xs, paddingRight: space.xs },
  feeTop: { flexDirection: "row", alignItems: "flex-start", gap: space.sm },
  pills: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
  fee: { fontFamily: fonts.extrabold, fontSize: 22, lineHeight: 28 },
  detail: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.xs,
    marginTop: space.xxs,
  },
  rule: { height: 1, marginVertical: space.xxs },
});
