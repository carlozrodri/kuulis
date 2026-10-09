/**
 * Pure wallet and subscription logic for phase 1D (docs/api/phase-1d.md): fee tiers, what is still owed,
 * amount inputs, transfer limits and recipient lookups. No React and no network, so it can be unit tested.
 * The API validates everything again.
 */
import { normalizePhone } from "./driver";
import { parseAmount } from "./money";
import type { Charge, FeeTier, SubscriptionSummary } from "./types";
import { isEmail } from "./validation";

type Amount = string | number | null | undefined;

/** Amounts as integer cents, so comparisons never suffer from floating point ("0.1" + "0.2"). */
export function toCents(value: Amount): number | null {
  const n = parseAmount(value);
  return n === null ? null : Math.round(n * 100);
}

const fromCents = (cents: number) => cents / 100;

// ── Fee tiers ──

export interface TierMatch {
  /** Earnings must be above this to fall in the tier. */
  from: number;
  /** Where the next tier starts; null for the top tier ("más de $600"). */
  to: number | null;
  fee: number;
}

/** Tiers sorted by `above`, skipping malformed rows. */
function sortedTiers(tiers: FeeTier[] | null | undefined) {
  return (tiers ?? [])
    .map((tier) => ({ above: toCents(tier.above), fee: toCents(tier.fee) }))
    .filter(
      (tier): tier is { above: number; fee: number } =>
        tier.above !== null && tier.fee !== null,
    )
    .sort((a, b) => a.above - b.above);
}

/**
 * The tier a month's earnings fall in: the one with the highest `above` that the earnings exceed. Null
 * without earnings (a month with no trips costs 0) or without a schedule.
 */
export function feeTierFor(
  tiers: FeeTier[] | null | undefined,
  earnings: Amount,
): TierMatch | null {
  const cents = toCents(earnings);
  if (cents === null || cents <= 0) return null;
  const sorted = sortedTiers(tiers);
  let index = -1;
  sorted.forEach((tier, i) => {
    if (cents > tier.above) index = i;
  });
  if (index < 0) return null;
  const next = sorted[index + 1];
  return {
    from: fromCents(sorted[index].above),
    to: next ? fromCents(next.above) : null,
    fee: fromCents(sorted[index].fee),
  };
}

/** The fee for some earnings under a schedule (0 without earnings). */
export function feeFor(
  tiers: FeeTier[] | null | undefined,
  earnings: Amount,
): number {
  return feeTierFor(tiers, earnings)?.fee ?? 0;
}

/** Tier bounds without useless decimals: 100 -> "$100", 99.5 -> "$99.50". */
export function formatTierBound(value: number): string {
  return Number.isInteger(value) ? `$${value}` : `$${value.toFixed(2)}`;
}

/** The parts of a tier to put in a sentence: {from: "$100", to: "$200"} or {from: "$600", to: null}. */
export function tierBounds(tier: TierMatch): {
  from: string;
  to: string | null;
} {
  return {
    from: formatTierBound(tier.from),
    to: tier.to === null ? null : formatTierBound(tier.to),
  };
}

// ── Charges and what is owed ──

/** Sum of the fees still pending. */
export function pendingTotal(charges: Charge[] | null | undefined): number {
  const cents = (charges ?? [])
    .filter((charge) => charge.status === "pending")
    .reduce((sum, charge) => sum + (toCents(charge.fee) ?? 0), 0);
  return fromCents(cents);
}

/** How much the driver still has to top up to cover `due` with `balance`: never negative. */
export function shortfall(balance: Amount, due: Amount): number {
  const missing = (toCents(due) ?? 0) - Math.max(0, toCents(balance) ?? 0);
  return missing > 0 ? fromCents(missing) : 0;
}

/** The earliest due date among pending charges (ISO), or null. */
export function nextDueAt(charges: Charge[] | null | undefined): string | null {
  const dates = (charges ?? [])
    .filter((charge) => charge.status === "pending" && charge.due_at)
    .map((charge) => charge.due_at as string)
    .filter((iso) => Number.isFinite(Date.parse(iso)))
    .sort((a, b) => Date.parse(a) - Date.parse(b));
  return dates[0] ?? null;
}

export type SubscriptionState =
  /** Past the grace week: cannot go online until paying. */
  | "blocked"
  /** A fee was charged and the balance did not cover it; still in the grace week. */
  | "pending"
  /** Inside the free months. */
  | "free"
  /** No completed trip yet: the free months have not started. */
  | "not_started"
  /** Paying normally: shows this month's estimated fee. */
  | "active";

export function subscriptionState(
  summary: SubscriptionSummary | null | undefined,
): SubscriptionState | null {
  if (!summary) return null;
  if (summary.blocked || summary.overdue) return "blocked";
  if (summary.pending?.some((charge) => charge.status === "pending"))
    return "pending";
  if (summary.in_free_period) return "free";
  if (!summary.free_until && (toCents(summary.earnings) ?? 0) <= 0)
    return "not_started";
  return "active";
}

// ── Months ──

/** "2026-10" -> {year: 2026, month: 10}; null when malformed. */
export function parseMonth(
  value: string | null | undefined,
): { year: number; month: number } | null {
  const match = value ? /^(\d{4})-(\d{2})$/.exec(value) : null;
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  return month >= 1 && month <= 12 ? { year, month } : null;
}

/** A local date in the middle of that month, safe to format with any timezone ("octubre"). */
export function monthDate(value: string | null | undefined): Date | null {
  const parsed = parseMonth(value);
  return parsed ? new Date(parsed.year, parsed.month - 1, 15, 12) : null;
}

/** The day a month's fee is charged: the 1st of the next month ("2026-10" -> 1 Nov 2026, local noon). */
export function chargeDate(value: string | null | undefined): Date | null {
  const parsed = parseMonth(value);
  return parsed ? new Date(parsed.year, parsed.month, 1, 12) : null;
}

// ── Inputs ──

/**
 * Keeps what can be typed in an amount field: digits and one decimal separator ("," becomes "."), with at
 * most two decimals. "5,509" -> "5.50", "$12" -> "12".
 */
export function sanitizeAmountInput(text: string): string {
  const cleaned = text.replace(/,/g, ".").replace(/[^\d.]/g, "");
  const [whole, ...rest] = cleaned.split(".");
  const integer = whole.replace(/^0+(?=\d)/, "").slice(0, 7);
  if (!rest.length) return integer;
  return `${integer || "0"}.${rest.join("").slice(0, 2)}`;
}

/** "5", "5.5", "5,50" -> 5.5; null when empty, invalid, zero or with more than two decimals. */
export function parseAmountInput(text: string): number | null {
  const value = text.trim().replace(",", ".");
  if (!/^\d+(\.\d{1,2})?$/.test(value)) return null;
  const n = Number(value);
  return Number.isFinite(n) && n > 0 ? n : null;
}

export type TransferAmountError =
  | "invalid"
  | "insufficient_balance"
  | "transfer_limit_exceeded";

/** Checks a transfer amount against the balance and what is left of the monthly limit. */
export function transferAmountError(
  text: string,
  limits: { balance: Amount; available?: Amount },
): TransferAmountError | null {
  const amount = parseAmountInput(text);
  if (amount === null) return "invalid";
  const cents = Math.round(amount * 100);
  if (cents > Math.max(0, toCents(limits.balance) ?? 0))
    return "insufficient_balance";
  const available = toCents(limits.available);
  if (available !== null && cents > Math.max(0, available))
    return "transfer_limit_exceeded";
  return null;
}

/** The most the driver can send right now: the lower of the balance and what is left this month. */
export function maxTransfer(limits: {
  balance: Amount;
  available?: Amount;
}): number {
  const balance = Math.max(0, toCents(limits.balance) ?? 0);
  const available = toCents(limits.available);
  return fromCents(
    available === null ? balance : Math.min(balance, Math.max(0, available)),
  );
}

/** Top-up notice amount: at least the configured minimum. */
export function topUpAmountError(
  text: string,
  minAmount: Amount,
): "invalid" | "below_minimum" | null {
  const amount = parseAmountInput(text);
  if (amount === null) return "invalid";
  const min = toCents(minAmount);
  return min !== null && Math.round(amount * 100) < min
    ? "below_minimum"
    : null;
}

export type RecipientQuery =
  | { type: "email"; value: string }
  | { type: "phone"; value: string };

/**
 * What the driver typed to find a recipient, as the API matches it (exactly): emails trimmed and
 * lowercased, phones in E.164 ("0412-123 4567" -> "+584121234567"). Null when it is neither.
 */
export function parseRecipientQuery(input: string): RecipientQuery | null {
  const trimmed = input.trim();
  if (!trimmed) return null;
  if (trimmed.includes("@")) {
    return isEmail(trimmed)
      ? { type: "email", value: trimmed.toLowerCase() }
      : null;
  }
  const phone = normalizePhone(trimmed);
  return phone ? { type: "phone", value: phone } : null;
}

/** Binance Pay IDs are 6–20 digits; spaces and dashes typed by the driver are dropped. */
export function normalizeBinancePayId(value: string): string {
  return value.replace(/[\s-]+/g, "");
}

export const isValidBinancePayId = (value: string) =>
  /^\d{6,20}$/.test(normalizeBinancePayId(value));

/** Binance order IDs are long numbers; keep digits and letters only. */
export function normalizeOrderReference(value: string): string {
  return value.replace(/[^0-9A-Za-z]/g, "").slice(0, 64);
}
