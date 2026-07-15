import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Dialog } from "../components/Dialog";
import { FeedbackBanner } from "../components/FeedbackBanner";
import { MonthNavigation } from "../components/MonthNavigation";
import { AmountInput, DateChoice } from "../components/TransactionFormControls";
import { api, notifyAppDataChanged } from "../lib/api";

const defaultFilters = {
  month_label: getCurrentMonthLabel(),
  search: "",
  sort: "date_desc",
};

export function IncomesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [data, setData] = useState(null);
  const [filters, setFilters] = useState(defaultFilters);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState("");
  const [feedbackType, setFeedbackType] = useState("success");
  const [dialogMode, setDialogMode] = useState(null);
  const [selectedIncomeId, setSelectedIncomeId] = useState(null);
  const [form, setForm] = useState(createDefaultIncomeForm());
  const [formError, setFormError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isEditMode, setIsEditMode] = useState(false);
  const [isDeleteMode, setIsDeleteMode] = useState(false);
  const [isSortPanelOpen, setIsSortPanelOpen] = useState(false);

  const sortOptions = data?.filters?.sort_options || [
    { value: "date_desc", label: "Data piu recente" },
    { value: "amount_desc", label: "Importo maggiore" },
    { value: "amount_asc", label: "Importo minore" },
  ];

  useEffect(() => {
    const nextFilters = {
      month_label: searchParams.get("month_label") || getCurrentMonthLabel(),
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
  }, [searchParams, setSearchParams]);

  useEffect(() => {
    let isMounted = true;

    async function loadIncomes() {
      setIsLoading(true);
      setError("");
      try {
        const response = await fetchIncomes(filters);
        if (isMounted) {
          setData(response);
        }
      } catch (requestError) {
        if (isMounted) {
          setError(requestError.message || "Impossibile caricare le entrate.");
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    loadIncomes();

    return () => {
      isMounted = false;
    };
  }, [filters]);

  if (isLoading) {
    return (
      <section className="page income-workspace">
        <section className="section-local-skeleton" aria-label="Caricamento entrate">
          <span />
          <span />
          <span />
        </section>
      </section>
    );
  }

  if (error) {
    return (
      <section className="page income-workspace">
        <section className="inline-error-card">
          <h1>Entrate</h1>
          <p>{error}</p>
        </section>
      </section>
    );
  }

  if (!data) {
    return (
      <section className="page income-workspace">
        <section className="inline-error-card">
          <h1>Entrate</h1>
          <p>Nessun dato disponibile.</p>
        </section>
      </section>
    );
  }

  return (
    <section className="page income-workspace">
      <section className="expenses-top-shell income-top-shell panel compact-panel">
        <div className="expenses-top-shell__header">
          <div className="expenses-top-shell__copy">
            <p className="eyebrow">Entrate</p>
            <h2 className="expenses-top-shell__title">Entrate {formatMonthHeading(filters.month_label)}</h2>
            <p className="expenses-top-shell__subtitle">
              {data.summary?.top_source ? `Fonte principale: ${data.summary.top_source}` : "Registra e controlla tutte le entrate visibili."}
            </p>
          </div>

          {filters.month_label ? (
            <div className="income-top-shell__actions">
              <div className="expenses-top-shell__month">
                <MonthNavigation
                  label={formatMonthHeading(filters.month_label)}
                  onPrevious={() => shiftSelectedMonth(-1)}
                  onNext={() => shiftSelectedMonth(1)}
                />
              </div>
            </div>
          ) : null}
        </div>
      </section>

      <FeedbackBanner type={feedbackType} message={feedback} />

      <div className="section-lower-layout">
        <div className="section-toolbar panel income-toolbar">
          <button
            type="button"
            className="toolbar-button"
            disabled={!filters.search && !isDeleteMode && !isEditMode}
            onClick={handleBackReset}
          >
            ←
          </button>
          <button
            type="button"
            className={`toolbar-button icon-toolbar-button${isSortPanelOpen ? " active" : ""}`}
            onClick={() => setIsSortPanelOpen((current) => !current)}
            aria-label="Ordina entrate"
            title="Ordina"
          >
            <span aria-hidden="true">▾</span>
          </button>
          <button
            type="button"
            className={`toolbar-button wide${isEditMode ? " active" : ""}`}
            onClick={() => {
              setIsEditMode(true);
              setIsDeleteMode(false);
            }}
          >
            Modifica entrata
          </button>
          <button
            type="button"
            className={`toolbar-button danger-lite${isDeleteMode ? " active" : ""}`}
            onClick={() => {
              setIsDeleteMode((current) => !current);
              setIsEditMode(false);
            }}
          >
            Elimina
          </button>
          <input
            className="toolbar-search expense-toolbar-search"
            type="search"
            value={filters.search}
            onChange={(event) => updateFilter("search", event.target.value)}
            placeholder="Fonte o descrizione"
          />
        </div>

        <div className="section-sticky-total">
          <div className="expense-total-pill-react">
            <span>Totale</span>
            <strong>{formatCurrency(data.summary?.total_amount || 0)}</strong>
          </div>
          <div className="expense-balance-pill-react">{data.count} movimenti</div>
        </div>
      </div>

      {isSortPanelOpen ? (
        <div className="expense-sort-popover income-sort-popover">
          {sortOptions.map((option) => (
            <button
              key={option.value}
              type="button"
              className={`expense-sort-option${filters.sort === option.value ? " active" : ""}`}
              onClick={() => updateFilter("sort", option.value)}
            >
              {option.label}
            </button>
          ))}
        </div>
      ) : null}

      <IncomeFeed
        items={data.items}
        isEditMode={isEditMode}
        isDeleteMode={isDeleteMode}
        onEdit={openEditDialog}
        onDelete={(incomeId) => {
          setDialogMode("delete");
          setSelectedIncomeId(incomeId);
        }}
      />

      {dialogMode === "create" || dialogMode === "edit" ? (
        <Dialog
          title={dialogMode === "create" ? "Nuova entrata" : "Modifica entrata"}
          onClose={closeDialog}
          footer={
            <>
              <button type="button" className="secondary-button" onClick={closeDialog}>
                Annulla
              </button>
              <button type="button" className="primary-button" onClick={handleSubmitIncome} disabled={isSubmitting}>
                {isSubmitting ? "Salvataggio..." : dialogMode === "create" ? "Crea entrata" : "Salva modifiche"}
              </button>
            </>
          }
        >
          <IncomeForm form={form} setForm={setForm} formError={formError} />
        </Dialog>
      ) : null}

      {dialogMode === "delete" ? (
        <Dialog
          title="Conferma eliminazione"
          onClose={closeDialog}
          footer={
            <>
              <button type="button" className="secondary-button" onClick={closeDialog}>
                Annulla
              </button>
              <button type="button" className="primary-button danger-button" onClick={handleDeleteIncome} disabled={isSubmitting}>
                {isSubmitting ? "Eliminazione..." : "Elimina"}
              </button>
            </>
          }
        >
          <p>Questa entrata verra eliminata definitivamente.</p>
        </Dialog>
      ) : null}
    </section>
  );

  async function fetchIncomes(activeFilters) {
    const params = new URLSearchParams(activeFilters);
    return api.get(`/api/incomes?${params.toString()}`);
  }

  function openCreateDialog() {
    setDialogMode("create");
    setSelectedIncomeId(null);
    setFormError("");
    setForm(createDefaultIncomeForm());
  }

  function closeDialog() {
    setDialogMode(null);
    setSelectedIncomeId(null);
    setFormError("");
    setIsSubmitting(false);
  }

  function updateFilter(key, value) {
    setFilters((current) => ({ ...current, [key]: value }));
    const next = new URLSearchParams(searchParams);
    if (value && value !== "Tutti" && value !== "date_desc") {
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

  function handleBackReset() {
    if (isDeleteMode) {
      setIsDeleteMode(false);
      return;
    }
    if (isEditMode) {
      setIsEditMode(false);
      return;
    }
    updateFilter("search", "");
  }

  async function refreshIncomesList(message = "", type = "success") {
    const response = await fetchIncomes(filters);
    setData(response);
    setFeedback(message);
    setFeedbackType(type);
  }

  async function openEditDialog(incomeId) {
    setDialogMode("edit");
    setSelectedIncomeId(incomeId);
    setFormError("");
    try {
      const response = await api.get(`/api/incomes/${incomeId}`);
      setForm({
        income_date: response.item.income_date,
        amount: String(response.item.amount ?? ""),
        source: response.item.source || "",
        description: response.item.description || "",
      });
    } catch (requestError) {
      setDialogMode(null);
      setFeedback(requestError.message || "Impossibile caricare il dettaglio dell'entrata.");
      setFeedbackType("error");
    }
  }

  async function handleSubmitIncome() {
    const validationMessage = validateIncomeForm(form);
    if (validationMessage) {
      setFormError(validationMessage);
      return;
    }
    setIsSubmitting(true);
    setFormError("");
    try {
      const payload = buildIncomePayload(form);
      if (dialogMode === "create") {
        await api.post("/api/incomes", payload);
        notifyAppDataChanged({ scope: "incomes" });
        await refreshIncomesList("Entrata creata con successo.");
      } else if (selectedIncomeId) {
        await api.put(`/api/incomes/${selectedIncomeId}`, payload);
        notifyAppDataChanged({ scope: "incomes" });
        await refreshIncomesList("Entrata aggiornata con successo.");
      }
      closeDialog();
    } catch (requestError) {
      setFormError(requestError.message || "Impossibile salvare l'entrata.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleDeleteIncome() {
    if (!selectedIncomeId) {
      return;
    }
    setIsSubmitting(true);
    try {
      await api.delete(`/api/incomes/${selectedIncomeId}`);
      notifyAppDataChanged({ scope: "incomes" });
      await refreshIncomesList("Entrata eliminata con successo.");
      closeDialog();
    } catch (requestError) {
      setFeedback(requestError.message || "Impossibile eliminare l'entrata.");
      setFeedbackType("error");
    } finally {
      setIsSubmitting(false);
    }
  }
}

function IncomeFeed({ items, isEditMode, isDeleteMode, onEdit, onDelete }) {
  if (!items.length) {
    return <div className="panel empty-feed">Nessuna entrata trovata con i filtri selezionati.</div>;
  }

  const isActionMode = isEditMode || isDeleteMode;

  return (
    <div className={`expenses-grouped-list income-grouped-list${isActionMode ? " edit-focus" : ""}`}>
      {groupIncomesByDay(items).map((group) => (
        <section key={group.dateKey} className="couple-day-group income-day-group">
          <div className="couple-day-header income-day-header">
            <strong>{formatDayGroupLabel(group.dateKey)}</strong>
            <span className="credit">+{formatCurrency(group.total)}</span>
          </div>

          <div className="couple-day-card income-day-card">
            {group.items.map((item) => {
              const handleRowAction = () => {
                if (isEditMode) {
                  onEdit(item.id);
                } else if (isDeleteMode) {
                  onDelete(item.id);
                }
              };

              return (
                <article
                  key={item.id}
                  className={`couple-expense-row income-day-row${isActionMode ? " is-interactive" : ""}`}
                  onClick={isActionMode ? handleRowAction : undefined}
                  onKeyDown={(event) => {
                    if (!isActionMode || (event.key !== "Enter" && event.key !== " ")) {
                      return;
                    }
                    event.preventDefault();
                    handleRowAction();
                  }}
                  role={isActionMode ? "button" : undefined}
                  tabIndex={isActionMode ? 0 : undefined}
                >
                  <div className="couple-row-category-icon income-row-icon">
                    <IncomeMiniIcon />
                  </div>

                  <div className="couple-row-main">
                    <strong>{item.source || "Entrata"}</strong>
                    <span>{item.description || "Senza descrizione"}</span>
                    <span className="couple-row-paid-by income-row-source">
                      <i />
                      Entrata
                    </span>
                  </div>

                  <div className="couple-row-impact credit income-row-amount">
                    <strong>{formatCurrency(item.amount)}</strong>
                    <small>{formatShortDayLabel(item.income_date)}</small>
                  </div>

                  <div className="couple-row-actions">
                    <button
                      type="button"
                      className={`expenses-row-delete${isDeleteMode ? " is-active" : ""}`}
                      aria-label={`Elimina ${item.source || "entrata"}`}
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

export function IncomeForm({ form, setForm, formError }) {
  const [isSourceFocused, setIsSourceFocused] = useState(false);
  const [isDescriptionFocused, setIsDescriptionFocused] = useState(false);

  return (
    <div className="expense-form-card income-form-card">
      <div className="expense-amount-row">
        <DateChoice
          value={form.income_date}
          onChange={(value) => setFormValue(setForm, "income_date", value)}
          ariaLabel="Data entrata"
        />
        <AmountInput value={form.amount} onChange={(value) => setFormValue(setForm, "amount", value)} />
        <div className="expense-amount-spacer" aria-hidden="true" />
      </div>

      <div className="expense-form-main-row income-form-main-row">
        <label className="expense-name-control">
          <input
            type="text"
            aria-label="Fonte entrata"
            value={form.source}
            placeholder={isSourceFocused ? "" : "Fonte"}
            onFocus={() => setIsSourceFocused(true)}
            onBlur={() => setIsSourceFocused(false)}
            onChange={(event) => setFormValue(setForm, "source", event.target.value)}
          />
        </label>
      </div>

      <label className="expense-name-control expense-notes-control">
        <textarea
          rows="1"
          aria-label="Descrizione entrata"
          value={form.description}
          placeholder={isDescriptionFocused ? "" : "Descrizione"}
          onFocus={() => setIsDescriptionFocused(true)}
          onBlur={() => setIsDescriptionFocused(false)}
          onChange={(event) => setFormValue(setForm, "description", event.target.value)}
        />
      </label>
      {formError ? <p className="error-message form-message">{formError}</p> : null}
    </div>
  );
}

export function createDefaultIncomeForm() {
  return {
    income_date: new Date().toISOString().slice(0, 10),
    amount: "",
    source: "",
    description: "",
  };
}

export function validateIncomeForm(form) {
  if (!form.income_date) return "La data e obbligatoria.";
  if (!form.source.trim()) return "La fonte e obbligatoria.";
  if (!form.description.trim()) return "La descrizione e obbligatoria.";
  if (!form.amount || Number(form.amount) <= 0) return "L'importo deve essere maggiore di zero.";
  return "";
}

export function buildIncomePayload(form) {
  return {
    income_date: form.income_date,
    amount: Number(form.amount),
    source: form.source.trim(),
    description: form.description.trim(),
  };
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

function formatCurrency(value) {
  return new Intl.NumberFormat("it-IT", { style: "currency", currency: "EUR" }).format(Number(value || 0));
}

function formatShortDate(value) {
  const date = new Date(`${value}T00:00:00`);
  return new Intl.DateTimeFormat("it-IT", { day: "2-digit", month: "2-digit" }).format(date);
}

function groupIncomesByDay(items) {
  const groupsByDate = new Map();
  (items || []).forEach((item) => {
    const dateKey = item.income_date || item.date || "Senza data";
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

function IncomeMiniIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M5 12h14" />
      <path d="m13 6 6 6-6 6" />
      <path d="M7 19V5" />
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
  const date = new Date();
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

function sameObject(left, right) {
  return JSON.stringify(left) === JSON.stringify(right);
}
