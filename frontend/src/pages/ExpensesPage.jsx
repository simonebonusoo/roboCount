import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Dialog } from "../components/Dialog";
import { FeedbackBanner } from "../components/FeedbackBanner";
import { MonthNavigation } from "../components/MonthNavigation";
import { StatusView } from "../components/StatusView";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";

const defaultFilters = {
  month_label: getCurrentMonthLabel(),
  category: "Tutte",
  payer: "Tutti",
  expense_type: "Tutte",
  search: "",
  sort: "date_desc",
};

export function ExpensesPage() {
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [data, setData] = useState(null);
  const [meta, setMeta] = useState(null);
  const [filters, setFilters] = useState(defaultFilters);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState("");
  const [feedbackType, setFeedbackType] = useState("success");
  const [dialogMode, setDialogMode] = useState(null);
  const [selectedExpenseId, setSelectedExpenseId] = useState(null);
  const [selectedIds, setSelectedIds] = useState([]);
  const [isEditMode, setIsEditMode] = useState(false);
  const [isDeleteMode, setIsDeleteMode] = useState(false);
  const [isFilterPanelOpen, setIsFilterPanelOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState("");
  const [form, setForm] = useState(createDefaultExpenseForm(""));
  const summaryMode = searchParams.get("summary");

  const payerOptions = useMemo(() => meta?.usernames || [], [meta]);
  const categoryOptions = useMemo(() => meta?.categories || [], [meta]);
  const splitOptions = meta?.split_options || ["equal", "custom"];
  const expenseTypeOptions = meta?.expense_types || ["Personale", "Condivisa"];
  const monthOptions = useMemo(() => data?.month_options || ["Tutti"], [data]);
  const sortOptions = data?.filters?.sort_options || [
    { value: "date_desc", label: "Data piu recente" },
    { value: "amount_desc", label: "Importo maggiore" },
    { value: "amount_asc", label: "Importo minore" },
  ];

  useEffect(() => {
    if (!user?.username) {
      return;
    }
    setForm(createDefaultExpenseForm(user.username));
  }, [user]);

  useEffect(() => {
    const nextFilters = {
      month_label: searchParams.get("month_label") || getCurrentMonthLabel(),
      category: searchParams.get("category") || "Tutte",
      payer: searchParams.get("payer") || "Tutti",
      expense_type: searchParams.get("expense_type") || "Tutte",
      search: searchParams.get("search") || "",
      sort: searchParams.get("sort") || "date_desc",
    };
    setFilters((current) => (sameObject(current, nextFilters) ? current : nextFilters));
  }, [searchParams]);

  useEffect(() => {
    if (searchParams.get("action") !== "new") {
      return;
    }
    openCreateDialog();
    const next = new URLSearchParams(searchParams);
    next.delete("action");
    setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams, user]);

  useEffect(() => {
    let isMounted = true;

    async function bootstrap() {
      setIsLoading(true);
      setError("");
      try {
        const [expensesResponse, metaResponse] = await Promise.all([
          fetchExpenses(filters),
          api.get("/api/meta/options"),
        ]);
        if (isMounted) {
          setData(expensesResponse);
          setMeta(metaResponse);
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
        const response = await fetchExpenses(filters);
        if (isMounted) {
          setData(response);
          setSelectedIds([]);
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

  const visibleIds = data.items.map((item) => item.id);
  const allVisibleSelected = visibleIds.length > 0 && selectedIds.length === visibleIds.length;

  return (
    <section className="page expense-workspace">
      <div className="page-header expense-page-header">
        <div>
          <p className="eyebrow">Uscite</p>
          <h2>{summaryMode ? "Riepilogo spese" : "Spese del periodo"}</h2>
          <p className="muted">Filtri, modifica e cancellazione sono allineati alla sezione Streamlit.</p>
        </div>
        <button type="button" className="primary-button" onClick={openCreateDialog}>
          Nuova spesa
        </button>
      </div>

      {filters.month_label ? (
        <MonthNavigation
          label={formatMonthHeading(filters.month_label)}
          onPrevious={() => shiftSelectedMonth(-1)}
          onNext={() => shiftSelectedMonth(1)}
        />
      ) : null}

      <FeedbackBanner type={feedbackType} message={feedback} />

      <CategoryPillBar
        categories={data.filters?.category_options || ["Tutte"]}
        activeCategory={filters.category}
        onChange={(category) => updateFilter("category", category)}
      />

      <div className="section-lower-layout">
        <div className="section-toolbar panel">
          <button
            type="button"
            className="toolbar-button"
            disabled={!filters.search && !isDeleteMode}
            onClick={handleBackReset}
          >
            ←
          </button>
          <button
            type="button"
            className={`toolbar-button${isFilterPanelOpen ? " active" : ""}`}
            onClick={() => setIsFilterPanelOpen((current) => !current)}
          >
            Filtri
          </button>
          <button
            type="button"
            className={`toolbar-button wide${isEditMode ? " active" : ""}`}
            onClick={() => {
              setIsEditMode((current) => !current);
              setIsDeleteMode(false);
              setSelectedIds([]);
            }}
          >
            Modifica spesa
          </button>
          <button
            type="button"
            className={`toolbar-button danger-lite${isDeleteMode ? " active" : ""}`}
            onClick={() => {
              setIsDeleteMode((current) => !current);
              setIsEditMode(false);
              setSelectedIds([]);
            }}
          >
            Elimina
          </button>
        </div>

        <StickyTotal summary={data.summary} />
      </div>

      {isFilterPanelOpen ? (
        <FilterPanel
          filters={filters}
          data={data}
          sortOptions={sortOptions}
          onChange={updateFilter}
          onReset={resetFilters}
        />
      ) : null}

      {isDeleteMode ? (
        <div className="delete-action-row panel">
          <button type="button" className="secondary-button" onClick={() => setSelectedIds(allVisibleSelected ? [] : visibleIds)}>
            {allVisibleSelected ? "Deseleziona tutte" : "Seleziona tutte"}
          </button>
          <span className="muted">{selectedIds.length} selezioni</span>
          <button type="button" className="danger-button primary-button" disabled={!selectedIds.length || isSubmitting} onClick={handleBulkDelete}>
            {isSubmitting ? "Eliminazione..." : "Elimina selezionate"}
          </button>
        </div>
      ) : null}

      <ExpenseFeed
        items={data.items}
        currentUsername={user?.username || ""}
        selectedIds={selectedIds}
        isEditMode={isEditMode}
        isDeleteMode={isDeleteMode}
        onSelect={toggleSelectedId}
        onEdit={openEditDialog}
      />

      {dialogMode === "create" || dialogMode === "edit" ? (
        <Dialog
          title={dialogMode === "create" ? "Nuova spesa" : "Modifica spesa"}
          onClose={closeDialog}
          footer={
            <>
              <button type="button" className="secondary-button" onClick={closeDialog}>
                Annulla
              </button>
              <button type="button" className="primary-button" onClick={handleSubmitExpense} disabled={isSubmitting}>
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
          />
        </Dialog>
      ) : null}

    </section>
  );

  async function fetchExpenses(activeFilters) {
    const params = new URLSearchParams(activeFilters);
    return api.get(`/api/expenses?${params.toString()}`);
  }

  function openCreateDialog() {
    setDialogMode("create");
    setSelectedExpenseId(null);
    setFormError("");
    setForm(createDefaultExpenseForm(user?.username || ""));
  }

  function closeDialog() {
    setDialogMode(null);
    setSelectedExpenseId(null);
    setFormError("");
    setIsSubmitting(false);
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
    const options = monthOptions.filter((item) => item !== "Tutti");
    if (!options.length) {
      return;
    }
    const currentIndex = options.indexOf(filters.month_label);
    const safeIndex = currentIndex === -1 ? 0 : currentIndex;
    const nextIndex = Math.max(0, Math.min(options.length - 1, safeIndex + delta));
    updateFilter("month_label", options[nextIndex]);
  }

  function handleBackReset() {
    if (isDeleteMode) {
      setIsDeleteMode(false);
      setSelectedIds([]);
      return;
    }
    updateFilter("search", "");
  }

  function resetFilters() {
    const nextFilters = { ...defaultFilters, month_label: filters.month_label || getCurrentMonthLabel() };
    setFilters(nextFilters);
    const next = new URLSearchParams(searchParams);
    ["category", "payer", "expense_type", "search", "sort"].forEach((key) => next.delete(key));
    setSearchParams(next, { replace: true });
  }

  function toggleSelectedId(expenseId) {
    setSelectedIds((current) =>
      current.includes(expenseId) ? current.filter((item) => item !== expenseId) : [...current, expenseId],
    );
  }

  async function refreshExpensesList(message = "", type = "success") {
    const response = await fetchExpenses(filters);
    setData(response);
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
    const validationMessage = validateExpenseForm(form);
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
        await refreshExpensesList("Spesa creata con successo.");
      } else if (selectedExpenseId) {
        await api.put(`/api/expenses/${selectedExpenseId}`, payload);
        await refreshExpensesList("Spesa aggiornata con successo.");
      }
      closeDialog();
    } catch (requestError) {
      setFormError(requestError.message || "Impossibile salvare la spesa.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleBulkDelete() {
    setIsSubmitting(true);
    try {
      const response = await api.post("/api/expenses/bulk-delete", { ids: selectedIds });
      setIsDeleteMode(false);
      setSelectedIds([]);
      await refreshExpensesList(`${response.deleted_count} spese eliminate.`);
    } catch (requestError) {
      setFeedback(requestError.message || "Impossibile eliminare le spese selezionate.");
      setFeedbackType("error");
    } finally {
      setIsSubmitting(false);
    }
  }

}

function CategoryPillBar({ categories, activeCategory, onChange }) {
  return (
    <div className="category-pill-bar" aria-label="Categorie uscite">
      {categories.map((category) => (
        <button
          key={category}
          type="button"
          className={`category-pill${activeCategory === category ? " active" : ""}`}
          onClick={() => onChange(category)}
        >
          {category}
        </button>
      ))}
    </div>
  );
}

function FilterPanel({ filters, data, sortOptions, onChange, onReset }) {
  return (
    <div className="panel expense-filter-panel">
      <div className="filter-panel-header">
        <div>
          <strong>Filtri uscite</strong>
          <p className="muted">Compatto come in Streamlit, senza occupare tutta la pagina.</p>
        </div>
        <button type="button" className="secondary-button" onClick={onReset}>
          Reset
        </button>
      </div>

      <div className="filters-grid">
        <label className="field">
          <span>Tipo vista</span>
          <select value={filters.expense_type} onChange={(event) => onChange("expense_type", event.target.value)}>
            <option value="Tutte">Tutte</option>
            <option value="Personale">Personali</option>
            <option value="Condivisa">Condivise</option>
          </select>
        </label>
        <label className="field">
          <span>Pagatore</span>
          <select value={filters.payer} onChange={(event) => onChange("payer", event.target.value)}>
            {(data.filters?.payer_options || ["Tutti"]).map((option) => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Ordinamento</span>
          <select value={filters.sort} onChange={(event) => onChange("sort", event.target.value)}>
            {sortOptions.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
        <label className="field field-span">
          <span>Ricerca</span>
          <input
            type="search"
            value={filters.search}
            onChange={(event) => onChange("search", event.target.value)}
            placeholder="Cerca per nome, note, categoria o pagatore"
          />
        </label>
      </div>
    </div>
  );
}

function ExpenseFeed({ items, currentUsername, selectedIds, isEditMode, isDeleteMode, onSelect, onEdit }) {
  if (!items.length) {
    return <div className="panel empty-feed">Nessuna spesa trovata con i filtri selezionati.</div>;
  }

  return (
    <div className={`transaction-feed${isEditMode ? " edit-focus" : ""}`}>
      {items.map((item) => {
        const isShared = item.expense_type === "Condivisa";
        const isMine = item.paid_by === currentUsername;
        return (
          <article key={item.id} className={`transaction-row-card${isDeleteMode ? " delete-mode" : ""}`}>
            {isDeleteMode ? (
              <input
                type="checkbox"
                aria-label={`Seleziona spesa ${item.id}`}
                checked={selectedIds.includes(item.id)}
                onChange={() => onSelect(item.id)}
              />
            ) : null}
            <div className="transaction-date">{formatShortDate(item.expense_date)}</div>
            <button
              type="button"
              className={`transaction-main${isEditMode ? " is-clickable" : ""}`}
              onClick={() => (isEditMode ? onEdit(item.id) : undefined)}
            >
              <strong>{item.name || item.description || "Spesa"}</strong>
              <span>{item.description || "Nessuna nota"}</span>
            </button>
            <span className="transaction-chip">{item.category}</span>
            <span className="transaction-user">{item.paid_by}</span>
            <span className="transaction-chip">{isShared ? "Condivisa" : "Personale"}</span>
            <span className={`transaction-amount${isMine ? " self" : " partner"}`}>{formatCurrency(item.amount)}</span>
          </article>
        );
      })}
    </div>
  );
}

function StickyTotal({ summary }) {
  const balance = Number(summary?.balance || 0);
  return (
    <div className="section-sticky-total">
      <div className="expense-total-pill-react">
        <span>Totale</span>
        <strong>{formatCurrency(summary?.total_amount || 0)}</strong>
      </div>
      <div className="expense-balance-pill-react">
        {balance > 0 ? `Mi devono ${formatCurrency(balance)}` : balance < 0 ? `Devo ${formatCurrency(Math.abs(balance))}` : "Siamo in pari"}
      </div>
    </div>
  );
}

function ExpenseForm({ form, setForm, formError, payerOptions, categoryOptions, splitOptions, expenseTypeOptions, currentUsername }) {
  const isPersonal = form.expense_type === "Personale";
  const amount = Number(form.amount || 0);
  const splitRatio = isPersonal ? 1 : Number(form.split_ratio || 0.5);
  const payerShare = amount * splitRatio;
  const partnerShare = amount - payerShare;
  const paidByCurrentUser = form.paid_by === currentUsername || isPersonal;
  const yourShare = paidByCurrentUser ? payerShare : partnerShare;
  const otherShare = paidByCurrentUser ? partnerShare : payerShare;

  return (
    <div className="form-grid">
      <label className="field">
        <span>Data</span>
        <input type="date" value={form.expense_date} onChange={(event) => setFormValue(setForm, "expense_date", event.target.value)} />
      </label>
      <label className="field">
        <span>Importo</span>
        <input type="number" min="0" step="0.01" value={form.amount} onChange={(event) => setFormValue(setForm, "amount", event.target.value)} />
      </label>
      <div className="amount-stepper field-span">
        <button type="button" onClick={() => adjustAmount(setForm, -1)}>
          −
        </button>
        <button type="button" onClick={() => adjustAmount(setForm, 1)}>
          +
        </button>
      </div>
      <label className="field field-span">
        <span>Nome</span>
        <input type="text" value={form.name} onChange={(event) => setFormValue(setForm, "name", event.target.value)} />
      </label>
      <label className="field">
        <span>Categoria</span>
        <select value={form.category} onChange={(event) => setFormValue(setForm, "category", event.target.value)}>
          {categoryOptions.map((option) => (
            <option key={option} value={option}>{option}</option>
          ))}
        </select>
      </label>
      <label className="field">
        <span>Tipo spesa</span>
        <select value={form.expense_type} onChange={(event) => updateExpenseType(setForm, event.target.value, currentUsername)}>
          {expenseTypeOptions.map((option) => (
            <option key={option} value={option}>{option}</option>
          ))}
        </select>
      </label>
      <label className="field">
        <span>Pagata da</span>
        <select value={isPersonal ? currentUsername : form.paid_by} disabled={isPersonal} onChange={(event) => setFormValue(setForm, "paid_by", event.target.value)}>
          {payerOptions.map((option) => (
            <option key={option} value={option}>{option}</option>
          ))}
        </select>
      </label>
      <label className="field">
        <span>Divisione</span>
        <select value={isPersonal ? "equal" : form.split_type} disabled={isPersonal} onChange={(event) => setFormValue(setForm, "split_type", event.target.value)}>
          {splitOptions.map((option) => (
            <option key={option} value={option}>{option === "equal" ? "50/50" : "Personalizzata"}</option>
          ))}
        </select>
      </label>
      {!isPersonal && form.split_type === "custom" ? (
        <label className="field field-span">
          <span>Quota di chi paga: {Math.round(splitRatio * 100)}%</span>
          <input type="range" min="0" max="1" step="0.01" value={form.split_ratio} onChange={(event) => setFormValue(setForm, "split_ratio", Number(event.target.value))} />
        </label>
      ) : null}
      <div className="split-preview field-span">
        {isPersonal ? "Le spese personali restano private e fuori dal saldo." : `Tu: ${formatCurrency(yourShare)} / Partner: ${formatCurrency(otherShare)}`}
      </div>
      <label className="field field-span">
        <span>Note</span>
        <textarea rows="3" value={form.description} onChange={(event) => setFormValue(setForm, "description", event.target.value)} />
      </label>
      {formError ? <p className="error-message form-message">{formError}</p> : null}
    </div>
  );
}

function createDefaultExpenseForm(currentUsername) {
  return {
    expense_date: new Date().toISOString().slice(0, 10),
    amount: "",
    name: "",
    category: "Casa",
    description: "",
    paid_by: currentUsername,
    expense_type: "Condivisa",
    split_type: "equal",
    split_ratio: 0.5,
  };
}

function normalizeExpenseForForm(item, currentUsername) {
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

function buildExpensePayload(form, currentUsername) {
  const expenseType = form.expense_type;
  const splitType = expenseType === "Personale" ? "equal" : form.split_type;
  const splitRatio = expenseType === "Personale" ? 1.0 : Number(form.split_ratio);
  return {
    expense_date: form.expense_date,
    amount: Number(form.amount),
    name: form.name.trim(),
    category: form.category,
    description: form.description.trim(),
    paid_by: expenseType === "Personale" ? currentUsername : form.paid_by,
    expense_type: expenseType,
    split_type: splitType,
    split_ratio: splitRatio,
  };
}

function validateExpenseForm(form) {
  if (!form.expense_date) return "La data e obbligatoria.";
  if (!form.name.trim()) return "Il nome della spesa e obbligatorio.";
  if (!form.category) return "La categoria e obbligatoria.";
  if (!form.amount || Number(form.amount) <= 0) return "L'importo deve essere maggiore di zero.";
  if (form.expense_type === "Condivisa" && !form.paid_by) return "Seleziona chi ha pagato.";
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

function getCurrentMonthLabel() {
  return new Date().toISOString().slice(0, 7);
}

function sameObject(left, right) {
  return JSON.stringify(left) === JSON.stringify(right);
}
