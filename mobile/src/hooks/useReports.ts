import {
  type QueryClient,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { Page, Report, ReportInput } from "@/lib/types";

/** "Mis reportes" (phase 1E): the reports this user made and their answers. */
export const reportKeys = {
  all: ["reports"] as const,
  mine: ["reports", "me"] as const,
  detail: (id: string) => ["reports", "me", id] as const,
};

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
