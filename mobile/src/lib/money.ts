/**
 * Money helpers for phase 1C (docs/api/phase-1c.md): prices in USD with their bolívar equivalents at the
 * BCV and Binance rates, promotions and the driver wallet. Pure functions so they can be unit tested.
 */
import type { RateSource, VesAmount } from "./types";

type Amount = string | number | null | undefined;

/** "2.40" | 2.4 -> 2.4; null for missing or invalid amounts. */
export function parseAmount(value: Amount): number | null {
  if (value === null || value === undefined || value === "") return null;
  const n = typeof value === "number" ? value : Number.parseFloat(value);
  return Number.isFinite(n) ? n : null;
}

/** Groups thousands with "." and uses "," for decimals (Venezuelan style): 2101.56 -> "2.101,56". */
function venezuelanNumber(value: number): string {
  const cents = Math.round(Math.abs(value) * 100);
  const whole = Math.floor(cents / 100).toString();
  const decimals = String(cents % 100).padStart(2, "0");
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  return `${value < 0 && cents > 0 ? "-" : ""}${grouped},${decimals}`;
}

/** "2101.56" -> "Bs 2.101,56". Null when there is no amount (the rate was not available). */
export function formatVes(amount: Amount): string | null {
  const value = parseAmount(amount);
  return value === null ? null : `Bs ${venezuelanNumber(value)}`;
}

export const RATE_LABELS: Record<RateSource, string> = {
  bcv: "BCV",
  binance: "Binance",
};

/** The bolívar equivalents that exist, in display order (BCV first). */
export function vesEntries(
  ves: VesAmount | null | undefined,
): { source: RateSource; amount: string }[] {
  if (!ves) return [];
  return (["bcv", "binance"] as const).flatMap((source) => {
    const amount = formatVes(ves[source]);
    return amount ? [{ source, amount }] : [];
  });
}

/**
 * Both equivalents on one line: "Bs 2.101,56 (BCV) · Bs 2.520,00 (Binance)". A missing rate is skipped;
 * null when there is none.
 */
export function formatVesPair(
  ves: VesAmount | null | undefined,
  labels: Record<RateSource, string> = RATE_LABELS,
): string | null {
  const parts = vesEntries(ves).map(
    ({ source, amount }) => `${amount} (${labels[source]})`,
  );
  return parts.length ? parts.join(" · ") : null;
}

/** True when a quote, ride or offer carries a discount greater than zero. */
export function hasDiscount(
  item: { discount?: string | null } | null | undefined,
): boolean {
  return (parseAmount(item?.discount) ?? 0) > 0.004;
}

/**
 * What the passenger pays (and the driver collects): `total` when the API sends it, else the fare (servers
 * older than phase 1C have no promotions).
 */
export function amountToPay(item: {
  fare: string;
  total?: string | null;
}): string {
  return parseAmount(item.total) === null ? item.fare : (item.total as string);
}

/** Wallet amounts: "0.60" -> "+0.60", "-3.00" -> "−3.00" (typographic minus). */
export function formatSignedAmount(amount: Amount): string {
  const value = parseAmount(amount);
  if (value === null) return "—";
  const abs = Math.abs(value).toFixed(2);
  if (Math.round(Math.abs(value) * 100) === 0) return abs;
  return value > 0 ? `+${abs}` : `−${abs}`;
}

/** "2.5" -> "2.50" (wallet balances are shown with their currency next to them). */
export function formatAmount(amount: Amount): string {
  const value = parseAmount(amount);
  return value === null ? "—" : value.toFixed(2);
}

/** Promo codes are case and space insensitive on the server; this is what we show and send. */
export function normalizePromoCode(code: string): string {
  return code.replace(/\s+/g, "").toUpperCase();
}

export const PROMOTION_INVALID_REASONS = [
  "not_found",
  "not_started",
  "ended",
  "exhausted",
  "max_uses",
  "first_ride_only",
  "not_eligible",
] as const;

export type PromotionInvalidReason = (typeof PROMOTION_INVALID_REASONS)[number];

/** `details.reason` of a 400 promotion_invalid, or "not_eligible" when the server sends something else. */
export function promotionInvalidReason(
  details: unknown,
): PromotionInvalidReason {
  const reason = (details as { reason?: unknown } | null | undefined)?.reason;
  return PROMOTION_INVALID_REASONS.includes(reason as PromotionInvalidReason)
    ? (reason as PromotionInvalidReason)
    : "not_eligible";
}
