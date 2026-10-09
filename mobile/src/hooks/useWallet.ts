import { useInfiniteQuery, useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { Page, Wallet, WalletEntry } from "@/lib/types";

/** Read-only driver wallet (phase 1C): balance and movements. */
export const walletKeys = {
  all: ["wallet"] as const,
  me: ["wallet", "me"] as const,
  entries: ["wallet", "me", "entries"] as const,
};

const PAGE_SIZE = 20;

/** Wallet pushes carry {type: "wallet_*" | "wallet.*", ...} (assumed; promo credits also count). */
export function isWalletNotification(payload: unknown): boolean {
  const record = payload as {
    type?: unknown;
    kind?: unknown;
    data?: { type?: unknown; kind?: unknown };
  } | null;
  const typeValue = record?.type ?? record?.data?.type;
  const kind = record?.kind ?? record?.data?.kind;
  return (
    (typeof typeValue === "string" &&
      (typeValue.startsWith("wallet") || typeValue === "promo_credit")) ||
    kind === "promo_credit"
  );
}

export function useWallet(enabled = true) {
  return useQuery({
    queryKey: walletKeys.me,
    queryFn: () => api<Wallet>("/wallet/me"),
    enabled,
    staleTime: 30_000,
  });
}

export function useWalletEntries(enabled = true) {
  return useInfiniteQuery({
    queryKey: walletKeys.entries,
    initialPageParam: 0,
    queryFn: ({ pageParam }) =>
      api<Page<WalletEntry>>("/wallet/me/entries", {
        query: { limit: PAGE_SIZE, offset: pageParam },
      }),
    getNextPageParam: (last) =>
      last.offset + last.items.length < last.total
        ? last.offset + last.items.length
        : undefined,
    enabled,
    staleTime: 30_000,
  });
}
