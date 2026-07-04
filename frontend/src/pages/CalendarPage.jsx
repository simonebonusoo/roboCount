import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Dialog } from "../components/Dialog";
import { FeedbackBanner } from "../components/FeedbackBanner";
import { MonthNavigation } from "../components/MonthNavigation";
import { api } from "../lib/api";

const filterOptions = [
  { value: "all", label: "Tutto" },
  { value: "incomes", label: "Entrate" },
  { value: "expenses", label: "Uscite" },
];

export function CalendarPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [calendarData, setCalendarData] = useState(null);
  const [selectedDay, setSelectedDay] = useState(null);
  const [dayDetail, setDayDetail] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isDayLoading, setIsDayLoading] = useState(false);
  const [error, setError] = useState("");

  const monthLabel = searchParams.get("month_label") || "";
  const contentFilter = normalizeFilter(searchParams.get("content_filter") || "all");

  useEffect(() => {
    let ignore = false;

    async function loadCalendar() {
      setIsLoading(true);
      setError("");
      try {
        const params = new URLSearchParams({
          content_filter: contentFilter,
          preview_limit: "3",
        });
        if (monthLabel) {
          params.set("month_label", monthLabel);
        }
        const response = await api.get(`/api/calendar?${params.toString()}`);
        if (!ignore) {
          setCalendarData(response);
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
  }, [monthLabel, contentFilter]);

  const selectedFilterLabel = useMemo(
    () => filterOptions.find((option) => option.value === contentFilter)?.label || "Tutto",
    [contentFilter],
  );

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

  async function openDayDetail(day) {
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

  const monthTitle = calendarData?.month?.title || "Calendario";
  const hasEvents = (calendarData?.summary?.event_count || 0) > 0;

  return (
    <section className="page calendar-page">
      <div className="page-header calendar-page-header">
        <div>
          <p className="eyebrow">Calendario</p>
          <h1>Vista mensile</h1>
          <p className="hero-description">
            Movimenti raggruppati per giorno, con entrate e uscite filtrate dal backend.
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
                <CalendarDayCell key={day.date} day={day} onSelect={() => openDayDetail(day)} />
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
            <DayDetail day={dayDetail || selectedDay} />
          )}
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
        {eventCount === 0 && day.is_current_month ? <span className="calendar-no-events">Nessun movimento</span> : null}
      </div>
    </button>
  );
}

function DayDetail({ day }) {
  const events = day?.events || [];

  return (
    <div className="calendar-day-detail">
      <div className="calendar-day-detail-summary">
        <SummaryItem label="Uscite" value={formatCurrency(day?.total_expenses || 0)} />
        <SummaryItem label="Entrate" value={formatCurrency(day?.total_incomes || 0)} />
        <SummaryItem label="Saldo" value={formatCurrency(day?.net_total || 0)} />
      </div>

      {events.length ? (
        <div className="stack-list">
          {events.map((event) => (
            <div key={`${event.type}-${event.id}`} className="calendar-detail-event">
              <EventPreview event={event} />
              <strong>{formatCurrency(event.amount)}</strong>
            </div>
          ))}
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
