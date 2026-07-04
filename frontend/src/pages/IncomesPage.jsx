import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Dialog } from "../components/Dialog";
import { FeedbackBanner } from "../components/FeedbackBanner";
import { MonthNavigation } from "../components/MonthNavigation";
import { StatusView } from "../components/StatusView";
import { api } from "../lib/api";

const defaultFilters = {
  month_label: "Tutti",
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

  const monthOptions = useMemo(() => data?.month_options || ["Tutti"], [data]);
  const sortOptions = data?.filters?.sort_options || [
    { value: "date_desc", label: "Data piu recente" },
    { value: "amount_desc", label: "Importo maggiore" },
    { value: "amount_asc", label: "Importo minore" },
  ];

  useEffect(() => {
    const nextFilters = {
      month_label: searchParams.get("month_label") || "Tutti",
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
    return <StatusView title="Entrate" message="Sto caricando le entrate dal backend." />;
  }

  if (error) {
    return <StatusView title="Errore entrate" message={error} />;
  }

  if (!data) {
    return <StatusView title="Entrate" message="Nessun dato disponibile." />;
  }

  return (
    <section className="page income-workspace">
      <div className="page-header expense-page-header">
        <div>
          <p className="eyebrow">Entrate</p>
          <h2>Entrate del periodo</h2>
          <p className="muted">
            {data.summary?.top_source ? `Fonte principale: ${data.summary.top_source}` : "Registra e controlla tutte le entrate visibili."}
          </p>
        </div>
        <button type="button" className="primary-button" onClick={openCreateDialog}>
          Nuova entrata
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

      <div className="section-lower-layout">
        <div className="section-toolbar panel">
          <button type="button" className="toolbar-button" disabled={!filters.search} onClick={() => updateFilter("search", "")}>
            ←
          </button>
          <button type="button" className={`toolbar-button wide${isEditMode ? " active" : ""}`} onClick={() => setIsEditMode((current) => !current)}>
            Modifica entrata
          </button>
          <select className="toolbar-select" value={filters.sort} onChange={(event) => updateFilter("sort", event.target.value)}>
            {sortOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <input
            className="toolbar-search"
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

      <IncomeFeed
        items={data.items}
        isEditMode={isEditMode}
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
    const options = monthOptions.filter((item) => item !== "Tutti");
    if (!options.length) {
      return;
    }
    const currentIndex = options.indexOf(filters.month_label);
    const safeIndex = currentIndex === -1 ? 0 : currentIndex;
    const nextIndex = Math.max(0, Math.min(options.length - 1, safeIndex + delta));
    updateFilter("month_label", options[nextIndex]);
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
      const payload = {
        income_date: form.income_date,
        amount: Number(form.amount),
        source: form.source.trim(),
        description: form.description.trim(),
      };
      if (dialogMode === "create") {
        await api.post("/api/incomes", payload);
        await refreshIncomesList("Entrata creata con successo.");
      } else if (selectedIncomeId) {
        await api.put(`/api/incomes/${selectedIncomeId}`, payload);
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

function IncomeFeed({ items, isEditMode, onEdit, onDelete }) {
  if (!items.length) {
    return <div className="panel empty-feed">Nessuna entrata trovata con i filtri selezionati.</div>;
  }

  return (
    <div className={`transaction-feed${isEditMode ? " edit-focus" : ""}`}>
      {items.map((item) => (
        <article key={item.id} className="transaction-row-card income-row-card">
          <div className="transaction-date">{formatShortDate(item.income_date)}</div>
          <button type="button" className={`transaction-main${isEditMode ? " is-clickable" : ""}`} onClick={() => (isEditMode ? onEdit(item.id) : undefined)}>
            <strong>{item.source}</strong>
            <span>{item.description}</span>
          </button>
          <span className="transaction-chip">Entrata</span>
          <span className="transaction-amount income">{formatCurrency(item.amount)}</span>
          <div className="transaction-actions">
            <button type="button" className="text-button" onClick={() => onEdit(item.id)}>
              Modifica
            </button>
            <button type="button" className="text-button danger" onClick={() => onDelete(item.id)}>
              Elimina
            </button>
          </div>
        </article>
      ))}
    </div>
  );
}

function IncomeForm({ form, setForm, formError }) {
  return (
    <div className="form-grid">
      <label className="field">
        <span>Data</span>
        <input type="date" value={form.income_date} onChange={(event) => setFormValue(setForm, "income_date", event.target.value)} />
      </label>
      <label className="field">
        <span>Importo</span>
        <input type="number" min="0" step="0.01" value={form.amount} onChange={(event) => setFormValue(setForm, "amount", event.target.value)} />
      </label>
      <div className="amount-stepper field-span">
        <button type="button" onClick={() => adjustAmount(setForm, -1)}>−</button>
        <button type="button" onClick={() => adjustAmount(setForm, 1)}>+</button>
      </div>
      <label className="field field-span">
        <span>Fonte</span>
        <input type="text" value={form.source} onChange={(event) => setFormValue(setForm, "source", event.target.value)} />
      </label>
      <label className="field field-span">
        <span>Descrizione</span>
        <textarea rows="3" value={form.description} onChange={(event) => setFormValue(setForm, "description", event.target.value)} />
      </label>
      {formError ? <p className="error-message form-message">{formError}</p> : null}
    </div>
  );
}

function createDefaultIncomeForm() {
  return {
    income_date: new Date().toISOString().slice(0, 10),
    amount: "",
    source: "",
    description: "",
  };
}

function validateIncomeForm(form) {
  if (!form.income_date) return "La data e obbligatoria.";
  if (!form.source.trim()) return "La fonte e obbligatoria.";
  if (!form.description.trim()) return "La descrizione e obbligatoria.";
  if (!form.amount || Number(form.amount) <= 0) return "L'importo deve essere maggiore di zero.";
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

function sameObject(left, right) {
  return JSON.stringify(left) === JSON.stringify(right);
}
