import { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { ChevronDown, CircleX, Receipt } from "@/components/icons";
import {
  Button,
  EmptyState,
  Skeleton,
  StatusPill,
  type Tone,
  Txt,
} from "@/components/ui";
import { useCharges, useSubscription } from "@/hooks/useWallet";
import { apiErrorMessage } from "@/i18n";
import { formatFare } from "@/lib/ride";
import type { Charge, ChargeStatus, SubscriptionSummary } from "@/lib/types";
import { feeTierFor, formatTierBound, toCents } from "@/lib/wallet";
import { fonts, radius, space, useTheme } from "@/theme";

import { FlowHeader } from "./components";
import { useWalletFormat } from "./format";

const STATUS_TONE: Record<ChargeStatus, Tone> = {
  paid: "success",
  pending: "warning",
  waived: "neutral",
};

/** "Cuotas": every monthly charge (paid, pending or waived) and how the fee is calculated. */
export function ChargesScreen() {
  const { t } = useTranslation();
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const charges = useCharges();
  const subscription = useSubscription();
  const items = charges.data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <View
      style={{
        flex: 1,
        backgroundColor: theme.background,
        paddingTop: insets.top,
      }}
    >
      <FlatList
        data={items}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <ChargeCard charge={item} summary={subscription.data} />
        )}
        contentContainerStyle={{
          paddingHorizontal: space.lg,
          paddingBottom: Math.max(insets.bottom, space.md) + space.md,
          gap: space.sm,
          flexGrow: 1,
        }}
        refreshControl={
          <RefreshControl
            refreshing={charges.isRefetching && !charges.isFetchingNextPage}
            onRefresh={() => {
              void charges.refetch();
              void subscription.refetch();
            }}
            tintColor={theme.primary}
          />
        }
        onEndReachedThreshold={0.4}
        onEndReached={() => {
          if (charges.hasNextPage && !charges.isFetchingNextPage)
            void charges.fetchNextPage();
        }}
        ListHeaderComponent={
          <View style={{ gap: space.sm, paddingBottom: space.xs }}>
            <FlowHeader
              title={t("charges.title")}
              subtitle={t("charges.subtitle")}
            />
            {subscription.data?.tiers?.length ? (
              <TiersCard summary={subscription.data} />
            ) : null}
          </View>
        }
        ListFooterComponent={
          charges.isFetchingNextPage ? (
            <ActivityIndicator
              color={theme.primary}
              style={{ margin: space.md }}
            />
          ) : null
        }
        ListEmptyComponent={
          charges.isPending ? (
            <View style={{ gap: space.sm }}>
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} height={96} radius={radius.card} />
              ))}
            </View>
          ) : charges.isError ? (
            <View>
              <EmptyState
                icon={CircleX}
                title={t("common.error")}
                body={apiErrorMessage(charges.error)}
              />
              <Button
                title={t("common.retry")}
                variant="secondary"
                onPress={() => void charges.refetch()}
              />
            </View>
          ) : (
            <EmptyState
              icon={Receipt}
              title={t("charges.empty")}
              body={t("charges.emptyBody")}
            />
          )
        }
      />
    </View>
  );
}

function ChargeCard({
  charge,
  summary,
}: {
  charge: Charge;
  summary: SubscriptionSummary | undefined;
}) {
  const { t } = useTranslation();
  const theme = useTheme();
  const format = useWalletFormat();
  const status = t(`charges.status.${charge.status}`);

  let detail: string;
  if (charge.status === "pending") {
    detail = charge.due_at
      ? t("charges.dueOn", { date: format.dayMonth(charge.due_at) })
      : t("charges.statusHint.pending");
  } else if (charge.status === "paid") {
    detail = charge.paid_at
      ? t("charges.paidOn", { date: format.dayMonth(charge.paid_at) })
      : t("charges.statusHint.paid");
  } else if (charge.free_period) {
    detail = t("charges.freePeriod");
  } else if ((toCents(charge.fee) ?? 0) === 0 && !charge.waived_reason) {
    detail = t("charges.noFee");
  } else {
    detail = charge.waived_reason
      ? t("charges.waivedReason", { reason: charge.waived_reason })
      : t("charges.statusHint.waived");
  }

  const month = format.monthTitle(charge.month);
  return (
    <View
      accessible
      accessibilityLabel={`${month}. ${status}. ${formatFare(charge.fee)}. ${format.earnedSentence(summary, charge)} ${detail}`}
      style={[
        styles.card,
        { backgroundColor: theme.surface },
        charge.status === "pending" && {
          borderColor: theme.warning,
          borderWidth: 1.5,
        },
      ]}
    >
      <View style={styles.top}>
        <View style={{ flex: 1, gap: 4 }}>
          <Txt variant="subtitle">{month}</Txt>
          <View style={styles.pills}>
            <StatusPill label={status} tone={STATUS_TONE[charge.status]} dot />
            {charge.free_period ? (
              <StatusPill label={t("charges.freePill")} tone="accent" />
            ) : null}
          </View>
        </View>
        <Txt
          style={[
            styles.fee,
            {
              color: theme.text,
              textDecorationLine:
                charge.status === "waived" && (toCents(charge.fee) ?? 0) > 0
                  ? "line-through"
                  : "none",
            },
          ]}
          tabular
        >
          {formatFare(charge.fee)}
        </Txt>
      </View>
      <Txt variant="caption" color="muted">
        {format.earnedSentence(summary, charge)}
      </Txt>
      <Txt
        variant="label"
        style={{
          color: charge.status === "pending" ? theme.warning : theme.muted,
        }}
      >
        {detail}
      </Txt>
    </View>
  );
}

/** "¿Cómo se calcula?": the fee schedule, with the driver's current tier marked. */
function TiersCard({ summary }: { summary: SubscriptionSummary }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const [open, setOpen] = useState(false);
  const current = feeTierFor(summary.tiers, summary.earnings);
  const tiers = [...summary.tiers].sort(
    (a, b) => (toCents(a.above) ?? 0) - (toCents(b.above) ?? 0),
  );

  return (
    <View style={[styles.card, { backgroundColor: theme.surfaceAlt }]}>
      <Pressable
        accessibilityRole="button"
        accessibilityState={{ expanded: open }}
        onPress={() => setOpen((v) => !v)}
        style={styles.top}
      >
        <Txt variant="bodyStrong" style={{ flex: 1 }}>
          {t("charges.howTitle")}
        </Txt>
        <ChevronDown
          size={20}
          color={theme.muted}
          strokeWidth={2.2}
          style={{ transform: [{ rotate: open ? "180deg" : "0deg" }] }}
        />
      </Pressable>
      {open ? (
        <View style={{ gap: space.xs }}>
          <Txt variant="caption" color="muted">
            {t("charges.howBody")}
          </Txt>
          {tiers.map((tier, index) => {
            const from = (toCents(tier.above) ?? 0) / 100;
            const nextAbove = tiers[index + 1]?.above;
            const to =
              nextAbove !== undefined ? (toCents(nextAbove) ?? 0) / 100 : null;
            const label =
              to === null
                ? t("charges.tierAbove", { from: formatTierBound(from) })
                : from === 0
                  ? t("charges.tierUpTo", { to: formatTierBound(to) })
                  : t("charges.tierRange", {
                      from: formatTierBound(from),
                      to: formatTierBound(to),
                    });
            const mine = current !== null && current.from === from;
            return (
              <View
                key={tier.above}
                style={[
                  styles.tier,
                  { borderBottomColor: theme.border },
                  index === tiers.length - 1 && { borderBottomWidth: 0 },
                ]}
              >
                <Txt style={{ flex: 1 }}>{label}</Txt>
                {mine ? (
                  <StatusPill label={t("charges.yourTier")} tone="primary" />
                ) : null}
                <Txt variant="bodyStrong" tabular>
                  {formatFare(tier.fee)}
                </Txt>
              </View>
            );
          })}
          <Txt variant="caption" color="muted">
            {t("charges.howNote")}
          </Txt>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: { borderRadius: radius.card, padding: space.md, gap: space.xs },
  top: { flexDirection: "row", alignItems: "flex-start", gap: space.sm },
  pills: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
  fee: { fontFamily: fonts.extrabold, fontSize: 20, lineHeight: 26 },
  tier: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.sm,
    paddingVertical: space.xs,
    borderBottomWidth: 1,
    minHeight: 40,
  },
});
