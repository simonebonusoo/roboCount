import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../lib/api";
import { StatusView } from "../components/StatusView";
import { MonthNavigation } from "../components/MonthNavigation";
import { useAuth } from "../context/AuthContext";

const KPI_CONFIG = [
  { key: "total_month", label: "USCITE" },
  { key: "my_personal", label: "PERSONALI" },
  { key: "shared_total", label: "CONDIVISE" },
  { key: "net_month", label: "SALDO" },
  { key: "balance", label: "SALDO COPPIA" },
];

export function HomePage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { user } = useAuth();
  const [selectedMonth, setSelectedMonth] = useState(searchParams.get("month_label") || "");
  const [scope, setScope] = useState("Mensile");
  const [dashboardData, setDashboardData] = useState(null);
  const [allExpenses, setAllExpenses] = useState([]);
  const [allIncomes, setAllIncomes] = useState([]);
  const [allSharedExpenses, setAllSharedExpenses] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let isMounted = true;

    async function bootstrap() {
      setIsLoading(true);
      setError("");

      try {
        const [expensesResponse, incomesResponse, sharedResponse] = await Promise.all([
          api.get("/api/expenses?month_label=Tutti"),
          api.get("/api/incomes?month_label=Tutti"),
          api.get("/api/couple-balance?month_label=Tutti&status_filter=all"),
        ]);

        if (!isMounted) {
          return;
        }

        setAllExpenses(expensesResponse.items || []);
        setAllIncomes(incomesResponse.items || []);
        setAllSharedExpenses(sharedResponse.items || []);

        const initialMonth = searchParams.get("month_label") || pickInitialMonth([
          ...(expensesResponse.month_options || []),
          ...(incomesResponse.month_options || []),
        ]);
        setSelectedMonth(initialMonth);
      } catch (requestError) {
        if (isMounted) {
          setError(requestError.message || "Impossibile caricare la home.");
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
    if (!selectedMonth) {
      return;
    }

    let isMounted = true;

    async function loadDashboard() {
      setIsLoading(true);
      setError("");

      try {
        const response = await api.get(`/api/dashboard?month_label=${encodeURIComponent(selectedMonth)}`);
        if (!isMounted) {
          return;
        }
        setDashboardData(response);
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

  const monthOptions = useMemo(
    () => normalizeMonthOptions(dashboardData?.month_options || [], allExpenses, allIncomes),
    [dashboardData, allExpenses, allIncomes],
  );

  useEffect(() => {
    if (!monthOptions.length) {
      return;
    }
    if (!selectedMonth || !monthOptions.includes(selectedMonth)) {
      setSelectedMonth(monthOptions[0]);
    }
  }, [monthOptions, selectedMonth]);

  const homeSummary = useMemo(() => {
    if (!selectedMonth) {
      return createEmptySummary();
    }

    const activeYear = selectedMonth.split("-")[0];
    const expensePool = scope === "Annuale"
      ? allExpenses.filter((item) => String(item.month_label || "").startsWith(activeYear))
      : allExpenses.filter((item) => item.month_label === selectedMonth);
    const incomePool = scope === "Annuale"
      ? allIncomes.filter((item) => String(item.month_label || "").startsWith(activeYear))
      : allIncomes.filter((item) => item.month_label === selectedMonth);
    const sharedPool = scope === "Annuale"
      ? allSharedExpenses.filter((item) => String(item.month_label || "").startsWith(activeYear))
      : allSharedExpenses.filter((item) => item.month_label === selectedMonth);

    const totalExpenses = sumAmounts(expensePool);
    const totalIncomes = sumAmounts(incomePool);
    const savings = totalIncomes - totalExpenses;
    const coupleBalance = computeCoupleBalance(sharedPool, user?.username || "");

    return {
      periodLabel: scope === "Annuale" ? activeYear : formatMonthHeading(selectedMonth),
      contextNote: scope === "Annuale" ? "Visione complessiva del periodo in corso." : "Panoramica del mese attivo con focus immediato sul saldo.",
      totalExpenses,
      totalIncomes,
      savings,
      expenseCount: expensePool.length,
      coupleBalance,
      balanceNote: buildSavingsNote(savings),
      coupleBalanceNote: buildCoupleBalanceNote(coupleBalance),
    };
  }, [allExpenses, allIncomes, allSharedExpenses, scope, selectedMonth, user]);

  const kpiValues = useMemo(() => {
    if (!dashboardData) {
      return {};
    }

    const monthExpenses = allExpenses.filter((item) => item.month_label === selectedMonth);
    const monthIncomes = allIncomes.filter((item) => item.month_label === selectedMonth);
    const monthBalance = computeCoupleBalance(
      allSharedExpenses.filter((item) => item.month_label === selectedMonth),
      user?.username || "",
    );

    return {
      total_month: dashboardData.metrics?.total_month || 0,
      my_personal: dashboardData.metrics?.my_personal || 0,
      shared_total: dashboardData.metrics?.shared_total || 0,
      net_month: sumAmounts(monthIncomes) - sumAmounts(monthExpenses),
      balance: monthBalance,
    };
  }, [allExpenses, allIncomes, allSharedExpenses, dashboardData, selectedMonth, user]);

  if (isLoading && !dashboardData) {
    return <StatusView title="Home" message="Sto ricostruendo la panoramica principale." />;
  }

  if (error && !dashboardData) {
    return <StatusView title="Errore home" message={error} />;
  }

  if (!selectedMonth || !dashboardData) {
    return <StatusView title="Home" message="Nessun dato disponibile per la home." />;
  }

  return (
    <section className="page home-page">
      <div className="home-welcome-shell">
        <div>
          <div className="home-welcome-title">Ciao {user?.username || "Utente"}</div>
          <div className="home-welcome-copy">Ogni movimento che registri ti avvicina a un mese piu sereno.</div>
        </div>
      </div>

      <div className="hero-layout">
        <div className="hero-left-column">
          <section className="hero-surface hero-visual-surface">
            <div className="hero-image-frame">
              <img
                src="/hero-couple-balance-transparent.png"
                alt="Robot che gestiscono i risparmi di coppia"
                className="hero-image"
              />
            </div>
          </section>

          <section className="summary-cta-card">
            <div>
              <div className="summary-cta-eyebrow">Resoconto mensile</div>
              <div className="summary-cta-copy">
                Analizza e scarica PDF o CSV dei tuoi movimenti mensili.
              </div>
            </div>
            <button
              type="button"
              className="secondary-button"
              onClick={() => navigate(buildExpenseUrl({ month_label: selectedMonth, summary: "1" }))}
            >
              Apri riepilogo
            </button>
          </section>
        </div>

        <div className="hero-right-column">
          <section className="financial-panel">
            <div className="financial-panel-header">
              <div>
                <p className="eyebrow">Quadro finanziario</p>
                <h2>{homeSummary.periodLabel}</h2>
                <p className="financial-context-note">{homeSummary.contextNote}</p>
              </div>
              <div className="scope-toggle">
                <button
                  type="button"
                  className={scope === "Mensile" ? "scope-button active" : "scope-button"}
                  onClick={() => setScope("Mensile")}
                >
                  Mensile
                </button>
                <button
                  type="button"
                  className={scope === "Annuale" ? "scope-button active" : "scope-button"}
                  onClick={() => setScope("Annuale")}
                >
                  Annuale
                </button>
              </div>
            </div>

            <div className="financial-card-grid">
              <FinancialCard
                label="Spese"
                value={formatCurrency(homeSummary.totalExpenses)}
                note={`${homeSummary.expenseCount} movimenti in uscita`}
                accent="expense"
              />
              <FinancialCard
                label="Risparmi"
                value={formatCurrency(homeSummary.savings)}
                note={homeSummary.balanceNote}
                accent={homeSummary.savings >= 0 ? "positive" : "negative"}
              />
              <FinancialCard
                label="Saldo di coppia"
                value={formatCurrency(Math.abs(homeSummary.coupleBalance))}
                note={homeSummary.coupleBalanceNote}
                accent={homeSummary.coupleBalance > 0 ? "positive" : homeSummary.coupleBalance < 0 ? "negative" : "neutral"}
              />
            </div>
          </section>
        </div>
      </div>

      <MonthNavigation
        label={formatMonthHeading(selectedMonth)}
        onPrevious={() => shiftSelectedMonth(-1)}
        onNext={() => shiftSelectedMonth(1)}
      />

      <div className="kpi-grid">
        {KPI_CONFIG.map((item) => (
          <button
            key={item.key}
            type="button"
            className="kpi-card"
            onClick={() => navigate(handleMetricNavigation(item.key))}
          >
            <span className="kpi-label">{item.label}</span>
            <strong className="kpi-value">
              {item.key === "balance" ? buildBalanceLabel(kpiValues[item.key] || 0) : formatCurrency(kpiValues[item.key] || 0)}
            </strong>
          </button>
        ))}
      </div>

      <div className="metric-detail-card">
        <div>
          <p className="eyebrow">Dettaglio dashboard</p>
          <h3>Azioni rapide</h3>
          <p className="metric-detail-copy">
            Le card KPI aprono direttamente la vista coerente con il mese attivo e con il filtro giusto.
          </p>
        </div>
        <button
          type="button"
          className="secondary-button"
          onClick={() => navigate(buildExpenseUrl({ month_label: selectedMonth, summary: "1" }))}
        >
          Apri riepilogo
        </button>
      </div>
    </section>
  );

  function shiftSelectedMonth(delta) {
    const currentIndex = monthOptions.indexOf(selectedMonth);
    if (currentIndex === -1) {
      return;
    }
    const nextIndex = Math.max(0, Math.min(monthOptions.length - 1, currentIndex + delta));
    persistMonth(monthOptions[nextIndex]);
  }

  function persistMonth(month) {
    setSelectedMonth(month);
    const next = new URLSearchParams(searchParams);
    next.set("month_label", month);
    setSearchParams(next, { replace: true });
  }

  function buildExpenseUrl(extraFilters = {}) {
    const params = new URLSearchParams({
      month_label: selectedMonth,
      category: "Tutte",
      payer: "Tutti",
      expense_type: "Tutte",
      ...extraFilters,
    });
    return `/expenses?${params.toString()}`;
  }

  function handleMetricNavigation(metricKey) {
    if (metricKey === "my_personal") {
      return buildExpenseUrl({ expense_type: "Personale" });
    }
    if (metricKey === "shared_total") {
      return buildExpenseUrl({ expense_type: "Condivisa" });
    }
    if (metricKey === "balance") {
      return `/couple-balance?month_label=${encodeURIComponent(selectedMonth)}&status_filter=open`;
    }
    return buildExpenseUrl({ summary: metricKey === "net_month" ? "net" : "1" });
  }
}

function FinancialCard({ label, value, note, accent }) {
  return (
    <div className={`financial-card financial-card-${accent}`}>
      <div className="financial-card-label">{label}</div>
      <div className="financial-card-value">{value}</div>
      <div className="financial-card-note">{note}</div>
    </div>
  );
}

function normalizeMonthOptions(options, expenses, incomes) {
  const merged = new Set(
    [
      ...options,
      ...expenses.map((item) => item.month_label).filter(Boolean),
      ...incomes.map((item) => item.month_label).filter(Boolean),
    ].filter((item) => item && item !== "Tutti"),
  );

  return Array.from(merged).sort((left, right) => right.localeCompare(left));
}

function pickInitialMonth(options) {
  const normalized = Array.from(new Set(options.filter((item) => item && item !== "Tutti"))).sort((left, right) => right.localeCompare(left));
  const currentMonth = new Date().toISOString().slice(0, 7);
  return normalized.find((item) => item === currentMonth) || normalized[0] || "";
}

function sumAmounts(items) {
  return items.reduce((total, item) => total + Number(item.amount || 0), 0);
}

function computeCoupleBalance(items, currentUsername) {
  if (!currentUsername) {
    return 0;
  }

  return items.reduce((total, item) => {
    const ratio = Number(item.split_ratio ?? 0.5);
    const amount = Number(item.amount || 0);
    const partnerShare = amount - amount * ratio;
    return item.paid_by === currentUsername ? total + partnerShare : total - partnerShare;
  }, 0);
}

function formatMonthHeading(monthLabel) {
  if (!monthLabel) {
    return "";
  }

  const [year, month] = monthLabel.split("-");
  const date = new Date(`${year}-${month}-01T00:00:00`);
  return new Intl.DateTimeFormat("it-IT", { month: "long", year: "numeric" }).format(date);
}

function formatCurrency(value) {
  return new Intl.NumberFormat("it-IT", {
    style: "currency",
    currency: "EUR",
  }).format(Number(value || 0));
}

function buildSavingsNote(savings) {
  if (savings > 0) {
    return "Margine positivo rispetto alle uscite.";
  }
  if (savings < 0) {
    return "Le uscite stanno superando le entrate.";
  }
  return "Entrate e uscite sono perfettamente allineate.";
}

function buildCoupleBalanceNote(balance) {
  if (balance > 0) {
    return `Mi devono ${formatCurrency(balance)}`;
  }
  if (balance < 0) {
    return `Devo ${formatCurrency(Math.abs(balance))}`;
  }
  return "Siamo in pari";
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

function createEmptySummary() {
  return {
    periodLabel: "",
    contextNote: "",
    totalExpenses: 0,
    totalIncomes: 0,
    savings: 0,
    expenseCount: 0,
    coupleBalance: 0,
    balanceNote: "",
    coupleBalanceNote: "",
  };
}
