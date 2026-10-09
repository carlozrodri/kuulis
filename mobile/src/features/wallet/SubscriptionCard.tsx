import { router } from "expo-router";
import { useTranslation } from "react-i18next";
import { Pressable, StyleSheet, View } from "react-native";

import {
  CalendarClock,
  ChevronRight,
  Clock,
  Gift,
  LockKeyhole,
  Receipt,
  RotateCcw,
} from "@/components/icons";
import {
  Button,
  Skeleton,
  StatusPill,
  type Tone,
  toneColors,
  Txt,
} from "@/components/ui";
import { apiErrorMessage } from "@/i18n";
import { formatAmount } from "@/lib/money";
import { formatFare } from "@/lib/ride";
import type { SubscriptionSummary } from "@/lib/types";
import {
  feeFor,
  feeTierFor,
  nextDueAt,
  pendingTotal,
  shortfall,
  subscriptionState,
} from "@/lib/wallet";
import { elevation, fonts, radius, space, useTheme } from "@/theme";

import { useWalletFormat } from "./format";

export const goToTopUp = () => router.push("/wallet/top-up");
export const goToCharges = () => router.push("/wallet/charges");

/**
 * Fee card on the wallet screen (Motorizado-Billetera): this month's estimate and tier, the free period, a
 * pending fee with what is missing and until when, or the blocked state.
 */
export function SubscriptionCard({
  summary,
  balance,
  loading,
  error,
  onRetry,
}: {
  summary: SubscriptionSummary | undefined;
  balance: string | undefined;
  loading: boolean;
  error: unknown;
  onRetry: () => void;
}) {
  const { t } = useTranslation();
  const theme = useTheme();
  const format = useWalletFormat();

  if (loading) {
    return (
      <View style={[styles.card, { backgroundColor: theme.surface }]}>
        <Skeleton height={22} width="60%" />
        <Skeleton height={16} />
        <Skeleton height={16} width="80%" />
      </View>
    );
  }

  if (error || !summary) {
    return (
      <View
        style={[styles.card, styles.row, { backgroundColor: theme.surface }]}
      >
        <Txt variant="caption" color="muted" style={{ flex: 1 }}>
          {t("wallet.sub.loadError", { error: apiErrorMessage(error) })}
        </Txt>
        <Pressable
          accessibilityRole="button"
          onPress={onRetry}
          hitSlop={10}
          style={styles.row}
        >
          <RotateCcw size={16} color={theme.primary} strokeWidth={2.2} />
          <Txt variant="bodyStrong" style={{ color: theme.primary }}>
            {t("common.retry")}
          </Txt>
        </Pressable>
      </View>
    );
  }

  const state = subscriptionState(summary);
  const pending = summary.pending.filter((c) => c.status === "pending");
  const owed = pendingTotal(pending);
  const missing = shortfall(balance, owed);
  const dueAt = nextDueAt(pending);

  if (state === "blocked") {
    const danger = toneColors(theme, "danger");
    return (
      <View
        accessibilityRole="alert"
        style={[
          styles.card,
          {
            backgroundColor: danger.bg,
            borderColor: theme.danger,
            borderWidth: 1.5,
          },
        ]}
      >
        <View style={styles.row}>
          <View style={[styles.badgeIcon, { backgroundColor: theme.surface }]}>
            <LockKeyhole size={20} color={theme.danger} strokeWidth={2.2} />
          </View>
          <Txt
            variant="subtitle"
            style={{ color: theme.danger, flex: 1 }}
            accessibilityRole="header"
          >
            {t("wallet.sub.blocked.title")}
          </Txt>
          <Txt variant="subtitle" tabular style={{ color: theme.danger }}>
            {formatFare(owed)}
          </Txt>
        </View>
        <Txt style={{ color: theme.text }}>
          {dueAt
            ? t("wallet.sub.blocked.bodySince", {
                amount: formatFare(owed),
                date: format.dayMonth(dueAt),
              })
            : t("wallet.sub.blocked.body", { amount: formatFare(owed) })}
        </Txt>
        {missing > 0 ? (
          <Txt variant="label" style={{ color: theme.text }}>
            {t("wallet.sub.blocked.topUp", { amount: formatAmount(missing) })}
          </Txt>
        ) : null}
        <Button
          title={t("wallet.topUpNow")}
          variant="accent"
          onPress={goToTopUp}
        />
        <HistoryLink />
      </View>
    );
  }

  let title: string;
  let amount: string;
  let pill: { label: string; tone: Tone } | null = null;
  let body: string;
  let extra: string | null = null;

  if (state === "pending") {
    const first = pending[0];
    title =
      pending.length > 1
        ? t("wallet.sub.pendingMany", { count: pending.length })
        : t("wallet.sub.pendingTitle", { date: format.chargeDay(first.month) });
    amount = formatFare(owed);
    body =
      pending.length > 1
        ? pending
            .map((c) => `${format.monthTitle(c.month)}: ${formatFare(c.fee)}`)
            .join(" · ")
        : format.earnedSentence(summary, first);
  } else if (state === "free") {
    title = t("wallet.sub.thisMonth");
    amount = formatFare(0);
    pill = summary.free_until
      ? {
          label: t("wallet.sub.freeUntil", {
            date: format.shortDate(summary.free_until),
          }),
          tone: "accent",
        }
      : null;
    body = t("wallet.sub.freeBody", {
      earnings: formatFare(summary.earnings),
      month: format.monthName(summary.month),
    });
    const wouldPay = feeFor(summary.tiers, summary.earnings);
    if (wouldPay > 0) {
      const tier = feeTierFor(summary.tiers, summary.earnings);
      extra = t("wallet.sub.wouldPay", {
        fee: formatFare(wouldPay),
        tier: tier ? format.tierText(tier) : "",
      });
    }
  } else if (state === "not_started") {
    title = t("wallet.sub.monthly");
    amount = formatFare(0);
    pill = { label: t("wallet.sub.freeMonthsPill"), tone: "accent" };
    body = t("driver.home.freeMonths");
    extra = t("wallet.sub.howItWorks");
  } else {
    title = t("wallet.sub.estimated", {
      month: format.monthName(summary.month),
    });
    amount = formatFare(summary.estimated_fee);
    const tier = feeTierFor(summary.tiers, summary.earnings);
    body = tier
      ? t("wallet.sub.soFarTier", {
          earnings: formatFare(summary.earnings),
          month: format.monthName(summary.month),
          tier: format.tierText(tier),
        })
      : t("wallet.sub.noEarnings", {
          month: format.monthName(summary.month),
        });
    const chargeOn = summary.next_charge_at
      ? format.dayMonth(summary.next_charge_at)
      : format.chargeDay(summary.month);
    const short = shortfall(balance, summary.estimated_fee);
    extra =
      short > 0
        ? t("wallet.sub.chargedOnShort", {
            date: chargeOn,
            amount: formatAmount(short),
          })
        : t("wallet.sub.chargedOn", { date: chargeOn });
  }

  return (
    <View
      style={[
        styles.card,
        { backgroundColor: theme.surface },
        elevation(theme),
      ]}
    >
      <View style={styles.header}>
        <Txt variant="subtitle" style={{ flex: 1 }} accessibilityRole="header">
          {title}
        </Txt>
        <Txt style={[styles.fee, { color: theme.text }]} tabular>
          {amount}
        </Txt>
      </View>
      {pill ? <StatusPill label={pill.label} tone={pill.tone} /> : null}
      <Txt variant="caption" color="muted" style={styles.body}>
        {body}
      </Txt>
      {extra ? (
        <View style={styles.row}>
          {state === "free" || state === "not_started" ? (
            <Gift size={16} color={theme.muted} strokeWidth={2} />
          ) : (
            <CalendarClock size={16} color={theme.muted} strokeWidth={2} />
          )}
          <Txt variant="caption" color="muted" style={{ flex: 1 }}>
            {extra}
          </Txt>
        </View>
      ) : null}
      {state === "pending" ? (
        <>
          <View
            style={[styles.due, { backgroundColor: theme.warningSoft }]}
            accessibilityRole="alert"
          >
            <Clock size={18} color={theme.warning} strokeWidth={2} />
            <Txt variant="label" style={{ color: theme.warning, flex: 1 }}>
              {missing > 0
                ? dueAt
                  ? t("wallet.sub.missingUntil", {
                      amount: formatAmount(missing),
                      date: format.dayMonth(dueAt),
                    })
                  : t("wallet.sub.missing", { amount: formatAmount(missing) })
                : t("wallet.sub.covered")}
            </Txt>
          </View>
          {missing > 0 ? (
            <Button
              title={t("wallet.topUp")}
              variant="accent"
              size="sm"
              onPress={goToTopUp}
            />
          ) : null}
        </>
      ) : null}
      <HistoryLink />
    </View>
  );
}

function HistoryLink() {
  const { t } = useTranslation();
  const theme = useTheme();
  return (
    <Pressable
      accessibilityRole="button"
      onPress={goToCharges}
      style={({ pressed }) => [
        styles.link,
        { borderTopColor: theme.divider, opacity: pressed ? 0.6 : 1 },
      ]}
    >
      <Receipt size={18} color={theme.muted} strokeWidth={2} />
      <Txt variant="label" style={{ flex: 1 }}>
        {t("wallet.sub.history")}
      </Txt>
      <ChevronRight size={18} color={theme.muted} strokeWidth={2.2} />
    </Pressable>
  );
}

/**
 * Floating card on the driver home (Motorizado-Inicio): "Ganado en octubre $142.50 · 23 viajes" and the fee
 * row ("Cuota de este mes: $0 · Gratis hasta 14 ene"). Opens the wallet.
 */
export function EarningsCard({
  summary,
  blocked,
}: {
  summary: SubscriptionSummary;
  blocked: boolean;
}) {
  const { t } = useTranslation();
  const theme = useTheme();
  const format = useWalletFormat();
  const state = blocked ? "blocked" : subscriptionState(summary);
  const pending = summary.pending.filter((c) => c.status === "pending");
  const owed = pendingTotal(pending);
  const dueAt = nextDueAt(pending);
  const trips = typeof summary.trips === "number" ? summary.trips : null;

  let label: string;
  let pill: string | null;
  let tone: Tone;
  switch (state) {
    case "blocked":
      label = t("home.fee.overdue", { amount: formatFare(owed) });
      pill = t("home.fee.blockedPill");
      tone = "danger";
      break;
    case "pending":
      label = t("home.fee.pending", { amount: formatFare(owed) });
      pill = dueAt
        ? t("home.fee.duePill", { date: format.shortDate(dueAt) })
        : null;
      tone = "warning";
      break;
    case "free":
    case "not_started":
      label = t("home.fee.thisMonth", { amount: formatFare(0) });
      pill = summary.free_until
        ? t("wallet.sub.freeUntil", {
            date: format.shortDate(summary.free_until),
          })
        : t("wallet.sub.freeMonthsPill");
      tone = "accent";
      break;
    default:
      label = t("home.fee.estimated", {
        amount: formatFare(summary.estimated_fee),
      });
      pill = summary.next_charge_at
        ? t("home.fee.chargePill", {
            date: format.shortDate(summary.next_charge_at),
          })
        : null;
      tone = "primary";
  }
  const rowColors =
    tone === "accent"
      ? {
          bg: theme.surfaceAlt,
          fg: theme.scheme === "dark" ? theme.primary : theme.primaryPressed,
        }
      : toneColors(theme, tone);
  const month = format.monthName(summary.month);

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={[
        t("home.earned", { month }),
        formatFare(summary.earnings),
        trips !== null ? t("home.trips", { count: trips }) : null,
        label,
        pill,
      ]
        .filter(Boolean)
        .join(". ")}
      accessibilityHint={t("home.openWallet")}
      onPress={() => router.push("/wallet")}
      style={({ pressed }) => [
        styles.earnings,
        { backgroundColor: theme.surface },
        elevation(theme, 2),
        { transform: [{ scale: pressed ? 0.985 : 1 }] },
      ]}
    >
      <View style={styles.header}>
        <View style={{ flex: 1, gap: 2 }}>
          <Txt variant="label" color="muted">
            {t("home.earned", { month })}
          </Txt>
          <Txt style={[styles.earned, { color: theme.text }]} tabular>
            {formatFare(summary.earnings)}
          </Txt>
        </View>
        {trips !== null ? (
          <Txt variant="label" color="muted">
            {t("home.trips", { count: trips })}
          </Txt>
        ) : null}
      </View>
      <View style={[styles.feeRow, { backgroundColor: rowColors.bg }]}>
        <Txt
          variant="label"
          style={{ color: rowColors.fg, flex: 1 }}
          numberOfLines={2}
        >
          {label}
        </Txt>
        {pill ? (
          <StatusPill
            label={pill}
            tone={tone === "primary" ? "neutral" : tone}
          />
        ) : null}
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: { borderRadius: radius.card, padding: space.md, gap: 10 },
  header: { flexDirection: "row", alignItems: "flex-start", gap: space.sm },
  row: { flexDirection: "row", alignItems: "center", gap: space.xs },
  fee: { fontFamily: fonts.extrabold, fontSize: 18, lineHeight: 24 },
  body: { fontSize: 13, lineHeight: 19 },
  due: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.xs,
    borderRadius: radius.field,
    paddingHorizontal: space.sm,
    paddingVertical: 10,
  },
  badgeIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
  },
  link: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.xs,
    borderTopWidth: 1,
    paddingTop: space.sm,
    marginTop: 2,
    minHeight: 40,
  },
  earnings: {
    borderRadius: 22,
    paddingHorizontal: 18,
    paddingVertical: space.md,
    gap: space.sm,
  },
  earned: {
    fontFamily: fonts.extrabold,
    fontSize: 30,
    lineHeight: 36,
    letterSpacing: -0.6,
  },
  feeRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    borderRadius: 14,
    paddingHorizontal: space.sm,
    paddingVertical: 10,
  },
});
