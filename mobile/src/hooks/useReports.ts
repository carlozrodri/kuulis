import {
  type QueryClient,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { ApiError, api } from "@/lib/api";
import { appendMessage, fallbackMessages } from "@/lib/support";
import type {
  Page,
  Report,
  ReportInput,
  ReportMessage,
} from "@/lib/types";

/** "Mis conversaciones" (phase 1E, doc 13): the reports this user made and their messages. */
export const reportKeys = {
  all: ["reports"] as const,
  mine: ["reports", "me"] as const,
  detail: (id: string) => ["reports", "me", id] as const,
  messages: (id: string) => ["reports", "me", id, "messages"] as const,
};

type ReportPages = { pages: Page<Report>[]; pageParams: unknown[] };

/** Writes a report snapshot in its detail and in the list. */
export function applyReport(queryClient: QueryClient, report: Report) {
  queryClient.setQueryData(reportKeys.detail(report.id), report);
  queryClient.setQueryData<ReportPages>(reportKeys.mine, (data) =>
    data
      ? {
          ...data,
          pages: data.pages.map((page) => ({
            ...page,
            items: page.items.map((item) =>
              item.id === report.id ? report : item,
            ),
          })),
        }
      : data,
  );
}

/** Opening the thread marks it seen: drop the unread dot right away (the API did the same). */
function markSeen(queryClient: QueryClient, id: string) {
  const patch = (report: Report | undefined) =>
    report && report.unread ? { ...report, unread: false } : report;
  queryClient.setQueryData<Report>(reportKeys.detail(id), patch);
  queryClient.setQueryData<ReportPages>(reportKeys.mine, (data) =>
    data
      ? {
          ...data,
          pages: data.pages.map((page) => ({
            ...page,
            items: page.items.map((item) =>
              item.id === id ? (patch(item) as Report) : item,
            ),
          })),
        }
      : data,
  );
}

const PAGE_SIZE = 20;

/** After a report push (resolved or dismissed): re-read the list and any open detail. */
export function refreshReports(queryClient: QueryClient) {
  void queryClient.invalidateQueries({ queryKey: reportKeys.all });
}

/** GET /reports/me, newest first. */
export function useMyReports(enabled = true) {
  return useInfiniteQuery({
    queryKey: reportKeys.mine,
    initialPageParam: 0,
    queryFn: ({ pageParam }) =>
      api<Page<Report>>("/reports/me", {
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

/** GET /reports/me/{id}, seeded from the list while it loads. */
export function useReport(id: string | undefined) {
  const queryClient = useQueryClient();
  return useQuery({
    queryKey: reportKeys.detail(id ?? ""),
    queryFn: () => api<Report>(`/reports/me/${id}`),
    enabled: !!id,
    initialData: () => {
      const pages = queryClient.getQueryData<{ pages: Page<Report>[] }>(
        reportKeys.mine,
      )?.pages;
      return pages?.flatMap((page) => page.items).find((r) => r.id === id);
    },
    initialDataUpdatedAt: () =>
      queryClient.getQueryState(reportKeys.mine)?.dataUpdatedAt,
    staleTime: 30_000,
  });
}

/**
 * GET /reports/me/{id}/messages, oldest first (marks the conversation seen). Polls while the thread is on
 * screen; pushes refresh it too. Servers without the endpoint (404) show the description and the answer.
 */
export function useReportMessages(id: string | undefined, report: Report | undefined) {
  const queryClient = useQueryClient();
  return useQuery({
    queryKey: reportKeys.messages(id ?? ""),
    queryFn: async () => {
      try {
        const messages = await api<ReportMessage[]>(
          `/reports/me/${id}/messages`,
        );
        markSeen(queryClient, id!);
        return { messages, legacy: false };
      } catch (error) {
        if (error instanceof ApiError && error.status === 404 && report)
          return { messages: fallbackMessages(report), legacy: true };
        throw error;
      }
    },
    enabled: !!id,
    refetchInterval: 30_000,
    staleTime: 5_000,
  });
}

/** POST /reports/me/{id}/messages. */
export function useSendReportMessage(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { body: string; attachments?: string[] }) =>
      api<ReportMessage>(`/reports/me/${id}/messages`, {
        method: "POST",
        body: input,
      }),
    onSuccess: (message) => {
      queryClient.setQueryData<{ messages: ReportMessage[]; legacy: boolean }>(
        reportKeys.messages(id),
        (data) => ({
          messages: appendMessage(data?.messages, message),
          legacy: false,
        }),
      );
      // waiting_on, status (a recent resolved ticket reopens) and the list order change.
      void queryClient.invalidateQueries({ queryKey: reportKeys.detail(id), exact: true });
      void queryClient.invalidateQueries({ queryKey: reportKeys.mine, exact: true });
    },
  });
}

/** POST /reports/me/{id}/csat: 1 to 5 stars and an optional comment once the conversation is closed. */
export function useRateReport(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { score: number; comment?: string }) =>
      api<Report>(`/reports/me/${id}/csat`, { method: "POST", body: input }),
    onSuccess: (report) => applyReport(queryClient, report),
  });
}

/** POST /reports. */
export function useCreateReport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: ReportInput) =>
      api<Report>("/reports", { method: "POST", body: input }),
    onSuccess: (report) => {
      if (report?.id)
        queryClient.setQueryData(reportKeys.detail(report.id), report);
      void queryClient.invalidateQueries({ queryKey: reportKeys.mine });
    },
  });
}
