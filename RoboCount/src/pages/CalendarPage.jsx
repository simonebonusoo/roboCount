import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Dialog } from "../components/Dialog";
import { FeedbackBanner } from "../components/FeedbackBanner";
import { MonthNavigation } from "../components/MonthNavigation";
import { useAuth } from "../context/AuthContext";
import { api, notifyAppDataChanged, subscribeAppDataChanged } from "../lib/api";
import {
  ExpenseForm,
  buildExpensePayload,
  createDefaultExpenseForm,
  normalizeExpenseForForm,
  validateExpenseForm,
} from "./ExpensesPage";

const filterOptions = [
  { value: "all", label: "Tutto" },
  { value: "incomes", label: "Entrate" },
  { value: "expenses", label: "Uscite" },
];

export function CalendarPage() {
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [calendarData, setCalendarData] = useState(null);
  const [meta, setMeta] = useState(null);
  const [selectedDay, setSelectedDay] = useState(null);
  const [dayDetail, setDayDetail] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isDayLoading, setIsDayLoading] = useState(false);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState("");
  const [expenseDialogMode, setExpenseDialogMode] = useState(null);
  const [selectedExpenseId, setSelectedExpenseId] = useState(null);
  const [expenseToDelete, setExpenseToDelete] = useState(null);
  const [expenseForm, setExpenseForm] = useState(createDefaultExpenseForm(user?.username || "", user?.account_type));
  const [formError, setFormError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  const monthLabel = searchParams.get("month_label") || "";
  const contentFilter = normalizeFilter(searchParams.get("content_filter") || "all");

  useEffect(() => {
    if (!user?.username) {
      return;
    }
    setExpenseForm(createDefaultExpenseForm(user.username, user.account_type));
  }, [user]);

  useEffect(() => {
    let ignore = false;

    async function loadCalendar() {
      setIsLoading(true);
      setError("");
      try {
        const [calendarResponse, metaResponse] = await Promise.all([
          fetchCalendar(),
          api.get("/api/meta/options"),
        ]);
        if (!ignore) {
          setCalendarData(calendarResponse);
          setMeta(metaResponse);
        }
      } catch (err) {
        if (!ignore) {
          setError(err.message || "Calendario non disponibile.");
          setCalendarData(null);
        }
      } finally {
        if (!ignore) {
          setIsLoading(false);
        }
      }
    }

    loadCalendar();

    return () => {
      ignore = true;
    };
  }, [monthLabel, contentFilter, reloadKey]);

  useEffect(() => subscribeAppDataChanged(() => setReloadKey((current) => current + 1)), []);

  const selectedFilterLabel = useMemo(
    () => filterOptions.find((option) => option.value === contentFilter)?.label || "Tutto",
    [contentFilter],
  );

  const payerOptions = meta?.usernames || [user?.username].filter(Boolean);
  const categoryOptions = meta?.categories || [];
  const splitOptions = meta?.split_options || ["equal", "custom"];
  const expenseTypeOptions = meta?.expense_types || ["Personale", "Condivisa"];

  function updateParams(nextValues) {
    const next = new URLSearchParams(searchParams);
    Object.entries(nextValues).forEach(([key, value]) => {
      if (value) {
        next.set(key, value);
      } else {
        next.delete(key);
      }
    });
    setSearchParams(next);
  }

  function handleMonthChange(nextMonthLabel) {
    if (!nextMonthLabel) {
      return;
    }
    updateParams({ month_label: nextMonthLabel });
  }

  function handleFilterChange(nextFilter) {
    updateParams({ content_filter: nextFilter });
  }

  async function fetchCalendar() {
    const params = new URLSearchParams({
      content_filter: contentFilter,
      preview_limit: "3",
    });
    if (monthLabel) {
      params.set("month_label", monthLabel);
    }
    return api.get(`/api/calendar?${params.toString()}`);
  }

  async function loadDayDetail(day) {
    setSelectedDay(day);
    setDayDetail(null);
    setIsDayLoading(true);
    try {
      const response = await api.get(
        `/api/calendar/day/${encodeURIComponent(day.date)}?content_filter=${encodeURIComponent(contentFilter)}`,
      );
      setDayDetail(response.day);
    } catch (err) {
      setDayDetail({
        ...day,
        events: [],
        preview_events: [],
        error: err.message || "Dettaglio giorno non disponibile.",
      });
    } finally {
      setIsDayLoading(false);
    }
  }

  function openDayAction(day) {
    if ((day.event_count || 0) === 0 && day.is_current_month) {
      openCreateExpenseDialog(day.date);
      return;
    }
    loadDayDetail(day);
  }

  function openCreateExpenseDialog(dateValue) {
    setSelectedExpenseId(null);
    setExpenseToDelete(null);
    setFormError("");
    setSelectedDay(null);
    setDayDetail(null);
    setExpenseDialogMode("create");
    setExpenseForm(createDefaultExpenseForm(user?.username || "", user?.account_type, dateValue));
  }

  async function openEditExpenseDialog(expenseId) {
    setFormError("");
    setExpenseToDelete(null);
    try {
      const response = await api.get(`/api/expenses/${expenseId}`);
      setSelectedExpenseId(expenseId);
      setSelectedDay(null);
      setDayDetail(null);
      setExpenseDialogMode("edit");
      setExpenseForm(normalizeExpenseForForm(response.item, user?.username || ""));
    } catch (requestError) {
      setFeedback(requestError.message || "Impossibile caricare la spesa.");
    }
  }

  function handleCategoryCreated(categoryName) {
    setMeta((current) => {
      if (!current || current.categories?.some((item) => item.toLowerCase() === categoryName.toLowerCase())) {
        return current;
      }
      return { ...current, categories: [...(current.categories || []), categoryName] };
    });
  }

  function handleCategoryDeleted(categoryName) {
    setMeta((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        categories: (current.categories || []).filter((item) => item.toLowerCase() !== categoryName.toLowerCase()),
      };
    });
  }

  async function handleSubmitExpense() {
    const validationMessage = validateExpenseForm(expenseForm, user?.username || "");
    if (validationMessage) {
      setFormError(validationMessage);
      return;
    }
    setIsSubmitting(true);
    setFormError("");
    try {
      const payload = buildExpensePayload(expenseForm, user?.username || "");
      if (expenseDialogMode === "create") {
        await api.post("/api/expenses", payload);
        setFeedback("Spesa creata con successo.");
      } else if (selectedExpenseId) {
        await api.put(`/api/expenses/${selectedExpenseId}`, payload);
        setFeedback("Spesa aggiornata con successo.");
      }
      notifyAppDataChanged({ scope: "expenses" });
      await refreshCalendarAndSelectedDay(expenseForm.expense_date);
      closeExpenseDialog();
    } catch (requestError) {
      setFormError(requestError.message || "Impossibile salvare la spesa.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleDeleteExpense() {
    if (!expenseToDelete?.id) {
      return;
    }
    setIsSubmitting(true);
    setFormError("");
    try {
      await api.delete(`/api/expenses/${expenseToDelete.id}`);
      notifyAppDataChanged({ scope: "expenses" });
      setFeedback("Spesa eliminata con successo.");
      await refreshCalendarAndSelectedDay(expenseToDelete.date);
      setExpenseToDelete(null);
    } catch (requestError) {
      setFormError(requestError.message || "Impossibile eliminare la spesa.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function refreshCalendarAndSelectedDay(dayDate = "") {
    const calendarResponse = await fetchCalendar();
    setCalendarData(calendarResponse);
    if (!dayDate) {
      return;
    }
    const nextDay = findDayInCalendar(calendarResponse, dayDate);
    if (!nextDay) {
      setSelectedDay(null);
      setDayDetail(null);
      return;
    }
    setSelectedDay(nextDay);
    const response = await api.get(
      `/api/calendar/day/${encodeURIComponent(dayDate)}?content_filter=${encodeURIComponent(contentFilter)}`,
    );
    setDayDetail(response.day || nextDay);
  }

  function closeExpenseDialog() {
    setExpenseDialogMode(null);
    setSelectedExpenseId(null);
    setFormError("");
    setIsSubmitting(false);
  }

  const monthTitle = calendarData?.month?.title || "Calendario";
  const hasEvents = (calendarData?.summary?.event_count || 0) > 0;

  return (
    <section className="page calendar-page">
      <div className="page-header calendar-page-header">
        <div>
          <p className="eyebrow">Calendario</p>
          <h1>Vista mensile</h1>
          <p className="hero-description">
            Ogni giorno diventa un accesso rapido per inserire o gestire le spese.
          </p>
        </div>
        <div className="calendar-filter" aria-label="Filtro calendario">
          {filterOptions.map((option) => (
            <button
              key={option.value}
              type="button"
              className={`calendar-filter-button${contentFilter === option.value ? " active" : ""}`}
              onClick={() => handleFilterChange(option.value)}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      <div className="panel calendar-toolbar-panel">
        <MonthNavigation
          label={monthTitle}
          onPrevious={() => handleMonthChange(calendarData?.month?.prev_month_label)}
          onNext={() => handleMonthChange(calendarData?.month?.next_month_label)}
        />
        {calendarData ? (
          <div className="calendar-summary-strip">
            <SummaryItem label="Filtro" value={selectedFilterLabel} />
            <SummaryItem label="Eventi" value={calendarData.summary.event_count} />
            <SummaryItem label="Uscite" value={formatCurrency(calendarData.summary.total_expenses)} />
            <SummaryItem label="Entrate" value={formatCurrency(calendarData.summary.total_incomes)} />
          </div>
        ) : null}
      </div>

      <FeedbackBanner type="success" message={feedback} />
      <FeedbackBanner type="error" message={error} />

      {isLoading ? (
        <div className="panel calendar-state">Caricamento calendario...</div>
      ) : calendarData ? (
        <div className="calendar-shell-react">
          <div className="calendar-grid-react">
            {calendarData.weekdays.map((weekday) => (
              <div key={weekday} className="calendar-weekday-react">
                {weekday}
              </div>
            ))}

            {calendarData.weeks.flatMap((week) =>
              week.days.map((day) => (
                <CalendarDayCell key={day.date} day={day} onSelect={() => openDayAction(day)} />
              )),
            )}
          </div>

          {!hasEvents ? (
            <div className="panel calendar-empty-state">
              Nessun movimento per questo mese con il filtro selezionato.
            </div>
          ) : null}
        </div>
      ) : (
        <div className="panel calendar-state">Calendario non disponibile.</div>
      )}

      {selectedDay ? (
        <Dialog title={formatDayTitle(selectedDay.date)} onClose={() => setSelectedDay(null)}>
          {isDayLoading ? (
            <p className="muted">Caricamento dettaglio...</p>
          ) : dayDetail?.error ? (
            <p className="error-message">{dayDetail.error}</p>
          ) : (
            <DayDetail
              day={dayDetail || selectedDay}
              onCreateExpense={() => openCreateExpenseDialog(selectedDay.date)}
              onEditExpense={openEditExpenseDialog}
              onDeleteExpense={(event) => setExpenseToDelete(event)}
            />
          )}
        </Dialog>
      ) : null}

      {expenseDialogMode ? (
        <Dialog
          title={expenseDialogMode === "create" ? "Nuova spesa" : "Modifica spesa"}
          onClose={closeExpenseDialog}
          footer={
            <>
              <button type="button" className="secondary-button" onClick={closeExpenseDialog}>
                Annulla
              </button>
              <button type="button" className="primary-button" onClick={handleSubmitExpense} disabled={isSubmitting}>
                {isSubmitting ? "Salvataggio..." : expenseDialogMode === "create" ? "Crea spesa" : "Salva modifiche"}
              </button>
            </>
          }
        >
          <ExpenseForm
            form={expenseForm}
            setForm={setExpenseForm}
            formError={formError}
            payerOptions={payerOptions}
            categoryOptions={categoryOptions}
            splitOptions={splitOptions}
            expenseTypeOptions={expenseTypeOptions}
            currentUsername={user?.username || ""}
            onCategoryCreated={handleCategoryCreated}
          />
        </Dialog>
      ) : null}

      {expenseToDelete ? (
        <Dialog
          title="Conferma eliminazione"
          onClose={() => setExpenseToDelete(null)}
          footer={
            <>
              <button type="button" className="secondary-button" onClick={() => setExpenseToDelete(null)}>
                Annulla
              </button>
              <button type="button" className="primary-button danger-button" onClick={handleDeleteExpense} disabled={isSubmitting}>
                {isSubmitting ? "Eliminazione..." : "Elimina spesa"}
              </button>
            </>
          }
        >
          {formError ? <p className="error-message">{formError}</p> : null}
          <p>Questa spesa verra eliminata definitivamente.</p>
        </Dialog>
      ) : null}
    </section>
  );
}

function CalendarDayCell({ day, onSelect }) {
  const eventCount = day.event_count || 0;
  const hasTotal = Number(day.total_expenses || 0) > 0 || Number(day.total_incomes || 0) > 0;

  return (
    <button
      type="button"
      className={[
        "calendar-day-react",
        day.is_current_month ? "" : "is-other-month",
        day.is_today ? "is-today" : "",
      ].filter(Boolean).join(" ")}
      onClick={onSelect}
    >
      <div className="calendar-day-react-top">
        <span className="calendar-day-react-number">{day.day_number}</span>
        {day.is_today ? <span className="calendar-today-badge">Oggi</span> : null}
      </div>

      {hasTotal ? (
        <div className="calendar-day-react-total">
          {Number(day.total_expenses || 0) > 0 ? <span>Uscite {formatCurrency(day.total_expenses)}</span> : null}
          {Number(day.total_incomes || 0) > 0 ? <span>Entrate {formatCurrency(day.total_incomes)}</span> : null}
        </div>
      ) : null}

      <div className="calendar-event-list-react">
        {(day.preview_events || []).map((event) => (
          <EventPreview key={`${event.type}-${event.id}`} event={event} />
        ))}
        {day.remaining_count > 0 ? (
          <div className="calendar-more-events">+{day.remaining_count} altri</div>
        ) : null}
        {eventCount === 0 && day.is_current_month ? (
          <span className="calendar-no-events">
            <span>Nessuna spesa</span>
            <strong className="calendar-no-events-plus" aria-hidden="true">+</strong>
          </span>
        ) : null}
      </div>
    </button>
  );
}

function DayDetail({ day, onCreateExpense, onEditExpense, onDeleteExpense }) {
  const events = day?.events || [];

  return (
    <div className="calendar-day-detail">
      <div className="calendar-day-detail-summary">
        <SummaryItem label="Uscite" value={formatCurrency(day?.total_expenses || 0)} />
        <SummaryItem label="Entrate" value={formatCurrency(day?.total_incomes || 0)} />
        <SummaryItem label="Saldo" value={formatCurrency(day?.net_total || 0)} />
      </div>

      <div className="calendar-day-detail-actions">
        <button type="button" className="secondary-button" onClick={onCreateExpense}>
          Nuova spesa
        </button>
      </div>

      {events.length ? (
        <div className="stack-list">
          {events.map((event) => {
            const isExpense = event.type === "expense";
            return (
              <div key={`${event.type}-${event.id}`} className="calendar-detail-event calendar-detail-event-card">
                <div className="calendar-detail-event-main">
                  <EventPreview event={event} />
                  <strong>{formatCurrency(event.amount)}</strong>
                </div>
                {isExpense ? (
                  <div className="calendar-detail-event-actions">
                    <button type="button" className="icon-button calendar-event-icon-button" onClick={() => onEditExpense(event.id)} aria-label="Modifica spesa" title="Modifica spesa">
                      <svg aria-hidden="true" viewBox="0 0 24 24">
                        <path d="M4 20h4l9.5-9.5-4-4L4 16v4Z" />
                        <path d="M13.5 6.5l4 4" />
                      </svg>
                    </button>
                    <button
                      type="button"
                      className="icon-button calendar-event-icon-button calendar-event-icon-button-danger"
                      aria-label="Elimina spesa"
                      title="Elimina spesa"
                      onClick={() => onDeleteExpense({ id: event.id, date: day?.date || event.date })}
                    >
                      <svg aria-hidden="true" viewBox="0 0 24 24">
                        <path d="M6 7h12" />
                        <path d="M9.5 7V5.5h5V7" />
                        <path d="M8 7l.7 11h6.6L16 7" />
                      </svg>
                    </button>
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      ) : (
        <p className="muted">Nessun movimento registrato in questo giorno.</p>
      )}
    </div>
  );
}

function EventPreview({ event }) {
  return (
    <div className={`calendar-event-react ${event.type}`}>
      <span className="calendar-event-dot-react" />
      <span>{event.display_label || event.title}</span>
    </div>
  );
}

function SummaryItem({ label, value }) {
  return (
    <div className="calendar-summary-item">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function findDayInCalendar(calendarData, targetDate) {
  if (!calendarData?.weeks) {
    return null;
  }
  for (const week of calendarData.weeks) {
    for (const day of week.days) {
      if (day.date === targetDate) {
        return day;
      }
    }
  }
  return null;
}

function normalizeFilter(value) {
  return filterOptions.some((option) => option.value === value) ? value : "all";
}

function formatCurrency(value) {
  return new Intl.NumberFormat("it-IT", {
    style: "currency",
    currency: "EUR",
  }).format(Number(value || 0));
}

function formatDayTitle(value) {
  const date = new Date(`${value}T00:00:00`);
  return new Intl.DateTimeFormat("it-IT", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(date);
}
