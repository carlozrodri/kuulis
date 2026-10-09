import {
  type QueryClient,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { rideKeys } from "@/hooks/useRides";
import { ApiError, api } from "@/lib/api";
import type {
  Charge,
  Page,
  Recipient,
  SubscriptionSummary,
  TopUp,
  TopUpInfo,
  Wallet,
  WalletEntry,
} from "@/lib/types";

/** Driver wallet: balance and movements (1C), top-ups, transfers and the monthly subscription (1D). */
export const walletKeys = {
  all: ["wallet"] as const,
  me: ["wallet", "me"] as const,
  entries: ["wallet", "me", "entries"] as const,
  topUps: ["wallet", "me", "top-ups"] as const,
  subscription: ["wallet", "me", "subscription"] as const,
  charges: ["wallet", "me", "charges"] as const,
  topUpInfo: ["wallet", "top-up-info"] as const,
};

const PAGE_SIZE = 20;

/**
 * Wallet pushes carry {type: "wallet" | "wallet_*" | "wallet.*", ...}; subscription pushes (fee charged, due
 * tomorrow, blocked) carry {type: "subscription" | "subscription_*"}. Promo credits also count.
 */
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
      (typeValue.startsWith("wallet") ||
        typeValue.startsWith("subscription") ||
        typeValue === "promo_credit")) ||
    kind === "promo_credit"
  );
}

/** Subscription pushes can block or unblock the driver, so the online state is re-read too. */
export function isSubscriptionNotification(payload: unknown): boolean {
  const record = payload as {
    type?: unknown;
    data?: { type?: unknown };
  } | null;
  const typeValue = record?.type ?? record?.data?.type;
  return typeof typeValue === "string" && typeValue.startsWith("subscription");
}

/** Everything that depends on money moving: wallet, top-ups, fees and whether the driver may go online. */
export function refreshWallet(queryClient: QueryClient) {
  void queryClient.invalidateQueries({ queryKey: walletKeys.all });
}

/** 403 subscription_overdue from going online. */
export const isSubscriptionOverdue = (error: unknown) =>
  error instanceof ApiError && error.code === "subscription_overdue";

function nextOffset<T>(last: Page<T>) {
  return last.offset + last.items.length < last.total
    ? last.offset + last.items.length
    : undefined;
}

// ── Queries ──

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
    getNextPageParam: nextOffset,
    enabled,
    staleTime: 30_000,
  });
}

/** Where to send USDT (Kuulis' Binance Pay ID), the minimum and whether payments are matched automatically. */
export function useTopUpInfo(enabled = true) {
  return useQuery({
    queryKey: walletKeys.topUpInfo,
    queryFn: () => api<TopUpInfo>("/wallet/top-up-info"),
    enabled,
    staleTime: 5 * 60_000,
  });
}

export function useTopUps(enabled = true) {
  return useInfiniteQuery({
    queryKey: walletKeys.topUps,
    initialPageParam: 0,
    queryFn: ({ pageParam }) =>
      api<Page<TopUp>>("/wallet/me/top-ups", {
        query: { limit: PAGE_SIZE, offset: pageParam },
      }),
    getNextPageParam: nextOffset,
    enabled,
    staleTime: 30_000,
  });
}

/** This month's earnings, the estimated fee, the free period and any pending charge. */
export function useSubscription(enabled = true) {
  return useQuery({
    queryKey: walletKeys.subscription,
    queryFn: () => api<SubscriptionSummary>("/wallet/me/subscription"),
    enabled,
    staleTime: 60_000,
  });
}

export function useCharges(enabled = true) {
  return useInfiniteQuery({
    queryKey: walletKeys.charges,
    initialPageParam: 0,
    queryFn: ({ pageParam }) =>
      api<Page<Charge>>("/wallet/me/charges", {
        query: { limit: PAGE_SIZE, offset: pageParam },
      }),
    getNextPageParam: nextOffset,
    enabled,
    staleTime: 60_000,
  });
}

// ── Mutations ──

/** PUT /wallet/me/binance: returns the wallet, which replaces the cached one. */
export function useSaveBinancePayId() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (binancePayId: string) =>
      api<Wallet>("/wallet/me/binance", {
        method: "PUT",
        body: { binance_pay_id: binancePayId },
      }),
    onSuccess: (wallet) => {
      if (wallet && typeof wallet === "object" && "balance" in wallet)
        queryClient.setQueryData(walletKeys.me, wallet);
      else void queryClient.invalidateQueries({ queryKey: walletKeys.me });
    },
  });
}

/** POST /wallet/me/top-ups: "Ya pagué" (amount and the optional Binance order ID). */
export function useNotifyTopUp() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { amount: string; reference?: string }) =>
      api<TopUp>("/wallet/me/top-ups", { method: "POST", body: input }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: walletKeys.topUps });
      // With automatic matching the payment may already be credited.
      void queryClient.invalidateQueries({ queryKey: walletKeys.me });
    },
  });
}

/** GET /wallet/recipients?q=: exact email or phone; 404 recipient_not_found. */
export function useFindRecipient() {
  return useMutation({
    mutationFn: (q: string) =>
      api<Recipient>("/wallet/recipients", { query: { q } }),
  });
}

export function useTransfer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      to_user_id: string;
      amount: string;
      note?: string;
    }) =>
      api<WalletEntry>("/wallet/me/transfers", { method: "POST", body: input }),
    onSuccess: () => refreshWallet(queryClient),
    // A rejected transfer means our balance or limit was stale.
    onError: () =>
      void queryClient.invalidateQueries({ queryKey: walletKeys.me }),
  });
}

/** After a subscription push or a 403 subscription_overdue: re-read the fee state and the online state. */
export function refreshSubscription(queryClient: QueryClient) {
  void queryClient.invalidateQueries({ queryKey: walletKeys.subscription });
  void queryClient.invalidateQueries({ queryKey: walletKeys.charges });
  void queryClient.invalidateQueries({ queryKey: rideKeys.driverState });
}
