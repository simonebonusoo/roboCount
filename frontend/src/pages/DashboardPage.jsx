import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { StatusView } from "../components/StatusView";

export function DashboardPage() {
  const [data, setData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedMonth, setSelectedMonth] = useState("Tutti");

  useEffect(() => {
    let isMounted = true;

    async function loadDashboard() {
      setIsLoading(true);
      setError("");

      try {
        const response = await api.get(`/api/dashboard?month_label=${encodeURIComponent(selectedMonth)}`);
        if (isMounted) {
          setData(response);
        }
      } catch (requestError) {
        if (isMounted) {
          setError(requestError.message || "Impossibile caricare la dashboard.");
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    loadDashboard();

    return () => {
      isMounted = false;
    };
  }, [selectedMonth]);

  if (isLoading) {
    return <StatusView title="Dashboard" message="Sto caricando i dati principali." />;
  }

  if (error) {
    return <StatusView title="Errore dashboard" message={error} />;
  }

  if (!data) {
    return <StatusView title="Dashboard vuota" message="Nessun dato disponibile." />;
  }

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <p className="eyebrow">Dashboard</p>
          <h2>Panoramica finanziaria</h2>
        </div>
        <label className="inline-field">
          <span>Mese</span>
          <select value={selectedMonth} onChange={(event) => setSelectedMonth(event.target.value)}>
            {(data.month_options || []).map((monthOption) => (
              <option key={monthOption} value={monthOption}>
                {monthOption}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="metric-grid">
        <MetricCard title="Totale mese" value={formatCurrency(data.metrics.total_month)} />
        <MetricCard title="Spese personali" value={formatCurrency(data.metrics.my_personal)} />
        <MetricCard title="Spese condivise" value={formatCurrency(data.metrics.shared_total)} />
        <MetricCard title="Saldo coppia" value={formatCurrency(data.metrics.balance)} />
      </div>

      <div className="content-grid">
        <DataList
          title="Categorie"
          emptyMessage="Nessuna categoria con dati nel periodo selezionato."
          items={(data.category_summary || []).map((item) => ({
            key: item.category,
            title: item.category,
            subtitle: `${item.numero_spese} spese`,
            value: formatCurrency(item.totale),
          }))}
        />

        <DataList
          title="Spese recenti"
          emptyMessage="Nessuna spesa visibile."
          items={(data.recent_expenses || []).map((item) => ({
            key: item.id,
            title: item.name || item.description,
            subtitle: `${item.expense_date} · ${item.category} · ${item.paid_by}`,
            value: formatCurrency(item.amount),
          }))}
        />

        <DataList
          title="Entrate recenti"
          emptyMessage="Nessuna entrata visibile."
          items={(data.recent_incomes || []).map((item) => ({
            key: item.id,
            title: item.source,
            subtitle: `${item.income_date} · ${item.description}`,
            value: formatCurrency(item.amount),
          }))}
        />
      </div>
    </section>
  );
}

function MetricCard({ title, value }) {
  return (
    <div className="panel metric-card">
      <span>{title}</span>
      <strong>{value}</strong>
    </div>
  );
}

function DataList({ title, items, emptyMessage }) {
  return (
    <div className="panel">
      <div className="section-heading">
        <h3>{title}</h3>
      </div>
      {items.length === 0 ? (
        <p className="muted">{emptyMessage}</p>
      ) : (
        <div className="stack-list">
          {items.map((item) => (
            <div key={item.key} className="stack-item">
              <div>
                <strong>{item.title}</strong>
                <p className="muted">{item.subtitle}</p>
              </div>
              <span>{item.value}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function formatCurrency(value) {
  return new Intl.NumberFormat("it-IT", {
    style: "currency",
    currency: "EUR",
  }).format(Number(value || 0));
}
