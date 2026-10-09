import { describe, expect, it } from "@jest/globals";

import {
  amountToPay,
  formatAmount,
  formatSignedAmount,
  formatVes,
  formatVesPair,
  hasDiscount,
  normalizePromoCode,
  parseAmount,
  promotionInvalidReason,
  vesEntries,
} from "@/lib/money";

describe("formatVes", () => {
  it("uses Venezuelan separators", () => {
    expect(formatVes("2101.56")).toBe("Bs 2.101,56");
    expect(formatVes("2520")).toBe("Bs 2.520,00");
    expect(formatVes(875.65)).toBe("Bs 875,65");
    expect(formatVes("1234567.891")).toBe("Bs 1.234.567,89");
    expect(formatVes("0")).toBe("Bs 0,00");
    expect(formatVes("999.995")).toBe("Bs 1.000,00");
  });

  it("handles negatives", () => {
    expect(formatVes("-1500.5")).toBe("Bs -1.500,50");
    expect(formatVes("-0.001")).toBe("Bs 0,00");
  });

  it("returns null without an amount", () => {
    expect(formatVes(null)).toBeNull();
    expect(formatVes(undefined)).toBeNull();
    expect(formatVes("")).toBeNull();
    expect(formatVes("abc")).toBeNull();
  });
});

describe("formatVesPair", () => {
  it("shows both rates", () => {
    expect(formatVesPair({ bcv: "2101.56", binance: "2520.00" })).toBe(
      "Bs 2.101,56 (BCV) · Bs 2.520,00 (Binance)",
    );
  });

  it("skips a missing rate", () => {
    expect(formatVesPair({ bcv: null, binance: "2520.00" })).toBe(
      "Bs 2.520,00 (Binance)",
    );
    expect(formatVesPair({ bcv: "2101.56", binance: null })).toBe(
      "Bs 2.101,56 (BCV)",
    );
  });

  it("returns null when there is nothing to show", () => {
    expect(formatVesPair({ bcv: null, binance: null })).toBeNull();
    expect(formatVesPair(null)).toBeNull();
    expect(formatVesPair(undefined)).toBeNull();
  });

  it("accepts custom labels", () => {
    expect(
      formatVesPair(
        { bcv: "10", binance: "12" },
        { bcv: "oficial", binance: "P2P" },
      ),
    ).toBe("Bs 10,00 (oficial) · Bs 12,00 (P2P)");
  });

  it("lists entries in BCV, Binance order", () => {
    expect(vesEntries({ binance: "2", bcv: "1" })).toEqual([
      { source: "bcv", amount: "Bs 1,00" },
      { source: "binance", amount: "Bs 2,00" },
    ]);
  });
});

describe("promotions", () => {
  it("detects a discount", () => {
    expect(hasDiscount({ discount: "0.60" })).toBe(true);
    expect(hasDiscount({ discount: "0.00" })).toBe(false);
    expect(hasDiscount({})).toBe(false);
    expect(hasDiscount(null)).toBe(false);
  });

  it("pays the total, falling back to the fare on older servers", () => {
    expect(amountToPay({ fare: "3.00", total: "2.40" })).toBe("2.40");
    expect(amountToPay({ fare: "3.00", total: "0.00" })).toBe("0.00");
    expect(amountToPay({ fare: "3.00" })).toBe("3.00");
    expect(amountToPay({ fare: "3.00", total: null })).toBe("3.00");
  });

  it("normalizes codes", () => {
    expect(normalizePromoCode(" ho la ")).toBe("HOLA");
  });

  it("reads the promotion_invalid reason", () => {
    expect(promotionInvalidReason({ reason: "exhausted" })).toBe("exhausted");
    expect(promotionInvalidReason({ reason: "weird" })).toBe("not_eligible");
    expect(promotionInvalidReason(undefined)).toBe("not_eligible");
  });
});

describe("wallet amounts", () => {
  it("signs amounts", () => {
    expect(formatSignedAmount("0.60")).toBe("+0.60");
    expect(formatSignedAmount("-3")).toBe("−3.00");
    expect(formatSignedAmount("0")).toBe("0.00");
    expect(formatSignedAmount(null)).toBe("—");
  });

  it("formats balances", () => {
    expect(formatAmount("2.5")).toBe("2.50");
    expect(formatAmount(undefined)).toBe("—");
    expect(parseAmount(" 1.5")).toBe(1.5);
  });
});
