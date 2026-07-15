import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { queryKeys } from "../lib/queryClient";

const META_STALE_TIME_MS = 10 * 60 * 1000;
const DASHBOARD_STALE_TIME_MS = 60 * 1000;
const HISTORY_STALE_TIME_MS = 2 * 60 * 1000;

async function fetchMetaOptions() {
  return api.get("/api/meta/options");
}

async function fetchDashboard(monthLabel) {
  return api.get(`/api/dashboard?month_label=${encodeURIComponent(monthLabel)}`);
}

async function fetchFinancialHistory(accountType) {
  const isPersonalAccount = accountType === "personal";
  const [expensesResponse, incomesResponse, sharedResponse] = await Promise.all([
    api.get("/api/expenses?month_label=Tutti"),
    api.get("/api/incomes?month_label=Tutti"),
    isPersonalAccount
      ? Promise.resolve({ items: [] })
      : api.get("/api/couple-balance?month_label=Tutti&status_filter=all"),
  ]);

  return {
    expenses: expensesResponse.items || [],
    incomes: incomesResponse.items || [],
    sharedExpenses: sharedResponse.items || [],
    expenseMonthOptions: expensesResponse.month_options || [],
    incomeMonthOptions: incomesResponse.month_options || [],
  };
}

export function useMetaOptionsQuery(options = {}) {
  return useQuery({
    queryKey: queryKeys.metaOptions(),
    queryFn: fetchMetaOptions,
    staleTime: META_STALE_TIME_MS,
    ...options,
  });
}

export function useDashboardQuery(monthLabel, options = {}) {
  return useQuery({
    queryKey: queryKeys.dashboard(monthLabel),
    queryFn: () => fetchDashboard(monthLabel),
    enabled: Boolean(monthLabel) && (options.enabled ?? true),
    staleTime: DASHBOARD_STALE_TIME_MS,
    placeholderData: (previousData) => previousData,
    ...options,
  });
}

export function useFinancialHistoryQuery(accountType, options = {}) {
  return useQuery({
    queryKey: queryKeys.financialHistory(accountType),
    queryFn: () => fetchFinancialHistory(accountType),
    enabled: Boolean(accountType) && (options.enabled ?? true),
    staleTime: HISTORY_STALE_TIME_MS,
    placeholderData: (previousData) => previousData,
    ...options,
  });
}
