import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Dialog } from "../components/Dialog";
import { FeedbackBanner } from "../components/FeedbackBanner";
import { MonthNavigation } from "../components/MonthNavigation";
import { StatusView } from "../components/StatusView";
import { DateChoice } from "../components/TransactionFormControls";
import { useAuth } from "../context/AuthContext";
import { api, notifyAppDataChanged } from "../lib/api";
import {
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

const defaultFilters = {
  month_label: getCurrentMonthLabel(),
  category: "Tutte",
  payer: "Tutti",
  expense_type: "Tutte",
  search: "",
  sort: "date_desc",
};

const DEFAULT_CATEGORY_OPTIONS = [
  "Casa",
  "Spesa",
  "Trasporti",
  "Ristoranti",
  "Abbonamenti",
  "Svago",
  "Regali",
  "Cura persona",
  "Altro",
];

const AVATAR_ACCENT_COLORS = {
  1: "#8b5cf6",
  2: "#facc15",
  3: "#22c55e",
  4: "#38bdf8",
  5: "#f97316",
  6: "#ec4899",
  7: "#14b8a6",
  8: "#a855f7",
  9: "#63d72a",
};

export function ExpensesPage() {
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [data, setData] = useState(null);
  const [meta, setMeta] = useState(null);
  const [incomeTotal, setIncomeTotal] = useState(0);
  const [filters, setFilters] = useState(() => buildFiltersFromSearchParams(searchParams));
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState("");
  const [feedbackType, setFeedbackType] = useState("success");
  const [dialogMode, setDialogMode] = useState(null);
  const [selectedExpenseId, setSelectedExpenseId] = useState(null);
  const [pendingDeleteExpenseId, setPendingDeleteExpenseId] = useState(null);
  const [selectedIds, setSelectedIds] = useState([]);
  const [isDeleteMode, setIsDeleteMode] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState("");
  const [form, setForm] = useState(createDefaultExpenseForm(""));
  const [isFilterPanelOpen, setIsFilterPanelOpen] = useState(false);
  const [selectedCategoryPreview, setSelectedCategoryPreview] = useState(null);
  const summaryMode = searchParams.get("summary");

  const payerOptions = useMemo(() => {
    const usernames = meta?.usernames || [];
    if (!user?.username || usernames.includes(user.username)) {
      return usernames;
    }
    return [user.username, ...usernames];
  }, [meta, user]);
  const categoryOptions = useMemo(() => meta?.category_items || meta?.categories || [], [meta]);
  const splitOptions = meta?.split_options || ["equal", "custom"];
  const expenseTypeOptions = meta?.expense_types || ["Personale", "Condivisa"];
  const monthOptions = useMemo(() => data?.month_options || ["Tutti"], [data]);
  const sortOptions = data?.filters?.sort_options || [
    { value: "date_desc", label: "Data piu recente" },
    { value: "amount_desc", label: "Importo maggiore" },
    { value: "amount_asc", label: "Importo minore" },
  ];
  const expenseItems = data?.items || [];
  const selectedCategoryExpenses = useMemo(() => {
    if (!selectedCategoryPreview?.label) {
      return [];
    }
    const normalizedCategory = normalizeCategoryName(selectedCategoryPreview.label);
    return expenseItems
      .filter((item) => normalizeCategoryName(item.category || "Altro") === normalizedCategory)
      .map((item) => ({
        ...item,
        userShare: getCurrentUserExpenseShare(item, user?.username || ""),
      }));
  }, [expenseItems, selectedCategoryPreview, user]);
  const selectedCategoryTotal = useMemo(
    () => selectedCategoryExpenses.reduce((sum, item) => sum + Number(item.userShare || 0), 0),
    [selectedCategoryExpenses],
  );

  useEffect(() => {
    if (!user?.username) {
      return;
    }
    setForm(createDefaultExpenseForm(user.username, user.account_type));
  }, [user]);

  useEffect(() => {
    const nextFilters = buildFiltersFromSearchParams(searchParams);
    setFilters((current) => (sameObject(current, nextFilters) ? current : nextFilters));
  }, [searchParams]);

  useEffect(() => {
    if (searchParams.get("action") !== "new") {
      return;
    }
    openCreateDialog(searchParams.get("date") || "");
    const next = new URLSearchParams(searchParams);
    next.delete("action");
    next.delete("date");
    setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams, user]);

  useEffect(() => {
    if (!feedback) {
      return undefined;
    }
    const timerId = window.setTimeout(() => {
      setFeedback("");
    }, 5000);
    return () => window.clearTimeout(timerId);
  }, [feedback]);

  useEffect(() => {
    let isMounted = true;

    async function bootstrap() {
      setIsLoading(true);
      setError("");
      try {
        const [expensesResponse, metaOptionsResponse, categoriesResponse, incomesResponse] = await Promise.all([
          fetchExpenses(filters),
          api.get("/api/meta/options"),
          api.get(`/api/categories?month_label=${encodeURIComponent(filters.month_label)}`),
          fetchIncomeSummary(filters),
        ]);
        if (isMounted) {
          setData(expensesResponse);
          setMeta({
            ...metaOptionsResponse,
            categories: categoriesResponse.items || [],
            category_items: categoriesResponse.category_items || [],
          });
          setIncomeTotal(Number(incomesResponse.summary?.total_amount || 0));
        }
      } catch (requestError) {
        if (isMounted) {
          setError(requestError.message || "Impossibile caricare le spese.");
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    bootstrap();

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    if (!data) {
      return;
    }
    let isMounted = true;

    async function refreshList() {
      try {
        const [response, incomesResponse] = await Promise.all([
          fetchExpenses(filters),
          fetchIncomeSummary(filters),
        ]);
        if (isMounted) {
          setData(response);
          setIncomeTotal(Number(incomesResponse.summary?.total_amount || 0));
          setSelectedIds([]);
          const categoriesResponse = await api.get(`/api/categories?month_label=${encodeURIComponent(filters.month_label)}`);
          setMeta((current) => ({
            ...(current || {}),
            categories: categoriesResponse.items || [],
            category_items: categoriesResponse.category_items || [],
          }));
        }
      } catch (requestError) {
        if (isMounted) {
          setError(requestError.message || "Impossibile aggiornare le spese.");
        }
      }
    }

    refreshList();

    return () => {
      isMounted = false;
    };
  }, [filters]);

  if (isLoading) {
    return <StatusView title="Spese" message="Sto caricando le spese dal backend." />;
  }

  if (error) {
    return <StatusView title="Errore spese" message={error} />;
  }

  if (!data) {
    return <StatusView title="Spese" message="Nessun dato disponibile." />;
  }

  const totalExpenses = Number(data.summary?.total_amount || 0);
  const visibleIds = data.items.map((item) => item.id);
  const allVisibleSelected = visibleIds.length > 0 && selectedIds.length === visibleIds.length;
  const userAccentMap = buildUserAccentMap(meta?.couple_members || [], user);
  const categoryDistribution = buildExpenseCategoryDistribution(data.items, user?.username || "");

  return (
    <section className="page expense-workspace">
      <section className="expenses-premium-top" aria-label="Riepilogo uscite">
        <div className="expenses-premium-top__main">
          <div className="expenses-premium-top__copy">
            <span className="expenses-premium-top__eyebrow">USCITE</span>
            <button type="button" className="expenses-title-reset" onClick={resetExpenseFilters}>
              Uscite
            </button>
            <p>Riepilogo spese</p>
            <div className="expenses-premium-top__actions">
              <button type="button" className="primary-button expenses-create-button" onClick={() => openCreateDialog()}>
                + Nuova spesa
              </button>
              {filters.month_label ? (
                <MonthNavigation
                  label={formatMonthHeading(filters.month_label)}
                  onPrevious={() => shiftSelectedMonth(-1)}
                  onNext={() => shiftSelectedMonth(1)}
                />
              ) : null}
            </div>
          </div>

          <div className="expenses-premium-metrics" aria-label="Metriche uscite">
            <ExpenseMetricCard
              icon="trend"
              tone="expense"
              label="Spesa totale"
              value={formatCurrency(totalExpenses)}
              detail={`${data.count || 0} movimenti nel periodo`}
            />
          </div>

          <ExpenseCategoryDonut
            entries={categoryDistribution}
            total={totalExpenses}
            onCategoryClick={(entry) => openCategoryInExpenses((entry?.payload || entry)?.label)}
          />
        </div>

        <section className="expenses-search-bar" aria-label="Ricerca e filtri uscite">
          <input
            type="search"
            value={filters.search}
            onChange={(event) => updateFilter("search", event.target.value)}
            placeholder="Cerca spesa..."
          />
          <button
            type="button"
            className={`expenses-filter-icon-button${isFilterPanelOpen ? " active" : ""}`}
            aria-label="Apri filtri avanzati"
            aria-expanded={isFilterPanelOpen}
            onClick={() => setIsFilterPanelOpen((current) => !current)}
          >
            <FilterIcon />
          </button>

          {isFilterPanelOpen ? (
            <section className="expenses-sort-menu" aria-label="Ordinamento uscite">
              <span>Ordina per</span>
              {sortOptions.map((option) => {
                const isActive = filters.sort === option.value;
                return (
                  <button
                    key={option.value}
                    type="button"
                    className={isActive ? "active" : ""}
                    onClick={() => {
                      updateFilter("sort", option.value);
                      setIsFilterPanelOpen(false);
                    }}
                  >
                    <CheckIcon visible={isActive} />
                    {option.label}
                  </button>
                );
              })}
            </section>
          ) : null}
        </section>
      </section>

      <FeedbackBanner type={feedbackType} message={feedback} />

      {isDeleteMode ? (
        <section className="expenses-selection-bar" aria-label="Azioni selezione">
          <button
            type="button"
            className="secondary-button"
            onClick={() => setSelectedIds(allVisibleSelected ? [] : visibleIds)}
          >
            {allVisibleSelected ? "Deseleziona tutte" : "Seleziona tutte"}
          </button>
          <span>{selectedIds.length} selezionate</span>
        </section>
      ) : null}

      <ExpenseFeed
        items={data.items}
        currentUsername={user?.username || ""}
        selectedIds={selectedIds}
        isDeleteMode={isDeleteMode}
        userAccentMap={userAccentMap}
        onSelect={toggleSelectedId}
        onEdit={openEditDialog}
        onDelete={openDeleteConfirmDialog}
      />

      {dialogMode === "create" || dialogMode === "edit" ? (
        <Dialog
          title={dialogMode === "create" ? "Nuova spesa" : "Modifica spesa"}
          subtitle={dialogMode === "create" ? "Aggiungi una nuova spesa e gestisci la ripartizione." : "Aggiorna i dettagli della spesa."}
          icon={<ExpenseDialogIcon />}
          className="expense-dialog"
          onClose={closeDialog}
          footer={
            <>
              <button type="button" className="secondary-button" onClick={closeDialog}>
                Annulla
              </button>
              <button
                type="button"
                className="primary-button"
                onClick={handleSubmitExpense}
                disabled={isSubmitting}
              >
                {isSubmitting ? "Salvataggio..." : dialogMode === "create" ? "Crea spesa" : "Salva modifiche"}
              </button>
            </>
          }
        >
          <ExpenseForm
            form={form}
            setForm={setForm}
            formError={formError}
            payerOptions={payerOptions}
            categoryOptions={categoryOptions}
            splitOptions={splitOptions}
            expenseTypeOptions={expenseTypeOptions}
            currentUsername={user?.username || ""}
            monthLabel={filters.month_label}
            onCategoryCreated={handleCategoryCreated}
            onCategoryDeleted={handleCategoryDeleted}
          />
        </Dialog>
      ) : null}

      {selectedCategoryPreview ? (
        <Dialog
          title={`Anteprima ${selectedCategoryPreview.label}`}
          onClose={() => setSelectedCategoryPreview(null)}
          footer={(
            <>
              <button type="button" className="secondary-button" onClick={() => setSelectedCategoryPreview(null)}>
                Chiudi
              </button>
              <button
                type="button"
                className="primary-button"
                onClick={() => openCategoryInExpenses(selectedCategoryPreview.label)}
              >
                Vedi in Uscite
              </button>
            </>
          )}
        >
          <div className="category-preview-card">
            <div className="category-preview-head">
              <span className="category-preview-icon" style={{ "--category-color": selectedCategoryPreview.color }}>
                <CategoryIcon label={selectedCategoryPreview.label} />
              </span>
              <div>
                <p className="eyebrow">Totale categoria</p>
                <h2>{formatCurrency(selectedCategoryTotal)}</h2>
                <span>{selectedCategoryExpenses.length} spese nel periodo</span>
              </div>
            </div>

            <div className="category-preview-list">
              {selectedCategoryExpenses.length ? (
                selectedCategoryExpenses.map((expense) => (
                  <button
                    key={expense.id}
                    type="button"
                    className="category-preview-row"
                    onClick={() => openCategoryInExpenses(selectedCategoryPreview.label)}
                  >
                    <div>
                      <strong>{expense.name || expense.description || "Spesa"}</strong>
                      <span>{formatShortDayLabel(expense.expense_date)} · {expense.paid_by || "-"} · {expense.expense_type || "Spesa"}</span>
                    </div>
                    <strong>{formatCurrency(expense.userShare)}</strong>
                  </button>
                ))
              ) : (
                <p>Nessuna spesa trovata per questa categoria.</p>
              )}
            </div>
          </div>
        </Dialog>
      ) : null}

      {pendingDeleteExpenseId ? (
        <Dialog
          title="Eliminare spesa?"
          onClose={closeDeleteConfirmDialog}
          footer={(
            <>
              <button type="button" className="secondary-button" onClick={closeDeleteConfirmDialog}>
                Indietro
              </button>
              <button type="button" className="secondary-button" onClick={handleSelectMoreForDelete}>
                Seleziona altre
              </button>
              <button
                type="button"
                className="danger-soft-button"
                onClick={handleConfirmDeleteExpense}
                disabled={isSubmitting}
              >
                {isSubmitting ? "Eliminazione..." : "Si, elimina"}
              </button>
            </>
          )}
        >
          <div className="expenses-delete-confirm">
            <p>Sei sicuro di voler eliminare questa spesa?</p>
            <span>Vuoi selezionare altre spese prima di eliminare?</span>
          </div>
        </Dialog>
      ) : null}
    </section>
  );

  function handleCategoryCreated(category) {
    const categoryName = getCategoryName(category);
    setMeta((current) => {
      const existingNames = (current.categories || []).map(getCategoryName);
      if (!current || existingNames.some((item) => item.toLowerCase() === categoryName.toLowerCase())) {
        return current;
      }
      return {
        ...current,
        categories: [...(current.categories || []), categoryName],
        category_items: category && typeof category !== "string" ? [...(current.category_items || []), category] : current.category_items,
      };
    });
  }

  function handleCategoryDeleted(categoryName) {
    setMeta((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        categories: (current.categories || []).filter((item) => getCategoryName(item).toLowerCase() !== categoryName.toLowerCase()),
        category_items: (current.category_items || []).filter((item) => getCategoryName(item).toLowerCase() !== categoryName.toLowerCase()),
      };
    });
  }

  async function fetchExpenses(activeFilters) {
    const params = new URLSearchParams(activeFilters);
    return api.get(`/api/expenses?${params.toString()}`);
  }

  async function fetchIncomeSummary(activeFilters) {
    const params = new URLSearchParams({ month_label: activeFilters.month_label || "Tutti" });
    return api.get(`/api/incomes?${params.toString()}`);
  }

  function openCreateDialog(presetDate = "") {
    setDialogMode("create");
    setSelectedExpenseId(null);
    setFormError("");
    setForm(createDefaultExpenseForm(
      user?.username || "",
      user?.account_type,
      presetDate || getDefaultDateForMonth(filters.month_label),
    ));
  }

  function closeDialog() {
    setDialogMode(null);
    setSelectedExpenseId(null);
    setFormError("");
    setIsSubmitting(false);
  }

  function openDeleteConfirmDialog(expenseId) {
    setPendingDeleteExpenseId(expenseId);
  }

  function closeDeleteConfirmDialog() {
    if (isSubmitting) {
      return;
    }
    setPendingDeleteExpenseId(null);
  }

  async function handleConfirmDeleteExpense() {
    if (!pendingDeleteExpenseId) {
      return;
    }
    await handleDeleteExpense(pendingDeleteExpenseId);
    setPendingDeleteExpenseId(null);
  }

  function handleSelectMoreForDelete() {
    if (!pendingDeleteExpenseId) {
      return;
    }
    setSelectedIds([pendingDeleteExpenseId]);
    setIsDeleteMode(true);
    setPendingDeleteExpenseId(null);
  }

  function updateFilter(key, value) {
    setFilters((current) => ({ ...current, [key]: value }));
    const next = new URLSearchParams(searchParams);
    if (value && value !== "Tutti" && value !== "Tutte" && value !== "date_desc") {
      next.set(key, value);
    } else if (key === "search" && value) {
      next.set(key, value);
    } else {
      next.delete(key);
    }
    setSearchParams(next, { replace: true });
  }

  function shiftSelectedMonth(delta) {
    if (!filters.month_label || filters.month_label === "Tutti") {
      return;
    }
    const nextMonth = shiftMonthLabel(filters.month_label, delta);
    if (nextMonth < "2026-01") {
      return;
    }
    updateFilter("month_label", nextMonth);
  }

  async function refreshExpensesList(message = "", type = "success") {
    const [response, incomesResponse] = await Promise.all([
      fetchExpenses(filters),
      fetchIncomeSummary(filters),
    ]);
    setData(response);
    setIncomeTotal(Number(incomesResponse.summary?.total_amount || 0));
    setSelectedIds([]);
    setFeedback(message);
    setFeedbackType(type);
  }

  async function openEditDialog(expenseId) {
    setDialogMode("edit");
    setSelectedExpenseId(expenseId);
    setFormError("");
    setIsSubmitting(false);
    try {
      const response = await api.get(`/api/expenses/${expenseId}`);
      setForm(normalizeExpenseForForm(response.item, user?.username || ""));
    } catch (requestError) {
      setDialogMode(null);
      setFeedback(requestError.message || "Impossibile caricare il dettaglio della spesa.");
      setFeedbackType("error");
    }
  }

  async function handleSubmitExpense() {
    const validationMessage = validateExpenseForm(form, user?.username || "");
    if (validationMessage) {
      setFormError(validationMessage);
      return;
    }
    setIsSubmitting(true);
    setFormError("");
    try {
      const payload = buildExpensePayload(form, user?.username || "");
      if (dialogMode === "create") {
        await api.post("/api/expenses", payload);
        notifyAppDataChanged({ scope: "expenses" });
        await refreshExpensesList("Spesa creata con successo.");
      } else if (selectedExpenseId) {
        await api.put(`/api/expenses/${selectedExpenseId}`, payload);
        notifyAppDataChanged({ scope: "expenses" });
        await refreshExpensesList("Spesa aggiornata con successo.");
      }
      closeDialog();
    } catch (requestError) {
      setFormError(requestError.message || "Impossibile salvare la spesa.");
    } finally {
      setIsSubmitting(false);
    }
  }

  function toggleSelectedId(expenseId) {
    setSelectedIds((current) =>
      current.includes(expenseId) ? current.filter((item) => item !== expenseId) : [...current, expenseId],
    );
  }

  async function handleBulkDelete() {
    setIsSubmitting(true);
    try {
      const response = await api.post("/api/expenses/bulk-delete", { ids: selectedIds });
      setIsDeleteMode(false);
      setSelectedIds([]);
      notifyAppDataChanged({ scope: "expenses" });
      await refreshExpensesList(`${response.deleted_count} spese eliminate.`);
    } catch (requestError) {
      setFeedback(requestError.message || "Impossibile eliminare le spese selezionate.");
      setFeedbackType("error");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleDeleteExpense(expenseId) {
    setIsSubmitting(true);
    try {
      const response = await api.post("/api/expenses/bulk-delete", { ids: [expenseId] });
      notifyAppDataChanged({ scope: "expenses" });
      await refreshExpensesList(`${response.deleted_count || 1} spesa eliminata.`);
    } catch (requestError) {
      setFeedback(requestError.message || "Impossibile eliminare la spesa.");
      setFeedbackType("error");
    } finally {
      setIsSubmitting(false);
    }
  }

  function handleExportCsv() {
    const header = ["Data", "Descrizione", "Categoria", "Pagata da", "Importo", "Tua quota"];
    const rows = data.items.map((item) => [
      item.expense_date || "",
      item.name || item.description || "Spesa",
      item.category || "",
      item.paid_by || "",
      Number(item.amount || 0).toFixed(2),
      getCurrentUserExpenseShare(item, user?.username || "").toFixed(2),
    ]);
    const csv = [header, ...rows]
      .map((row) => row.map((cell) => `"${String(cell).replaceAll('"', '""')}"`).join(","))
      .join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `uscite-${filters.month_label || "tutti"}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  function openCategoryPreview(entry) {
    const category = entry?.payload || entry;
    if (!category?.label) {
      return;
    }
    setSelectedCategoryPreview({
      label: category.label,
      value: Number(category.value || 0),
      percentage: Number(category.percentage || 0),
      color: category.color || getExpenseCategoryColor(category.label),
    });
  }

  function openCategoryInExpenses(categoryLabel) {
    const cleanCategory = String(categoryLabel || "").trim();
    if (!cleanCategory) {
      return;
    }
    setSelectedCategoryPreview(null);
    const next = new URLSearchParams(searchParams);
    next.set("month_label", filters.month_label);
    next.set("category", cleanCategory);
    next.set("payer", filters.payer || "Tutti");
    next.set("expense_type", filters.expense_type || "Tutte");
    next.set("sort", filters.sort || "date_desc");
    next.delete("search");
    setFilters((current) => ({ ...current, category: cleanCategory, search: "" }));
    setSearchParams(next, { replace: true });
  }

  function resetExpenseFilters() {
    const monthLabel = filters.month_label || getCurrentMonthLabel();
    const next = new URLSearchParams();
    next.set("month_label", monthLabel);
    next.set("category", "Tutte");
    next.set("payer", "Tutti");
    next.set("expense_type", "Tutte");
    next.set("sort", "date_desc");
    setSelectedCategoryPreview(null);
    setFilters((current) => ({
      ...current,
      month_label: monthLabel,
      category: "Tutte",
      payer: "Tutti",
      expense_type: "Tutte",
      search: "",
      sort: "date_desc",
    }));
    setSearchParams(next, { replace: true });
  }
}

function ExpenseFeed({ items, currentUsername, selectedIds, isDeleteMode, userAccentMap, onSelect, onEdit, onDelete }) {
  if (!items.length) {
    return <div className="expenses-empty-state">Nessuna spesa trovata con i filtri selezionati.</div>;
  }

  return (
    <div className={`expenses-grouped-list${isDeleteMode ? " delete-mode" : ""}`}>
      {groupExpensesByDay(items).map((group) => (
        <section key={group.dateKey} className="couple-day-group expenses-day-group">
          <div className="couple-day-header expenses-day-header">
            <strong>{formatDayGroupLabel(group.dateKey)}</strong>
            <span className="debit">-{formatCurrency(group.total)}</span>
          </div>

          <div className="couple-day-card expenses-day-card">
            {group.items.map((item) => {
              const totalAmount = Number(item.amount || 0);
              const userShareAmount = getCurrentUserExpenseShare(item, currentUsername);
              const isSelected = selectedIds.includes(item.id);
              const handleRowAction = () => {
                if (isDeleteMode) {
                  onSelect(item.id);
                  return;
                }
                onEdit(item.id);
              };
              const handleRowKeyDown = (event) => {
                if (event.key !== "Enter" && event.key !== " ") {
                  return;
                }
                event.preventDefault();
                handleRowAction();
              };

              return (
                <article
                  key={item.id}
                  className={`couple-expense-row expenses-day-row${isSelected ? " is-selected" : ""}`}
                  tabIndex={0}
                  onClick={handleRowAction}
                  onKeyDown={handleRowKeyDown}
                >
                  {isDeleteMode ? (
                    <label className="couple-row-checkbox expenses-row-checkbox" aria-label={`Seleziona spesa ${item.name || item.description || item.id}`}>
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onClick={(event) => event.stopPropagation()}
                        onChange={() => onSelect(item.id)}
                      />
                      <span />
                    </label>
                  ) : null}

                  <div className="couple-row-category-icon" style={{ "--category-color": getExpenseCategoryColor(item.category) }}>
                    {renderExpenseCategoryGlyph(item.category)}
                  </div>

                  <div className="couple-row-main">
                    <strong>{item.name || item.description || "Spesa"}</strong>
                    <span>{buildExpenseRowMeta(item, userShareAmount)}</span>
                    <span className="couple-row-paid-by">
                      <i style={{ "--payer-color": getUserAccentColor(item.paid_by, userAccentMap) }} />
                      Pagata da {item.paid_by || "-"}
                    </span>
                  </div>

                  <div className="couple-row-impact debit expenses-row-amount">
                    <strong>{formatCurrency(totalAmount)}</strong>
                    <small>{formatShortDayLabel(item.expense_date)}</small>
                  </div>

                  <div className="couple-row-actions">
                    <button
                      type="button"
                      className="expenses-row-delete"
                      aria-label={`Elimina ${item.name || item.description || "spesa"}`}
                      onClick={(event) => {
                        event.stopPropagation();
                        onDelete(item.id);
                      }}
                    >
                      <TrashIcon />
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}

function ExpenseMetricCard({ icon, tone, label, value, detail }) {
  return (
    <article className={`expenses-premium-metric is-${tone}`}>
      <span className="expenses-premium-metric__icon" aria-hidden="true">{renderExpenseMetricIcon(icon)}</span>
      <span className="expenses-premium-metric__copy">
        <small>{label}</small>
        <strong>{value}</strong>
        <em>{detail}</em>
      </span>
    </article>
  );
}

function ExpenseCategoryDonut({ entries, total, onCategoryClick }) {
  return (
    <aside className="expenses-top-donut" aria-label="Dove vanno le tue spese">
      <div className="expenses-top-donut__head">
        <strong>{formatCurrency(total)}</strong>
      </div>
      <div className="expenses-top-donut__body" aria-label={`Totale categorie ${formatCurrency(total)}`}>
        <div className={`home-analytics-donut__chart expenses-top-donut__chart${entries.length ? " has-data" : ""}`}>
          {entries.length ? (
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Tooltip content={<ChartTooltip formatter={formatCurrency} />} />
                <Pie
                  data={entries}
                  dataKey="value"
                  nameKey="label"
                  innerRadius={44}
                  outerRadius={74}
                  paddingAngle={0}
                  stroke="none"
                  onClick={onCategoryClick}
                >
                  {entries.map((entry) => (
                    <Cell key={entry.label} fill={entry.color} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <span />
          )}
        </div>
      </div>
    </aside>
  );
}

function CategoryIcon({ label }) {
  const normalized = String(label || "").toLowerCase();
  if (normalized === "casa") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M4.75 10.75 12 4.75l7.25 6" />
        <path d="M6.25 9.75v8.5h4.25v-5h3v5h4.25v-8.5" />
      </svg>
    );
  }
  if (normalized === "spesa") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M6.5 7.25h12l-1.2 7.1a2 2 0 0 1-2 1.65H9.15a2 2 0 0 1-1.95-1.55L5.7 5.75H3.9" />
        <path d="M9.25 19.25h.01M16 19.25h.01" />
      </svg>
    );
  }
  if (normalized === "trasporti") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M6 16.5V8.75C6 6.95 7.45 5.5 9.25 5.5h5.5C16.55 5.5 18 6.95 18 8.75v7.75" />
        <path d="M7.25 13.25h9.5M8.25 9h7.5" />
        <path d="M8.5 18.75h.01M15.5 18.75h.01" />
      </svg>
    );
  }
  if (normalized === "svago") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M8.25 14.25h7.5" />
        <path d="M9.2 10.1h.01M14.8 10.1h.01" />
        <path d="M7.25 18.25h9.5a3 3 0 0 0 2.95-3.55l-1-5.45A3 3 0 0 0 15.75 6.8h-7.5A3 3 0 0 0 5.3 9.25l-1 5.45a3 3 0 0 0 2.95 3.55Z" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M6.75 7.25h10.5v10.5H6.75Z" />
      <path d="M9.25 10h5.5M9.25 13.25h5.5" />
    </svg>
  );
}

function ChartTooltip({ active, payload, label, formatter = (value) => value }) {
  if (!active || !payload?.length) {
    return null;
  }

  const visibleItems = payload.filter((item) => item.value !== null && item.value !== undefined);
  if (!visibleItems.length) {
    return null;
  }

  const firstItem = visibleItems[0];
  const tooltipLabel = label || firstItem.name || firstItem.payload?.label;
  return (
    <div className="home-chart-tooltip">
      {tooltipLabel ? <span className="home-chart-tooltip__label">{tooltipLabel}</span> : null}
      {visibleItems.map((item) => (
        <strong key={item.dataKey || item.name} className="home-chart-tooltip__value">
          {item.name ? <span style={{ color: item.color || item.stroke }}>{item.name}</span> : null}
          {formatter(item.value)}
        </strong>
      ))}
    </div>
  );
}

function renderExpenseMetricIcon(icon) {
  const common = {
    fill: "none",
    stroke: "currentColor",
    strokeLinecap: "round",
    strokeLinejoin: "round",
    strokeWidth: 2,
  };
  if (icon === "ratio") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path {...common} d="M4 19V5" />
        <path {...common} d="M4 19h16" />
        <path {...common} d="M8 15l3-4 3 2 4-6" />
      </svg>
    );
  }
  if (icon === "average") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path {...common} d="M12 3v18" />
        <path {...common} d="M6 7h9a3 3 0 1 1 0 6H8" />
        <path {...common} d="M6 17h10" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path {...common} d="M5 7h14" />
      <path {...common} d="m13 13 4-4 4 4" />
      <path {...common} d="M17 9v10" />
      <path {...common} d="M5 17h8" />
    </svg>
  );
}

function CategoryBadge({ category }) {
  const normalized = String(category || "Altro").toLowerCase();
  const tone = ["casa", "spesa", "trasporti", "svago"].includes(normalized) ? normalized : "altro";
  return <span className={`expenses-category-badge ${tone}`}>{category || "Altro"}</span>;
}

function buildExpenseRowMeta(item, userShareAmount) {
  const typeLabel = item.expense_type === "Condivisa" ? "Condivisa" : "Personale";
  const shareLabel = item.expense_type === "Condivisa" ? ` · Tua quota ${formatCurrency(userShareAmount)}` : "";
  return `${item.category || "Senza categoria"} · ${typeLabel}${shareLabel}`;
}

function groupExpensesByDay(items) {
  const groupsByDate = new Map();
  (items || []).forEach((item) => {
    const dateKey = item.expense_date || item.date || "Senza data";
    if (!groupsByDate.has(dateKey)) {
      groupsByDate.set(dateKey, { dateKey, items: [], total: 0 });
    }
    const group = groupsByDate.get(dateKey);
    group.items.push(item);
    group.total += Number(item.amount || 0);
  });

  return Array.from(groupsByDate.values())
    .sort((left, right) => String(right.dateKey).localeCompare(String(left.dateKey)))
    .map((group) => ({
      ...group,
      total: Number(group.total.toFixed(2)),
    }));
}

function formatDayGroupLabel(value) {
  if (!value || value === "Senza data") {
    return "Senza data";
  }
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const day = new Date(date);
  day.setHours(0, 0, 0, 0);
  const diffDays = Math.round((today.getTime() - day.getTime()) / 86400000);
  if (diffDays === 0) {
    return "Oggi";
  }
  if (diffDays === 1) {
    return "Ieri";
  }
  return new Intl.DateTimeFormat("it-IT", { day: "numeric", month: "long" }).format(date);
}

function formatShortDayLabel(value) {
  if (!value) {
    return "";
  }
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return new Intl.DateTimeFormat("it-IT", { day: "numeric", month: "short" }).format(date).replace(".", "");
}

function renderExpenseCategoryGlyph(category) {
  const normalized = String(category || "").toLowerCase();
  if (normalized.includes("casa")) return <ExpenseMiniIcon name="home" />;
  if (normalized.includes("spesa") || normalized.includes("ristor")) return <ExpenseMiniIcon name="cart" />;
  if (normalized.includes("trasport")) return <ExpenseMiniIcon name="car" />;
  if (normalized.includes("svago")) return <ExpenseMiniIcon name="sparkle" />;
  if (normalized.includes("regal")) return <ExpenseMiniIcon name="gift" />;
  return <ExpenseMiniIcon name="receipt" />;
}

function getExpenseCategoryColor(category) {
  const normalized = String(category || "").toLowerCase();
  if (normalized.includes("casa")) return "#63d72a";
  if (normalized.includes("spesa") || normalized.includes("ristor")) return "#f59e0b";
  if (normalized.includes("trasport")) return "#a855f7";
  if (normalized.includes("svago")) return "#3b82f6";
  if (normalized.includes("regal")) return "#a855f7";
  return "#6b7280";
}

function normalizeCategoryName(value) {
  return String(value || "Altro").trim().toLowerCase();
}

function buildExpenseCategoryDistribution(items, currentUsername) {
  const groups = new Map();
  (items || []).forEach((item) => {
    const label = String(item.category || "Altro").trim() || "Altro";
    const normalized = label.toLowerCase();
    const current = groups.get(normalized) || {
      label,
      value: 0,
      color: getExpenseCategoryColor(label),
    };
    current.value += getCurrentUserExpenseShare(item, currentUsername);
    groups.set(normalized, current);
  });

  const total = Array.from(groups.values()).reduce((sum, item) => sum + Number(item.value || 0), 0);
  return Array.from(groups.values())
    .filter((entry) => Number(entry.value || 0) > 0)
    .sort((left, right) => right.value - left.value)
    .map((entry) => ({
      ...entry,
      value: Number(entry.value.toFixed(2)),
      percentage: total ? Math.round((entry.value / total) * 100) : 0,
    }));
}

function buildExpenseDonutGradient(entries) {
  if (!entries.length) {
    return "rgba(255,255,255,0.08) 0deg 360deg";
  }
  const total = entries.reduce((sum, entry) => sum + Number(entry.value || 0), 0);
  let start = 0;
  return entries.map((entry) => {
    const sweep = total ? (Number(entry.value || 0) / total) * 360 : 0;
    const end = start + sweep;
    const segment = `${entry.color} ${start.toFixed(2)}deg ${end.toFixed(2)}deg`;
    start = end;
    return segment;
  }).join(", ");
}

function ExpenseMiniIcon({ name }) {
  const common = {
    fill: "none",
    stroke: "currentColor",
    strokeLinecap: "round",
    strokeLinejoin: "round",
    strokeWidth: 2,
  };
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      {name === "home" ? (
        <>
          <path {...common} d="m3 11 9-8 9 8" />
          <path {...common} d="M5 10v10h14V10" />
          <path {...common} d="M9 20v-6h6v6" />
        </>
      ) : null}
      {name === "cart" ? (
        <>
          <path {...common} d="M4 5h2l2 10h9l2-7H7" />
          <path {...common} d="M9 20h.01" />
          <path {...common} d="M17 20h.01" />
        </>
      ) : null}
      {name === "car" ? (
        <>
          <path {...common} d="M5 16h14l-1.5-5h-11L5 16Z" />
          <path {...common} d="M7 16v2" />
          <path {...common} d="M17 16v2" />
          <path {...common} d="M8 11l1-3h6l1 3" />
        </>
      ) : null}
      {name === "sparkle" ? (
        <>
          <path {...common} d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3Z" />
          <path {...common} d="M19 16l.7 2.1L22 19l-2.3.9L19 22l-.9-2.1L16 19l2.1-.9L19 16Z" />
        </>
      ) : null}
      {name === "gift" ? (
        <>
          <path {...common} d="M20 12v8H4v-8" />
          <path {...common} d="M2 8h20v4H2z" />
          <path {...common} d="M12 8v12" />
          <path {...common} d="M12 8H8.5A2.5 2.5 0 1 1 11 5.5V8Z" />
          <path {...common} d="M12 8h3.5A2.5 2.5 0 1 0 13 5.5V8Z" />
        </>
      ) : null}
      {name === "receipt" ? (
        <>
          <path {...common} d="M6 3h12v18l-2-1.2-2 1.2-2-1.2-2 1.2-2-1.2L6 21V3Z" />
          <path {...common} d="M9 8h6" />
          <path {...common} d="M9 12h6" />
          <path {...common} d="M9 16h4" />
        </>
      ) : null}
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M4 7h16" />
      <path d="M10 11v6" />
      <path d="M14 11v6" />
      <path d="M6 7l1 14h10l1-14" />
      <path d="M9 7V4h6v3" />
    </svg>
  );
}

function FilterIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M4 6h16" />
      <path d="M7 12h10" />
      <path d="M10 18h4" />
    </svg>
  );
}

function CheckIcon({ visible }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" className={visible ? "visible" : ""}>
      <path d="m5 12 4 4 10-10" />
    </svg>
  );
}

function buildUserAccentMap(members, currentUser) {
  const map = new Map();
  if (currentUser?.username) {
    map.set(currentUser.username, getAvatarAccentColor(currentUser.avatar_id || currentUser.avatarId));
  }
  members.forEach((member) => {
    if (member?.username) {
      map.set(member.username, getAvatarAccentColor(member.avatar_id || member.avatarId));
    }
  });
  return map;
}

function getUserAccentColor(username, accentMap) {
  return accentMap.get(username) || AVATAR_ACCENT_COLORS[1];
}

function getAvatarAccentColor(avatarId) {
  return AVATAR_ACCENT_COLORS[String(avatarId || "1")] || AVATAR_ACCENT_COLORS[1];
}

function getCurrentUserExpenseShare(item, currentUsername) {
  const amount = Number(item?.amount || 0);
  if (!item || item.expense_type !== "Condivisa") {
    return amount;
  }

  const payerShareRatio = item.split_type === "custom" ? Number(item.split_ratio ?? 0.5) : 0.5;
  return item.paid_by === currentUsername ? amount * payerShareRatio : amount * (1 - payerShareRatio);
}

function getCategoryName(option) {
  return typeof option === "string" ? option : option?.name || "";
}

function getCategoryKey(option) {
  return typeof option === "string" ? option : option?.id || option?.name || "";
}

function getCategoryColor(option) {
  return typeof option === "string" ? "" : option?.color || "";
}

function buildCategoryUsageMap(categoryItems) {
  const usageMap = new Map();
  categoryItems.forEach((item) => {
    const name = getCategoryName(item).toLowerCase();
    if (name) {
      usageMap.set(name, Number(item?.usedCount || 0));
    }
  });
  return usageMap;
}

function buildCategoryUsageMapFromExpenses(items) {
  const usageMap = new Map();
  items.forEach((item) => {
    const name = String(item?.category || "").trim().toLowerCase();
    if (!name) {
      return;
    }
    usageMap.set(name, (usageMap.get(name) || 0) + 1);
  });
  return usageMap;
}

export function ExpenseForm({ form, setForm, formError, payerOptions, categoryOptions, splitOptions, expenseTypeOptions, currentUsername, monthLabel, onCategoryCreated, onCategoryDeleted }) {
  const [isNameFocused, setIsNameFocused] = useState(false);
  const [isNotesFocused, setIsNotesFocused] = useState(false);
  const [createdCategoryOptions, setCreatedCategoryOptions] = useState([]);
  const [runtimeCategoryOptions, setRuntimeCategoryOptions] = useState(categoryOptions);
  const [categoryUsageByName, setCategoryUsageByName] = useState(new Map());
  const categoryMonthLabel = useMemo(() => getMonthLabelFromDate(form.expense_date) || monthLabel || getCurrentMonthLabel(), [form.expense_date, monthLabel]);

  useEffect(() => {
    setRuntimeCategoryOptions(categoryOptions);
  }, [categoryOptions]);

  useEffect(() => {
    let isMounted = true;
    async function loadMonthCategories() {
      try {
        const response = await api.get(`/api/categories?month_label=${encodeURIComponent(categoryMonthLabel)}`);
        if (isMounted) {
          setRuntimeCategoryOptions(response.category_items || response.items || []);
          if (response.category_items?.length) {
            setCategoryUsageByName(buildCategoryUsageMap(response.category_items));
          } else {
            const expensesResponse = await api.get(`/api/expenses?month_label=${encodeURIComponent(categoryMonthLabel)}`);
            if (isMounted) {
              setCategoryUsageByName(buildCategoryUsageMapFromExpenses(expensesResponse.items || []));
            }
          }
        }
      } catch {
        if (isMounted) {
          setRuntimeCategoryOptions(categoryOptions);
          setCategoryUsageByName(new Map());
        }
      }
    }
    loadMonthCategories();
    return () => {
      isMounted = false;
    };
  }, [categoryMonthLabel, categoryOptions]);

  const mergedCategoryOptions = useMemo(() => {
    const optionsByName = new Map();
    runtimeCategoryOptions.forEach((item) => {
      const normalized = getCategoryName(item).toLowerCase();
      if (normalized) {
        optionsByName.set(normalized, item);
      }
    });
    createdCategoryOptions.forEach((item) => {
      const normalized = getCategoryName(item).toLowerCase();
      if (!normalized) {
        return;
      }
      const existing = optionsByName.get(normalized);
      if (typeof existing === "string" || !existing) {
        optionsByName.set(normalized, item);
      }
    });
    return Array.from(optionsByName.values());
  }, [runtimeCategoryOptions, createdCategoryOptions]);
  const availableCategoryOptions = useMemo(() => (
    mergedCategoryOptions
      .filter((item) => Boolean(getCategoryName(item)))
      .sort((first, second) => getCategoryName(first).localeCompare(getCategoryName(second), "it", { sensitivity: "base" }))
  ), [mergedCategoryOptions]);
  const isPersonal = form.expense_type === "Personale";
  const amount = Number(form.amount || 0);
  const splitRatio = isPersonal ? 1 : Number(form.split_ratio || 0.5);
  const payerShare = amount * splitRatio;
  const partnerShare = amount - payerShare;
  const paidByCurrentUser = form.paid_by === currentUsername || isPersonal;
  const yourShare = paidByCurrentUser ? payerShare : partnerShare;
  const otherShare = paidByCurrentUser ? partnerShare : payerShare;
  const availablePayers = useMemo(() => {
    const payersByName = new Map();
    [currentUsername, ...(payerOptions || []), form.paid_by].forEach((payer) => {
      const payerName = typeof payer === "string" ? payer : payer?.username || payer?.name || "";
      const cleanName = String(payerName || "").trim();
      if (cleanName) {
        payersByName.set(cleanName.toLowerCase(), cleanName);
      }
    });
    return Array.from(payersByName.values());
  }, [currentUsername, payerOptions, form.paid_by]);
  const partnerName = availablePayers.find((payer) => payer.toLowerCase() !== currentUsername.toLowerCase()) || "";
  const showQuoteSummary = amount > 0 && !isPersonal;
  const payerSegmentOptions = [
    { value: currentUsername, label: currentUsername, tone: "you" },
    { value: partnerName, label: partnerName, tone: "partner" },
  ].filter((option) => option.value);

  async function handleCreateCategory(categoryName) {
    const cleanName = categoryName.trim();
    const response = await api.post("/api/categories", { name: cleanName, month_label: categoryMonthLabel });
    const createdCategory = response.category || {
      id: `local-${categoryMonthLabel}-${cleanName.toLowerCase()}`,
      name: cleanName,
      color: "#63d72a",
      icon: "tag",
      isDefault: false,
      deletable: true,
      isMonthlyCustom: true,
      monthLabel: categoryMonthLabel,
      usedCount: 0,
    };
    setRuntimeCategoryOptions((current) => (
      current.some((item) => getCategoryName(item).toLowerCase() === cleanName.toLowerCase()) ? current : [...current, createdCategory]
    ));
    setCreatedCategoryOptions((current) => (
      current.some((item) => getCategoryName(item).toLowerCase() === cleanName.toLowerCase()) ? current : [...current, createdCategory]
    ));
    onCategoryCreated?.(createdCategory);
    setFormValue(setForm, "category", cleanName);
    return cleanName;
  }

  async function handleDeleteCategory(categoryName) {
    await api.delete(`/api/categories/${encodeURIComponent(categoryName)}?month_label=${encodeURIComponent(categoryMonthLabel)}`);
    setRuntimeCategoryOptions((current) => current.filter((item) => getCategoryName(item).toLowerCase() !== categoryName.toLowerCase()));
    setCreatedCategoryOptions((current) => current.filter((item) => getCategoryName(item).toLowerCase() !== categoryName.toLowerCase()));
    onCategoryDeleted?.(categoryName);
    notifyAppDataChanged({ scope: "expenses" });
    if (form.category.toLowerCase() === categoryName.toLowerCase()) {
      setFormValue(setForm, "category", "Spesa");
    }
  }

  return (
    <div className="expense-form-card expense-form-card--premium">
      <div className="expense-form-grid">
        <ExpenseFormField label="Importo">
          <div className="expense-amount-input-shell">
            <CompactAmountInput value={form.amount} onChange={(value) => setFormValue(setForm, "amount", value)} />
            <DateChoice
              value={form.expense_date}
              onChange={(value) => setFormValue(setForm, "expense_date", value)}
            />
          </div>
        </ExpenseFormField>

        <ExpenseFormField label="Pagata da">
          <PayerSegmentedControl
            value={isPersonal ? currentUsername : form.paid_by}
            options={payerSegmentOptions}
            disabled={isPersonal}
            onChange={(value) => setFormValue(setForm, "paid_by", value)}
          />
        </ExpenseFormField>

        <ExpenseFormField label="Nome spesa" icon="receipt">
          <label className="expense-name-control">
            <input
              type="text"
              aria-label="Nome spesa"
              value={form.name}
              placeholder={isNameFocused ? "" : "Nome"}
              onFocus={() => setIsNameFocused(true)}
              onBlur={() => setIsNameFocused(false)}
              onChange={(event) => setFormValue(setForm, "name", event.target.value)}
            />
          </label>
        </ExpenseFormField>

        <ExpenseFormField label="Categoria" icon="category">
          <ChoiceMenu
            ariaLabel="Categoria spesa"
            value={form.category}
            options={availableCategoryOptions}
            placeholder="Categoria"
            allowCreate
            allowDelete
            createLabel="Aggiungi categoria"
            canDeleteOption={(option) => {
              const optionName = getCategoryName(option);
              const usageCount = categoryUsageByName.get(optionName.toLowerCase()) ?? Number(option?.usedCount || 0);
              if (DEFAULT_CATEGORY_OPTIONS.some((item) => item.toLowerCase() === optionName.toLowerCase())) {
                return false;
              }
              if (typeof option === "string") {
                return usageCount === 0;
              }
              return Boolean(option.isMonthlyCustom || option.deletable) && usageCount === 0;
            }}
            onCreateOption={handleCreateCategory}
            onDeleteOption={handleDeleteCategory}
            onChange={(value) => setFormValue(setForm, "category", value)}
            getLabel={getCategoryName}
            getValue={getCategoryName}
            getOptionKey={getCategoryKey}
            getColor={getCategoryColor}
          />
        </ExpenseFormField>

        <ExpenseFormField label="Tipo di spesa" icon="users">
          <ChoiceMenu
            ariaLabel="Tipo spesa"
            value={form.expense_type}
            options={expenseTypeOptions}
            onChange={(value) => updateExpenseType(setForm, value, currentUsername)}
          />
        </ExpenseFormField>

        <ExpenseFormField label="Ripartizione" icon="split">
          {!isPersonal ? (
            <ChoiceMenu
              ariaLabel="Divisione spesa"
              value={form.split_type}
              options={splitOptions}
              getLabel={(option) => (option === "equal" ? "50/50" : "Personalizzata")}
              onChange={(value) => {
                setForm((current) => ({
                  ...current,
                  split_type: value,
                  split_ratio: value === "custom" ? 0.5 : current.split_ratio,
                }));
              }}
            />
          ) : (
            <div className="expense-static-field">Non divisa</div>
          )}
        </ExpenseFormField>

        {!isPersonal && form.split_type === "custom" ? (
          <label className="field expense-split-range expense-form-full">
            <span>Quota di chi paga: {Math.round(splitRatio * 100)}%</span>
            <input type="range" min="0" max="1" step="0.01" value={form.split_ratio} onChange={(event) => setFormValue(setForm, "split_ratio", Number(event.target.value))} />
          </label>
        ) : null}

        {showQuoteSummary ? (
          <div className="expense-quote-summary expense-form-full">
            <BalanceGlyph />
            <div>
              <span>RIEPILOGO QUOTE</span>
              <p>La spesa verra ripartita in base alle impostazioni selezionate.</p>
            </div>
            <strong>
              <small>Tua quota</small>
              {formatCurrency(yourShare)}
            </strong>
            <strong>
              <small>Quota partner</small>
              {formatCurrency(otherShare)}
            </strong>
          </div>
        ) : null}

        <ExpenseFormField label="Note facoltative" icon="note" fullWidth>
          <label className="expense-name-control expense-notes-control">
            <textarea
              rows="1"
              aria-label="Note facoltative"
              value={form.description}
              placeholder={isNotesFocused ? "" : "Note (facoltativo)"}
              onFocus={() => setIsNotesFocused(true)}
              onBlur={() => setIsNotesFocused(false)}
              onChange={(event) => setFormValue(setForm, "description", event.target.value)}
            />
          </label>
        </ExpenseFormField>
      </div>
      {formError ? <p className="error-message form-message expense-form-alert">{getFriendlyExpenseFormError(formError)}</p> : null}
    </div>
  );
}

function ExpenseFormField({ label, children, fullWidth = false, icon = "" }) {
  return (
    <div className={`expense-form-field${fullWidth ? " expense-form-full" : ""}${icon ? " has-icon" : ""}`}>
      <span className="expense-form-label">{label}</span>
      {icon ? <span className="expense-form-field-icon" aria-hidden="true"><ExpenseFieldIcon name={icon} /></span> : null}
      {children}
    </div>
  );
}

function CompactAmountInput({ value, onChange }) {
  function handleChange(event) {
    const nextValue = event.target.value.replace(",", ".");
    if (nextValue === "" || /^\d*\.?\d{0,2}$/.test(nextValue)) {
      onChange(nextValue);
    }
  }

  return (
    <label className="expense-compact-amount-control">
      <span aria-hidden="true">€</span>
      <input
        type="text"
        inputMode="decimal"
        aria-label="Importo"
        value={value}
        placeholder="0,00"
        onChange={handleChange}
      />
    </label>
  );
}

function ExpenseFieldIcon({ name }) {
  const common = { fill: "none", stroke: "currentColor", strokeLinecap: "round", strokeLinejoin: "round", strokeWidth: 2 };
  if (name === "receipt") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path {...common} d="M7 4.75h10v14.5l-2-1.2-2 1.2-2-1.2-2 1.2-2-1.2V4.75Z" />
        <path {...common} d="M9.5 9h5M9.5 12h5M9.5 15h3" />
      </svg>
    );
  }
  if (name === "category") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path {...common} d="M5 5h5v5H5zM14 5h5v5h-5zM5 14h5v5H5zM14 14h5v5h-5z" />
      </svg>
    );
  }
  if (name === "users") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path {...common} d="M9.5 11.5a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z" />
        <path {...common} d="M4.75 18.5a4.75 4.75 0 0 1 9.5 0" />
        <path {...common} d="M15.5 8a2.5 2.5 0 0 1 0 5" />
        <path {...common} d="M16.5 15.25a4.1 4.1 0 0 1 2.75 3.25" />
      </svg>
    );
  }
  if (name === "split") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path {...common} d="M12 4v4a4 4 0 0 1-4 4H5" />
        <path {...common} d="M12 4v4a4 4 0 0 0 4 4h3" />
        <path {...common} d="M5 12l3-3M5 12l3 3M19 12l-3-3M19 12l-3 3" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path {...common} d="M6.5 5.5h11v13h-11z" />
      <path {...common} d="M9 9h6M9 12h6M9 15h3.5" />
    </svg>
  );
}

function PayerSegmentedControl({ value, options, disabled, onChange }) {
  return (
    <div className={`expense-payer-segment${disabled ? " disabled" : ""}`}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          className={`${value === option.value ? "active " : ""}is-${option.tone}`}
          disabled={disabled}
          onClick={() => onChange(option.value)}
        >
          <i />
          {option.label}
        </button>
      ))}
    </div>
  );
}

function ExpenseDialogIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 3.5 13.9 9l5.6 1.9-5.6 1.9L12 18.5l-1.9-5.7-5.6-1.9L10.1 9 12 3.5Z" />
      <path d="M18.5 4.5v3M20 6h-3" />
    </svg>
  );
}

function BalanceGlyph() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 4v16" />
      <path d="M6.5 7.5h11" />
      <path d="M8 7.5 5 14h6L8 7.5Z" />
      <path d="M16 7.5 13 14h6l-3-6.5Z" />
    </svg>
  );
}

function getFriendlyExpenseFormError(message) {
  const normalized = String(message || "").toLowerCase();
  if (normalized.includes("internal server error") || normalized.includes("server error")) {
    return "Non e stato possibile creare la spesa. Riprova.";
  }
  return message;
}

function ChoiceMenu({
  ariaLabel,
  value,
  options,
  onChange,
  getLabel = (option) => option,
  getValue = (option) => option,
  getOptionKey = (option) => option,
  getColor = () => "",
  disabled = false,
  placeholder = "",
  allowCreate = false,
  allowDelete = false,
  createLabel = "Aggiungi",
  canDeleteOption = () => true,
  onCreateOption,
  onDeleteOption,
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [newOption, setNewOption] = useState("");
  const [createError, setCreateError] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [deletingOption, setDeletingOption] = useState("");
  const menuRef = useRef(null);
  const selectedOption = options.find((option) => getValue(option) === value);
  const selectedLabel = selectedOption ? getLabel(selectedOption) : value || placeholder;

  useEffect(() => {
    if (!isOpen) {
      return undefined;
    }

    function closeMenu(event) {
      if (menuRef.current?.contains(event.target)) {
        return;
      }
      setIsOpen(false);
    }

    function closeOnEscape(event) {
      if (event.key === "Escape") {
        setIsOpen(false);
      }
    }

    function closeOnResize() {
      setIsOpen(false);
    }

    document.addEventListener("pointerdown", closeMenu);
    window.addEventListener("resize", closeOnResize);
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeMenu);
      window.removeEventListener("resize", closeOnResize);
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [isOpen]);

  async function handleCreateOption() {
    const cleanOption = newOption.trim();
    if (!cleanOption || !onCreateOption) {
      return;
    }

    setIsCreating(true);
    setCreateError("");
    try {
      const createdOption = await onCreateOption(cleanOption);
      onChange(createdOption || cleanOption);
      setNewOption("");
      setIsOpen(false);
    } catch (requestError) {
      setCreateError(requestError.message || "Impossibile aggiungere la categoria.");
    } finally {
      setIsCreating(false);
    }
  }

  async function handleDeleteOption(option) {
    if (!onDeleteOption) {
      return;
    }
    setDeletingOption(option);
    setCreateError("");
    try {
      await onDeleteOption(option);
      if (value === option) {
        onChange("Spesa");
      }
    } catch (requestError) {
      setCreateError(requestError.message || "Impossibile eliminare la categoria.");
    } finally {
      setDeletingOption("");
    }
  }

  return (
    <div ref={menuRef} className={`expense-choice-control${disabled ? " disabled" : ""}`}>
      <button
        type="button"
        className="expense-choice-button"
        aria-label={ariaLabel}
        aria-expanded={isOpen}
        disabled={disabled}
        onClick={() => setIsOpen((current) => !current)}
      >
        {selectedLabel}
      </button>
      {isOpen ? (
        <div className={`expense-choice-menu${allowCreate ? " is-creatable" : ""}`}>
          <div className="expense-choice-options">
            {options.map((option) => {
              const optionValue = getValue(option);
              const optionKey = getOptionKey(option);
              const optionColor = getColor(option);
              const canDelete = allowDelete && canDeleteOption(option);
              return (
                <div key={optionKey} className={`expense-choice-option-row${canDelete ? " has-delete" : ""}`}>
                  <button
                    type="button"
                    className={`expense-choice-option${optionValue === value ? " active" : ""}`}
                    style={optionColor ? { "--option-color": optionColor } : undefined}
                    onMouseDown={(event) => event.preventDefault()}
                    onClick={() => {
                      onChange(optionValue);
                      setIsOpen(false);
                    }}
                  >
                    {optionColor ? <span className="expense-choice-option-dot" aria-hidden="true" /> : null}
                    {getLabel(option)}
                  </button>
                  {canDelete ? (
                    <button
                      type="button"
                      className="expense-choice-delete"
                      aria-label={`Elimina categoria ${getLabel(option)}`}
                      disabled={deletingOption === optionValue}
                      onClick={(event) => {
                        event.stopPropagation();
                        handleDeleteOption(optionValue);
                      }}
                    >
                      ×
                    </button>
                  ) : null}
                </div>
              );
            })}
          </div>
          {allowCreate ? (
            <div className="expense-choice-create" onMouseDown={(event) => event.stopPropagation()}>
              <input
                type="text"
                value={newOption}
                placeholder="Nuova categoria"
                onChange={(event) => {
                  setNewOption(event.target.value);
                  setCreateError("");
                }}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    handleCreateOption();
                  }
                }}
              />
              <button type="button" onClick={handleCreateOption} disabled={isCreating || !newOption.trim()}>
                {isCreating ? "..." : createLabel}
              </button>
              {createError ? <span className="expense-choice-create-error">{createError}</span> : null}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export function createDefaultExpenseForm(currentUsername, accountType = "couple", presetDate = "") {
  const isPersonalAccount = accountType === "personal";
  return {
    expense_date: presetDate || new Date().toISOString().slice(0, 10),
    amount: "",
    name: "",
    category: "",
    description: "",
    paid_by: currentUsername,
    expense_type: isPersonalAccount ? "Personale" : "Condivisa",
    split_type: "equal",
    split_ratio: isPersonalAccount ? 1 : 0.5,
  };
}

export function getDefaultDateForMonth(monthLabel) {
  if (!/^\d{4}-\d{2}$/.test(String(monthLabel || ""))) {
    return "";
  }
  const [year, month] = monthLabel.split("-").map(Number);
  if (month < 1 || month > 12) {
    return "";
  }
  const today = new Date();
  const lastDayOfMonth = new Date(year, month, 0).getDate();
  const day = Math.min(today.getDate(), lastDayOfMonth);
  return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

export function normalizeExpenseForForm(item, currentUsername) {
  return {
    expense_date: item.expense_date || new Date().toISOString().slice(0, 10),
    amount: String(item.amount ?? ""),
    name: item.name || "",
    category: item.category || "Casa",
    description: item.description || "",
    paid_by: item.expense_type === "Personale" ? currentUsername : item.paid_by || currentUsername,
    expense_type: item.expense_type || "Condivisa",
    split_type: item.split_type || "equal",
    split_ratio: Number(item.split_ratio ?? 0.5),
  };
}

export function buildExpensePayload(form, currentUsername) {
  const expenseType = form.expense_type;
  const splitType = expenseType === "Personale" ? "equal" : form.split_type;
  const splitRatio = expenseType === "Personale" ? 1.0 : Number(form.split_ratio);
  const paidBy = expenseType === "Personale" ? currentUsername : form.paid_by || currentUsername;
  return {
    expense_date: form.expense_date || getTodayDateString(),
    amount: Number(form.amount),
    name: form.name.trim(),
    category: form.category,
    description: form.description.trim(),
    paid_by: paidBy,
    expense_type: expenseType,
    split_type: splitType,
    split_ratio: splitRatio,
  };
}

export function validateExpenseForm(form, currentUsername = "") {
  if (!form.name.trim()) return "Il nome della spesa e obbligatorio.";
  if (!form.category) return "La categoria e obbligatoria.";
  if (!form.amount || Number(form.amount) <= 0) return "L'importo deve essere maggiore di zero.";
  if (form.expense_type === "Condivisa" && !form.paid_by && !currentUsername) return "Seleziona chi ha pagato.";
  return "";
}

function setFormValue(setForm, key, value) {
  setForm((current) => ({ ...current, [key]: value }));
}

function adjustAmount(setForm, delta) {
  setForm((current) => {
    const nextAmount = Math.max(0, Number(current.amount || 0) + delta);
    return { ...current, amount: nextAmount.toFixed(2) };
  });
}

function updateExpenseType(setForm, expenseType, currentUsername) {
  setForm((current) => ({
    ...current,
    expense_type: expenseType,
    paid_by: expenseType === "Personale" ? currentUsername : current.paid_by || currentUsername,
    split_type: expenseType === "Personale" ? "equal" : current.split_type,
    split_ratio: expenseType === "Personale" ? 1 : current.split_ratio || 0.5,
  }));
}

function formatAmountDisplay(value) {
  if (value === "" || value === null || value === undefined) {
    return "";
  }
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue) || numericValue <= 0) {
    return "";
  }
  const [integerPart, decimalPart = "00"] = numericValue.toFixed(2).split(".");
  return `${integerPart},${decimalPart}`;
}

function splitAmountDisplay(displayValue) {
  const normalized = String(displayValue || "").replace(".", ",");
  const [rawInteger = "", rawDecimal = ""] = normalized.split(",");
  return {
    integerPart: normalizeIntegerPart(rawInteger),
    decimalPart: rawDecimal.replace(/\D/g, "").slice(0, 2),
  };
}

function parseDisplayAmount(displayValue) {
  const { integerPart, decimalPart } = splitAmountDisplay(displayValue);
  if (!integerPart && !decimalPart) {
    return 0;
  }
  return Number(`${integerPart || "0"}.${decimalPart}`);
}

function normalizeIntegerPart(value) {
  const digits = String(value || "").replace(/\D/g, "");
  return digits.replace(/^0+(?=\d)/, "");
}

function formatPastedAmount(value) {
  const normalized = String(value || "").replace(/[^\d,.]/g, "").replace(".", ",");
  const [rawInteger = "", rawDecimal = ""] = normalized.split(",");
  const integerPart = normalizeIntegerPart(rawInteger);
  const decimalPart = rawDecimal.replace(/\D/g, "").slice(0, 2);
  if (!integerPart && !decimalPart) {
    return "";
  }
  return `${integerPart || "0"},${decimalPart.padEnd(2, "0")}`;
}

function getAmountVisualParts(displayValue, isDecimalEditing, isFocused) {
  if (!displayValue) {
    return { prefixGhost: "", typed: "", typedSuffix: "", ghost: "0,00", caret: false };
  }
  if (isFocused && displayValue === "0,") {
    return { prefixGhost: "0", typed: "", typedSuffix: ",00", ghost: "", caret: true };
  }
  const normalizedDisplay = displayValue.includes(",") ? displayValue : `${displayValue},00`;
  if (!isDecimalEditing) {
    const integerPart = normalizedDisplay.split(",")[0] || "0";
    const hasTypedAmount = Number(parseDisplayAmount(normalizedDisplay)) > 0;
    if (hasTypedAmount) {
      return {
        prefixGhost: "",
        typed: integerPart,
        typedSuffix: ",00",
        ghost: "",
        caret: isFocused,
      };
    }
    return {
      prefixGhost: "",
      typed: integerPart,
      typedSuffix: isFocused ? ",00" : "",
      ghost: isFocused ? "" : ",00",
      caret: isFocused,
    };
  }
  const { integerPart, decimalPart } = splitAmountDisplay(normalizedDisplay);
  if (!decimalPart) {
    if (isFocused && (integerPart || "0") === "0") {
      return { prefixGhost: "0", typed: "", typedSuffix: ",00", ghost: "", caret: true };
    }
    return { prefixGhost: "", typed: isFocused ? `${integerPart || "0"},` : "", typedSuffix: "", ghost: isFocused ? "00" : "0,00", caret: isFocused };
  }
  return {
    prefixGhost: "",
    typed: `${integerPart || "0"},${decimalPart}`,
    typedSuffix: "",
    ghost: "".padEnd(Math.max(0, 2 - decimalPart.length), "0"),
    caret: isFocused && decimalPart.length < 2,
  };
}

function buildCalendarDays(viewDate) {
  const year = viewDate.getFullYear();
  const month = viewDate.getMonth();
  const firstDay = new Date(year, month, 1);
  const startOffset = (firstDay.getDay() + 6) % 7;
  const startDate = new Date(year, month, 1 - startOffset);

  return Array.from({ length: 42 }, (_, index) => {
    const date = new Date(startDate);
    date.setDate(startDate.getDate() + index);
    return {
      date,
      iso: toISODate(date),
      isCurrentMonth: date.getMonth() === month,
    };
  });
}

function shiftMonth(date, delta) {
  return new Date(date.getFullYear(), date.getMonth() + delta, 1);
}

function parseISODate(value) {
  if (!value) {
    return null;
  }
  const date = new Date(`${value}T00:00:00`);
  return Number.isNaN(date.getTime()) ? null : date;
}

function toISODate(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function getTodayDateString() {
  return toISODate(new Date());
}

function formatCurrency(value) {
  return new Intl.NumberFormat("it-IT", { style: "currency", currency: "EUR" }).format(Number(value || 0));
}

function formatShortDate(value) {
  const date = new Date(`${value}T00:00:00`);
  return new Intl.DateTimeFormat("it-IT", { day: "2-digit", month: "2-digit" }).format(date);
}

function formatMonthHeading(monthLabel) {
  if (!monthLabel || monthLabel === "Tutti") {
    return "Tutti i mesi";
  }
  const [year, month] = monthLabel.split("-");
  const date = new Date(`${year}-${month}-01T00:00:00`);
  return new Intl.DateTimeFormat("it-IT", { month: "long", year: "numeric" }).format(date);
}

function shiftMonthLabel(monthLabel, delta) {
  const [year, month] = monthLabel.split("-").map(Number);
  const date = new Date(year, month - 1 + delta, 1);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

function getCurrentMonthLabel() {
  return new Date().toISOString().slice(0, 7);
}

function buildFiltersFromSearchParams(searchParams) {
  return {
    month_label: searchParams.get("month_label") || getCurrentMonthLabel(),
    category: searchParams.get("category") || "Tutte",
    payer: searchParams.get("payer") || "Tutti",
    expense_type: searchParams.get("expense_type") || "Tutte",
    search: searchParams.get("search") || "",
    sort: searchParams.get("sort") || "date_desc",
  };
}

function getMonthLabelFromDate(value) {
  if (!value) {
    return "";
  }
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

function sameObject(left, right) {
  return JSON.stringify(left) === JSON.stringify(right);
}
