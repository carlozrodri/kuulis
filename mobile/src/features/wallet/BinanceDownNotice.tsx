import { useTranslation } from "react-i18next";
import type { StyleProp, ViewStyle } from "react-native";

import { CirclePause } from "@/components/icons";
import { Notice } from "@/components/ui";
import type { TopUpInfo } from "@/lib/types";

/**
 * Doc 17: while reconciliation with Binance is failing (`manual_reason: "binance_down"`), top-ups are not
 * confirmed automatically: a person confirms them, so "Ya pagué" with the order ID matters.
 */
export function BinanceDownNotice({
  info,
  style,
}: {
  info: Pick<TopUpInfo, "manual_reason"> | null | undefined;
  style?: StyleProp<ViewStyle>;
}) {
  const { t } = useTranslation();
  if (info?.manual_reason !== "binance_down") return null;
  return (
    <Notice
      tone="warning"
      icon={CirclePause}
      title={t("topUp.binanceDown.title")}
      style={style}
    >
      {t("topUp.binanceDown.body")}
    </Notice>
  );
}
