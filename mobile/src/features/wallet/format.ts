import * as Clipboard from "expo-clipboard";
import { useTranslation } from "react-i18next";
import { Share } from "react-native";

import { showToast } from "@/components/Toast";
import { tick } from "@/lib/feedback";
import { formatFare } from "@/lib/ride";
import type { SubscriptionSummary, WalletEntry } from "@/lib/types";
import {
  chargeDate,
  feeTierFor,
  monthDate,
  tierBounds,
  type TierMatch,
} from "@/lib/wallet";

const capitalize = (text: string) =>
  text ? text.charAt(0).toLocaleUpperCase() + text.slice(1) : text;

const toDate = (value: string | Date | null | undefined) => {
  if (!value) return null;
  const date = value instanceof Date ? value : new Date(value);
  return Number.isFinite(date.getTime()) ? date : null;
};

/** Localized months and dates for the wallet ("octubre", "1 de noviembre", "14 ene"). */
export function useWalletFormat() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;

  /** "2026-10" -> "octubre". */
  const monthName = (month: string | null | undefined) =>
    monthDate(month)?.toLocaleDateString(lang, { month: "long" }) ?? "";
  /** "2026-10" -> "Octubre 2026" (list headers). */
  const monthTitle = (month: string | null | undefined) => {
    const date = monthDate(month);
    if (!date) return month ?? "";
    const name = capitalize(date.toLocaleDateString(lang, { month: "long" }));
    return `${name} ${date.getFullYear()}`;
  };
  /** "1 de noviembre" / "November 1". */
  const dayMonth = (value: string | Date | null | undefined) =>
    toDate(value)?.toLocaleDateString(lang, {
      day: "numeric",
      month: "long",
    }) ?? "";
  /** "14 ene" / "Jan 14". */
  const shortDate = (value: string | Date | null | undefined) =>
    toDate(value)
      ?.toLocaleDateString(lang, { day: "numeric", month: "short" })
      .replace(/\.$/, "") ?? "";

  /** "el tramo de $100 a $200" / "el tramo de más de $600". */
  const tierText = (tier: TierMatch) => {
    const bounds = tierBounds(tier);
    return bounds.to
      ? t("wallet.sub.tierRange", { from: bounds.from, to: bounds.to })
      : t("wallet.sub.tierTop", { from: bounds.from });
  };

  /**
   * "Ganaste $142.50 en octubre, así que te toca el tramo de $100 a $200." The tier is named only when the
   * current schedule gives the same fee (a closed month may have used an older schedule).
   */
  const earnedSentence = (
    summary: Pick<SubscriptionSummary, "tiers"> | null | undefined,
    charge: { month: string; earnings: string; fee: string },
  ) => {
    const tier = feeTierFor(summary?.tiers, charge.earnings);
    const values = {
      earnings: formatFare(charge.earnings),
      month: monthName(charge.month),
    };
    return tier && Math.abs(tier.fee - Number(charge.fee)) < 0.005
      ? t("wallet.sub.earnedTier", { ...values, tier: tierText(tier) })
      : t("wallet.sub.earned", values);
  };

  /** The day a month's fee is charged: "1 de noviembre". */
  const chargeDay = (month: string) => dayMonth(chargeDate(month));

  return {
    monthName,
    monthTitle,
    dayMonth,
    shortDate,
    tierText,
    earnedSentence,
    chargeDay,
  };
}

/** Title and subtitle of a wallet movement, from its kind and `details`. */
export function useEntryText() {
  const { t } = useTranslation();
  const { monthName } = useWalletFormat();
  return (entry: WalletEntry): { title: string; subtitle: string | null } => {
    const details = entry.details ?? {};
    const text = (key: string) => {
      const value = details[key];
      return typeof value === "string" && value.trim() ? value.trim() : null;
    };
    switch (entry.kind) {
      case "promo_credit": {
        const passenger = text("passenger_name");
        return {
          title: passenger
            ? t("wallet.kind.promo_credit.title", { name: passenger })
            : t("wallet.kind.promo_credit.titleNoName"),
          subtitle: entry.description
            ? t("wallet.kind.promo_credit.subtitleNamed", {
                name: entry.description,
              })
            : t("wallet.kind.promo_credit.subtitle"),
        };
      }
      case "top_up": {
        const reference = text("reference");
        return {
          title: t("wallet.kind.top_up.title"),
          subtitle: reference
            ? t("wallet.kind.top_up.reference", { reference })
            : null,
        };
      }
      case "transfer_in":
      case "transfer_out": {
        const name = text("counterpart_name");
        const note = text("note");
        const sent = entry.kind === "transfer_out";
        return {
          title: name
            ? t(
                sent
                  ? "wallet.kind.transfer_out.title"
                  : "wallet.kind.transfer_in.title",
                { name },
              )
            : t(
                sent
                  ? "wallet.kind.transfer_out.titleNoName"
                  : "wallet.kind.transfer_in.titleNoName",
              ),
          subtitle: note ? `“${note}”` : null,
        };
      }
      case "subscription_fee": {
        const month = monthName(text("month"));
        return {
          title: month
            ? t("wallet.kind.subscription_fee.title", { month })
            : t("wallet.kind.subscription_fee.titleNoMonth"),
          subtitle: null,
        };
      }
      case "adjustment":
        return {
          title: t("wallet.kind.adjustment.title"),
          subtitle: text("reason") ?? entry.description ?? null,
        };
      default:
        return { title: t("wallet.kind.other"), subtitle: null };
    }
  };
}

/** Copies text with a toast; falls back to the share sheet where the clipboard module is missing. */
export async function copyText(text: string, copiedMessage: string) {
  try {
    await Clipboard.setStringAsync(text);
    tick();
    showToast(copiedMessage, "success");
  } catch {
    await Share.share({ message: text }).catch(() => undefined);
  }
}
