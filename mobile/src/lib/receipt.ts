import { formatVesPair } from "@/lib/money";
import { formatFare, shortAddress } from "@/lib/ride";
import type { RideReceipt } from "@/lib/types";

/**
 * Doc 23: text that goes with the shared receipt image (WhatsApp shows it above the link). Price in USD and in
 * bolívares at the rates frozen on the ride, the payment method agreed and the "no fiscal" line.
 */
export function receiptText(
  receipt: RideReceipt,
  t: (key: string, values?: Record<string, unknown>) => string,
  language: string,
): string {
  const date = new Date(receipt.completed_at).toLocaleString(language, {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
  const ves = formatVesPair(receipt.total_ves);
  return [
    t("rideActions.receiptTitle", { number: receipt.number }),
    date,
    `${shortAddress(receipt.pickup_address) || "—"} → ${shortAddress(receipt.dropoff_address) || "—"}`,
    `${t("rideActions.receiptTotal")}: ${formatFare(receipt.total)}${ves ? ` · ${ves}` : ""}`,
    `${t("ride.paymentMethod")}: ${t(`payment.${receipt.payment_method}`)}`,
    t("rideActions.receiptNonFiscal"),
  ].join("\n");
}
