import { QueryClient } from "@tanstack/react-query";

const DEFAULT_STALE_TIME_MS = 30 * 1000;
const DEFAULT_GC_TIME_MS = 30 * 60 * 1000;

export const queryKeyRoots = {
  auth: ["auth"],
  metaOptions: ["meta-options"],
  dashboard: ["dashboard"],
  dashboardSummary: ["dashboard-summary"],
  financialHistory: ["financial-history"],
};

export const queryKeys = {
  auth: () => [...queryKeyRoots.auth, "me"],
  metaOptions: () => [...queryKeyRoots.metaOptions, "current"],
  dashboard: (monthLabel) => [...queryKeyRoots.dashboard, monthLabel || ""],
  dashboardSummary: (monthLabel, accountType) => [...queryKeyRoots.dashboardSummary, monthLabel || "", accountType || "unknown"],
  financialHistory: (accountType) => [...queryKeyRoots.financialHistory, accountType || "unknown"],
};

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: DEFAULT_STALE_TIME_MS,
      gcTime: DEFAULT_GC_TIME_MS,
      retry: 1,
      refetchOnMount: false,
      refetchOnReconnect: false,
      refetchOnWindowFocus: false,
    },
  },
});

export async function invalidateAppData(scope = "all") {
  const normalizedScope = String(scope || "all").toLowerCase();

  if (normalizedScope === "auth") {
    await queryClient.invalidateQueries({ queryKey: queryKeyRoots.auth });
    return;
  }

  if (normalizedScope === "profile") {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeyRoots.auth }),
      queryClient.invalidateQueries({ queryKey: queryKeyRoots.metaOptions }),
      queryClient.invalidateQueries({ queryKey: queryKeyRoots.dashboard }),
      queryClient.invalidateQueries({ queryKey: queryKeyRoots.dashboardSummary }),
      queryClient.invalidateQueries({ queryKey: queryKeyRoots.financialHistory }),
    ]);
    return;
  }

  if (normalizedScope === "expenses") {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeyRoots.metaOptions }),
      queryClient.invalidateQueries({ queryKey: queryKeyRoots.dashboard }),
      queryClient.invalidateQueries({ queryKey: queryKeyRoots.dashboardSummary }),
      queryClient.invalidateQueries({ queryKey: queryKeyRoots.financialHistory }),
    ]);
    return;
  }

  if (normalizedScope === "incomes") {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeyRoots.dashboard }),
      queryClient.invalidateQueries({ queryKey: queryKeyRoots.dashboardSummary }),
      queryClient.invalidateQueries({ queryKey: queryKeyRoots.financialHistory }),
    ]);
    return;
  }

  await Promise.all([
    queryClient.invalidateQueries(),
  ]);
}
