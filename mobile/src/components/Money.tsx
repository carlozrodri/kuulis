import { useTranslation } from "react-i18next";
import {
  type StyleProp,
  StyleSheet,
  type TextStyle,
  View,
  type ViewStyle,
} from "react-native";

import { BadgePercent } from "@/components/icons";
import { Txt } from "@/components/ui";
import { formatFare } from "@/lib/ride";
import { formatVesPair, hasDiscount, vesEntries } from "@/lib/money";
import type { RidePromotion, VesAmount } from "@/lib/types";
import { radius, space, useTheme } from "@/theme";

/** "Bs 2.101,56 (BCV) · Bs 2.520,00 (Binance)" on one line; renders nothing without rates. */
export function VesLine({
  ves,
  style,
  align,
}: {
  ves: VesAmount | null | undefined;
  style?: StyleProp<TextStyle>;
  align?: TextStyle["textAlign"];
}) {
  const { t } = useTranslation();
  const text = formatVesPair(ves, {
    bcv: t("money.rate.bcv"),
    binance: t("money.rate.binance"),
  });
  if (!text) return null;
  return (
    <Txt variant="caption" color="muted" align={align} tabular style={style}>
      {text}
    </Txt>
  );
}

/** The bolívar equivalents as two tiles ("En Bs a tasa BCV / Bs 2.101,56"), as on the price screen. */
export function VesTiles({
  ves,
  style,
}: {
  ves: VesAmount | null | undefined;
  style?: StyleProp<ViewStyle>;
}) {
  const { t } = useTranslation();
  const theme = useTheme();
  const entries = vesEntries(ves);
  if (!entries.length) return null;
  return (
    <View style={[styles.tiles, style]}>
      {entries.map(({ source, amount }) => {
        const label = t("money.vesAt", { rate: t(`money.rate.${source}`) });
        return (
          <View
            key={source}
            accessible
            accessibilityLabel={`${label}: ${amount}`}
            style={[styles.tile, { backgroundColor: theme.background }]}
          >
            <Txt variant="caption" color="muted" numberOfLines={1}>
              {label}
            </Txt>
            <Txt variant="subtitle" tabular numberOfLines={1}>
              {amount}
            </Txt>
          </View>
        );
      })}
    </View>
  );
}

/**
 * "Incluye $0.60 de descuento · Bienvenida" under a price the passenger pays. Renders nothing without a
 * discount.
 */
export function DiscountNote({
  item,
  style,
}: {
  item: { discount?: string | null; promotion?: RidePromotion | null };
  style?: StyleProp<ViewStyle>;
}) {
  const { t } = useTranslation();
  const theme = useTheme();
  if (!hasDiscount(item)) return null;
  const discount = formatFare(item.discount);
  return (
    <View style={[styles.note, style]}>
      <BadgePercent
        size={16}
        color={theme.scheme === "dark" ? theme.accent : theme.warning}
        strokeWidth={2.2}
      />
      <Txt variant="caption" color="muted" style={{ flex: 1 }}>
        {item.promotion?.name
          ? t("money.discountNoteNamed", {
              discount,
              name: item.promotion.name,
            })
          : t("money.discountNote", { discount })}
      </Txt>
    </View>
  );
}

const styles = StyleSheet.create({
  tiles: { flexDirection: "row", gap: space.xs },
  tile: {
    flex: 1,
    gap: 2,
    borderRadius: radius.tile,
    paddingHorizontal: space.sm,
    paddingVertical: 10,
  },
  note: { flexDirection: "row", alignItems: "center", gap: 6 },
});
