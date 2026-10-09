import { router } from "expo-router";
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
import Svg, { Path } from "react-native-svg";

import { CircleX, HandCoins, Info, Wallet } from "@/components/icons";
import {
  Button,
  EmptyState,
  Notice,
  Skeleton,
  TAB_BAR_SPACE,
  Txt,
} from "@/components/ui";
import { useWallet, useWalletEntries } from "@/hooks/useWallet";
import { apiErrorMessage } from "@/i18n";
import { formatAmount, formatSignedAmount, parseAmount } from "@/lib/money";
import type { WalletEntry } from "@/lib/types";
import { fonts, radius, space, useTheme } from "@/theme";

/** Text for a movement: "Promoción · viaje de Ana M." / "Kuulis te reintegra el descuento · Bienvenida". */
function useEntryText() {
  const { t } = useTranslation();
  return (entry: WalletEntry) => {
    if (entry.kind === "promo_credit") {
      const passenger = entry.details?.passenger_name;
      return {
        title:
          typeof passenger === "string" && passenger.trim()
            ? t("wallet.kind.promo_credit.title", { name: passenger.trim() })
            : t("wallet.kind.promo_credit.titleNoName"),
        subtitle: entry.description
          ? t("wallet.kind.promo_credit.subtitleNamed", {
              name: entry.description,
            })
          : t("wallet.kind.promo_credit.subtitle"),
      };
    }
    // Kinds from later phases (top-ups, transfers, fees) until the app knows them.
    return { title: t("wallet.kind.other"), subtitle: null };
  };
}

/**
 * Driver wallet (read-only in phase 1C): balance card and movements. Recargar / Transferir arrive in 1D, so
 * they show as disabled "Pronto" buttons.
 */
export function WalletScreen() {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const wallet = useWallet();
  const entries = useWalletEntries();
  const entryText = useEntryText();
  const items = entries.data?.pages.flatMap((page) => page.items) ?? [];

  const refreshing =
    (wallet.isRefetching || entries.isRefetching) &&
    !entries.isFetchingNextPage;
  const refresh = () => {
    void wallet.refetch();
    void entries.refetch();
  };

  const renderItem = ({
    item,
    index,
  }: {
    item: WalletEntry;
    index: number;
  }) => {
    const { title, subtitle } = entryText(item);
    const date = new Date(item.created_at).toLocaleDateString(i18n.language, {
      day: "numeric",
      month: "short",
    });
    const positive = (parseAmount(item.amount) ?? 0) > 0;
    const amount = formatSignedAmount(item.amount);
    const content = (
      <View
        style={[
          styles.entry,
          index < items.length - 1 && {
            borderBottomWidth: 1,
            borderBottomColor: theme.border,
          },
        ]}
      >
        <View style={{ flex: 1, gap: 2 }}>
          <Txt variant="bodyStrong" numberOfLines={2}>
            {title}
          </Txt>
          <Txt variant="caption" color="muted" numberOfLines={2}>
            {subtitle ? `${subtitle} · ${date}` : date}
          </Txt>
        </View>
        <Txt
          variant="bodyStrong"
          color={positive ? "success" : "text"}
          tabular
          style={{ fontFamily: fonts.extrabold }}
        >
          {amount}
        </Txt>
      </View>
    );
    const label = t("wallet.entryA11y", {
      title,
      amount,
      currency: wallet.data?.currency ?? "USDT",
      date,
    });
    if (!item.ride_id) {
      return (
        <View accessible accessibilityLabel={label}>
          {content}
        </View>
      );
    }
    const rideId = item.ride_id;
    return (
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={label}
        accessibilityHint={t("wallet.openRide")}
        onPress={() =>
          router.push({ pathname: "/ride/detail", params: { id: rideId } })
        }
        style={({ pressed }) => ({ opacity: pressed ? 0.6 : 1 })}
      >
        {content}
      </Pressable>
    );
  };

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
        renderItem={renderItem}
        contentContainerStyle={{
          paddingHorizontal: space.lg,
          paddingBottom: TAB_BAR_SPACE + insets.bottom,
          flexGrow: 1,
        }}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={refresh}
            tintColor={theme.primary}
          />
        }
        onEndReachedThreshold={0.4}
        onEndReached={() => {
          if (entries.hasNextPage && !entries.isFetchingNextPage)
            void entries.fetchNextPage();
        }}
        ListHeaderComponent={
          <View style={{ gap: space.md, paddingTop: space.lg }}>
            <Txt variant="title" accessibilityRole="header">
              {t("wallet.title")}
            </Txt>
            <BalanceCard
              balance={wallet.data?.balance}
              currency={wallet.data?.currency}
              loading={wallet.isPending}
              error={wallet.isError ? apiErrorMessage(wallet.error) : null}
              onRetry={() => void wallet.refetch()}
            />
            <Notice tone="info" icon={Info}>
              {t("wallet.promoInfo")}
            </Notice>
            <Txt
              variant="subtitle"
              accessibilityRole="header"
              style={{ marginTop: space.xs }}
            >
              {t("wallet.movements")}
            </Txt>
          </View>
        }
        ListFooterComponent={
          entries.isFetchingNextPage ? (
            <ActivityIndicator
              color={theme.primary}
              style={{ margin: space.md }}
            />
          ) : null
        }
        ListEmptyComponent={
          entries.isPending ? (
            <View style={{ gap: space.sm, paddingTop: space.xs }}>
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} height={52} />
              ))}
            </View>
          ) : entries.isError ? (
            <View>
              <EmptyState
                icon={CircleX}
                title={t("common.error")}
                body={apiErrorMessage(entries.error)}
              />
              <Button
                title={t("common.retry")}
                variant="secondary"
                onPress={() => void entries.refetch()}
              />
            </View>
          ) : (
            <EmptyState
              icon={HandCoins}
              title={t("wallet.empty")}
              body={t("wallet.emptyBody")}
            />
          )
        }
      />
    </View>
  );
}

/** Green card with the balance and the (not yet available) Recargar / Transferir buttons, as in the design. */
function BalanceCard({
  balance,
  currency,
  loading,
  error,
  onRetry,
}: {
  balance: string | undefined;
  currency: string | undefined;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}) {
  const { t } = useTranslation();
  const theme = useTheme();
  const unit = currency ?? "USDT";
  return (
    <View style={[styles.card, { backgroundColor: theme.hero }]}>
      <Svg
        width="100%"
        height={80}
        viewBox="0 0 350 80"
        preserveAspectRatio="none"
        style={styles.wave}
        pointerEvents="none"
      >
        <Path
          d="M0 80 C40 60 70 40 110 52 C150 64 170 28 215 30 C260 32 280 60 320 54 C335 52 345 48 350 48 L350 80 Z"
          fill={theme.heroShade}
        />
      </Svg>
      <View style={styles.cardTop}>
        <View style={{ flex: 1, gap: 2 }}>
          <Txt variant="label" style={{ color: theme.onHero, opacity: 0.85 }}>
            {t("wallet.balance")}
          </Txt>
          {loading ? (
            <Skeleton
              height={40}
              width={160}
              style={{ backgroundColor: theme.heroShade }}
            />
          ) : error ? (
            <View style={{ gap: space.xs, alignItems: "flex-start" }}>
              <Txt variant="caption" style={{ color: theme.onHero }}>
                {error}
              </Txt>
              <Pressable
                accessibilityRole="button"
                onPress={onRetry}
                hitSlop={8}
              >
                <Txt variant="bodyStrong" style={{ color: theme.accent }}>
                  {t("common.retry")}
                </Txt>
              </Pressable>
            </View>
          ) : (
            <View
              accessible
              accessibilityLabel={t("wallet.balanceA11y", {
                amount: formatAmount(balance),
                currency: unit,
              })}
            >
              <Txt style={[styles.balance, { color: theme.onHero }]} tabular>
                {formatAmount(balance)}{" "}
                <Txt style={[styles.currency, { color: theme.onHero }]}>
                  {unit}
                </Txt>
              </Txt>
            </View>
          )}
        </View>
        <View
          style={[
            styles.cardIcon,
            { backgroundColor: "rgba(255,255,255,0.16)" },
          ]}
        >
          <Wallet size={22} color={theme.onHero} strokeWidth={2} />
        </View>
      </View>
      <View style={styles.cardActions}>
        <SoonButton label={t("wallet.topUp")} filled />
        <SoonButton label={t("wallet.transfer")} />
      </View>
    </View>
  );
}

function SoonButton({ label, filled }: { label: string; filled?: boolean }) {
  const { t } = useTranslation();
  const theme = useTheme();
  return (
    <View
      accessible
      accessibilityRole="button"
      accessibilityLabel={`${label}, ${t("wallet.soon")}`}
      accessibilityState={{ disabled: true }}
      style={[
        styles.soon,
        filled
          ? { backgroundColor: theme.accent, opacity: 0.55 }
          : { borderWidth: 1.5, borderColor: "rgba(255,255,255,0.4)" },
      ]}
    >
      <Txt
        style={[
          styles.soonLabel,
          { color: filled ? theme.onAccent : theme.onHero },
          !filled && { opacity: 0.75 },
        ]}
        numberOfLines={1}
      >
        {label}
      </Txt>
      <View
        style={[
          styles.soonBadge,
          {
            backgroundColor: filled
              ? "rgba(58,42,0,0.14)"
              : "rgba(255,255,255,0.16)",
          },
        ]}
      >
        <Txt
          variant="micro"
          style={{ color: filled ? theme.onAccent : theme.onHero }}
        >
          {t("wallet.soon")}
        </Txt>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: radius.card + 4,
    padding: space.lg,
    gap: space.md,
    overflow: "hidden",
  },
  wave: { position: "absolute", left: 0, right: 0, bottom: 0 },
  cardTop: { flexDirection: "row", alignItems: "flex-start", gap: space.sm },
  cardIcon: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: "center",
    justifyContent: "center",
  },
  balance: {
    fontFamily: fonts.extrabold,
    fontSize: 38,
    lineHeight: 46,
    letterSpacing: -0.8,
  },
  currency: { fontFamily: fonts.extrabold, fontSize: 18 },
  cardActions: { flexDirection: "row", gap: 10 },
  soon: {
    flex: 1,
    height: 48,
    borderRadius: radius.pill,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    paddingHorizontal: space.sm,
  },
  soonLabel: { fontFamily: fonts.extrabold, fontSize: 14 },
  soonBadge: {
    borderRadius: radius.pill,
    paddingHorizontal: 7,
    paddingVertical: 1,
  },
  entry: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.sm,
    paddingVertical: space.sm,
    minHeight: 60,
  },
});
