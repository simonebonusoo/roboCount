import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../lib/api";
import { StatusView } from "../components/StatusView";
import { MonthNavigation } from "../components/MonthNavigation";

const STATUS_OPTIONS = [
  { value: "open", label: "Da regolare" },
  { value: "settled", label: "Pagate" },
  { value: "all", label: "Tutte" },
];

export function CoupleBalancePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [data, setData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const monthLabel = searchParams.get("month_label") || "";
  const statusFilter = searchParams.get("status_filter") || "open";

  useEffect(() => {
    let isMounted = true;

    async function loadBalance() {
      setIsLoading(true);
      setError("");

      try {
        const params = new URLSearchParams({
          month_label: monthLabel || "Tutti",
          status_filter: statusFilter,
        });
        const response = await api.get(`/api/couple-balance?${params.toString()}`);
        if (isMounted) {
          setData(response);
        }
      } catch (requestError) {
        if (isMounted) {
          setError(requestError.message || "Impossibile caricare il saldo di coppia.");
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    loadBalance();

    return () => {
      isMounted = false;
    };
  }, [monthLabel, statusFilter]);

  const monthOptions = useMemo(() => {
    const options = (data?.month_options || []).filter((item) => item && item !== "Tutti");
    return options.sort((left, right) => right.localeCompare(left));
  }, [data]);

  useEffect(() => {
    if (!monthOptions.length || monthLabel) {
      return;
    }

    const next = new URLSearchParams(searchParams);
    next.set("month_label", monthOptions[0]);
    setSearchParams(next, { replace: true });
  }, [monthLabel, monthOptions, searchParams, setSearchParams]);

  if (isLoading && !data) {
    return <StatusView title="Saldo di coppia" message="Sto caricando le spese condivise del periodo." />;
  }

  if (error && !data) {
    return <StatusView title="Errore saldo di coppia" message={error} />;
  }

  if (!data) {
    return <StatusView title="Saldo di coppia" message="Nessun dato disponibile." />;
  }

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <p className="eyebrow">Saldo di coppia</p>
          <h2>Spese condivise del periodo</h2>
          <p className="muted">Vista temporanea ma utile, collegata ai dati reali del backend.</p>
        </div>
      </div>

      {monthLabel ? (
        <MonthNavigation
          label={formatMonthHeading(monthLabel)}
          onPrevious={() => shiftSelectedMonth(-1)}
          onNext={() => shiftSelectedMonth(1)}
        />
      ) : null}

      <div className="status-pill-row">
        {STATUS_OPTIONS.map((option) => (
          <button
            key={option.value}
            type="button"
            className={statusFilter === option.value ? "status-pill active" : "status-pill"}
            onClick={() => updateParams({ status_filter: option.value })}
          >
            {option.label}
          </button>
        ))}
      </div>

      <div className="metric-grid metric-grid-three">
        <SummaryCard title="Saldo" value={buildBalanceLabel(data.summary?.balance || 0)} />
        <SummaryCard title="Totale condiviso" value={formatCurrency(data.summary?.shared_total || 0)} />
        <SummaryCard title="Da regolare" value={String(data.summary?.open_items || 0)} />
      </div>

      <div className="panel table-panel">
        {data.items?.length ? (
          <table>
            <thead>
              <tr>
                <th>Data</th>
                <th>Nome</th>
                <th>Categoria</th>
                <th>Pagata da</th>
                <th>Stato</th>
                <th>Importo</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((item) => (
                <tr key={item.id}>
                  <td>{item.expense_date}</td>
                  <td>{item.name || item.description || "Spesa condivisa"}</td>
                  <td>{item.category}</td>
                  <td>{item.paid_by}</td>
                  <td>{item.is_settled ? "Pagata" : "Da regolare"}</td>
                  <td>{formatCurrency(item.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="muted">Nessuna spesa condivisa con i filtri correnti.</p>
        )}
      </div>
    </section>
  );

  function updateParams(updates) {
    const next = new URLSearchParams(searchParams);
    Object.entries(updates).forEach(([key, value]) => {
      if (value) {
        next.set(key, value);
      } else {
        next.delete(key);
      }
    });
    setSearchParams(next, { replace: true });
  }

  function shiftSelectedMonth(delta) {
    const currentIndex = monthOptions.indexOf(monthLabel);
    if (currentIndex === -1) {
      return;
    }
    const nextIndex = Math.max(0, Math.min(monthOptions.length - 1, currentIndex + delta));
    updateParams({ month_label: monthOptions[nextIndex] });
  }
}

function SummaryCard({ title, value }) {
  return (
    <div className="panel metric-card">
      <span>{title}</span>
      <strong>{value}</strong>
    </div>
  );
}

function formatCurrency(value) {
  return new Intl.NumberFormat("it-IT", {
    style: "currency",
    currency: "EUR",
  }).format(Number(value || 0));
}

function formatMonthHeading(monthLabel) {
  if (!monthLabel) {
    return "";
  }
  const [year, month] = monthLabel.split("-");
  const date = new Date(`${year}-${month}-01T00:00:00`);
  return new Intl.DateTimeFormat("it-IT", { month: "long", year: "numeric" }).format(date);
}

function buildBalanceLabel(balance) {
  if (balance > 0) {
    return `+${formatCurrency(balance)}`;
  }
  if (balance < 0) {
    return `-${formatCurrency(Math.abs(balance))}`;
  }
  return "In pari";
}
