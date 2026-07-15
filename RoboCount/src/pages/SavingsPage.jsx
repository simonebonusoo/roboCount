import { useMemo } from "react";
import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { StatusView } from "../components/StatusView";
import { useAuth } from "../context/AuthContext";
import { useFinancialHistoryQuery } from "../hooks/useAppData";

const POSITIVE_COLOR = "#63d72a";
const NEGATIVE_COLOR = "#f59e0b";

export function SavingsPage() {
  const { user } = useAuth();
  const {
    data: financialHistory,
    error,
    isLoading,
  } = useFinancialHistoryQuery(user?.account_type || "couple", { enabled: Boolean(user?.username) });
  const expenses = financialHistory?.expenses || [];
  const incomes = financialHistory?.incomes || [];

  const monthlySavings = useMemo(
    () => buildMonthlySavings({ expenses, incomes, currentUsername: user?.username || "" }),
    [expenses, incomes, user],
  );

  const summary = useMemo(() => buildSavingsSummary(monthlySavings), [monthlySavings]);

  if (isLoading && !monthlySavings.length) {
    return <StatusView title="Risparmi" message="Sto calcolando i risparmi mensili." />;
  }

  if (error) {
    return <StatusView title="Errore risparmi" message={error.message || "Impossibile caricare i risparmi."} />;
  }

  return (
    <section className="page savings-page">
      <header className="savings-page__header">
        <div>
          <p className="eyebrow">Risparmi</p>
          <h1>Risparmi</h1>
          <p>Controlla quanto riesci a mettere da parte ogni mese</p>
        </div>
      </header>

      {!monthlySavings.length ? (
        <section className="savings-empty-card">
          <p className="eyebrow">Dati insufficienti</p>
          <h2>Non ci sono ancora dati sufficienti per calcolare i risparmi.</h2>
        </section>
      ) : (
        <>
          <section className="savings-kpi-grid" aria-label="Indicatori risparmi">
            <SavingsKpi label="Risparmio totale" value={formatCurrency(summary.totalSavings)} tone={summary.totalSavings >= 0 ? "positive" : "negative"} />
            <SavingsKpi label="Media mensile" value={formatCurrency(summary.monthlyAverage)} tone={summary.monthlyAverage >= 0 ? "positive" : "negative"} />
            <SavingsKpi label="Mese migliore" value={summary.bestMonth ? `${summary.bestMonth.label} · ${formatCurrency(summary.bestMonth.savings)}` : "Non disponibile"} tone="positive" />
            <SavingsKpi label="Mese peggiore" value={summary.worstMonth ? `${summary.worstMonth.label} · ${formatCurrency(summary.worstMonth.savings)}` : "Non disponibile"} tone={summary.worstMonth?.savings >= 0 ? "positive" : "negative"} />
          </section>

          <section className="savings-content-grid">
            <section className="savings-chart-card">
              <div className="savings-section-head">
                <p className="eyebrow">Andamento</p>
                <h2>Risparmi mensili</h2>
              </div>
              <div className="savings-chart-shell">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={monthlySavings} margin={{ top: 12, right: 16, left: -8, bottom: 0 }}>
                    <XAxis dataKey="shortLabel" axisLine={false} tickLine={false} tick={{ fill: "rgba(255,255,255,0.45)", fontSize: 11 }} />
                    <YAxis axisLine={false} tickLine={false} tick={{ fill: "rgba(255,255,255,0.45)", fontSize: 11 }} width={56} tickFormatter={(value) => formatCompactCurrency(value)} />
                    <Tooltip content={<SavingsTooltip />} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
                    <Bar dataKey="savings" radius={[10, 10, 6, 6]}>
                      {monthlySavings.map((item) => (
                        <Cell key={item.month} fill={item.savings >= 0 ? POSITIVE_COLOR : NEGATIVE_COLOR} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </section>

            <section className="savings-month-card">
              <div className="savings-section-head">
                <p className="eyebrow">Mesi</p>
                <h2>Dettaglio mensile</h2>
              </div>
              <div className="savings-month-list">
                {monthlySavings.map((item) => (
                  <article key={item.month} className={`savings-month-row${item.savings >= 0 ? " positive" : " negative"}`}>
                    <div className="savings-month-row__main">
                      <strong>{item.label}</strong>
                      <span>{item.savingsRate === null ? "Percentuale non disponibile" : `${item.savingsRate}% risparmio`}</span>
                    </div>
                    <div className="savings-month-row__values">
                      <span>Entrate <strong>{formatCurrency(item.incomes)}</strong></span>
                      <span>Uscite <strong>{formatCurrency(item.expenses)}</strong></span>
                      <span>Netto <strong>{formatCurrency(item.savings)}</strong></span>
                    </div>
                  </article>
                ))}
              </div>
            </section>
          </section>
        </>
      )}
    </section>
  );
}

function SavingsKpi({ label, value, tone }) {
  return (
    <article className={`savings-kpi-card ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function SavingsTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;

  return (
    <div className="savings-chart-tooltip">
      <span>{label}</span>
      <strong>{formatCurrency(payload[0].value)}</strong>
    </div>
  );
}

function buildMonthlySavings({ expenses, incomes, currentUsername }) {
  const groups = new Map();

  function ensureMonth(month) {
    if (!month) return null;
    if (!groups.has(month)) {
      groups.set(month, { month, incomes: 0, expenses: 0 });
    }
    return groups.get(month);
  }

  incomes.forEach((item) => {
    const group = ensureMonth(item.month_label || getMonthLabel(item.income_date));
    if (group) {
      group.incomes += Number(item.amount || 0);
    }
  });

  expenses.forEach((item) => {
    const group = ensureMonth(item.month_label || getMonthLabel(item.expense_date));
    if (group) {
      group.expenses += getExpenseShare(item, currentUsername);
    }
  });

  return Array.from(groups.values())
    .sort((left, right) => String(left.month).localeCompare(String(right.month)))
    .map((item) => {
      const savings = item.incomes - item.expenses;
      return {
        ...item,
        label: formatMonthHeading(item.month),
        shortLabel: formatShortMonth(item.month),
        incomes: roundCurrency(item.incomes),
        expenses: roundCurrency(item.expenses),
        savings: roundCurrency(savings),
        savingsRate: item.incomes > 0 ? Math.round((savings / item.incomes) * 100) : null,
      };
    });
}

function buildSavingsSummary(items) {
  if (!items.length) {
    return { totalSavings: 0, monthlyAverage: 0, bestMonth: null, worstMonth: null };
  }

  const totalSavings = items.reduce((sum, item) => sum + item.savings, 0);
  const sorted = [...items].sort((left, right) => right.savings - left.savings);
  return {
    totalSavings: roundCurrency(totalSavings),
    monthlyAverage: roundCurrency(totalSavings / items.length),
    bestMonth: sorted[0],
    worstMonth: sorted[sorted.length - 1],
  };
}

function getExpenseShare(item, currentUsername) {
  const amount = Number(item?.amount || 0);
  if (!item || item.expense_type !== "Condivisa") return amount;

  const ratio = item.split_type === "custom" ? Number(item.split_ratio ?? 0.5) : 0.5;
  return item.paid_by === currentUsername ? amount * ratio : amount * (1 - ratio);
}

function getMonthLabel(dateValue) {
  if (!dateValue) return "";
  return String(dateValue).slice(0, 7);
}

function formatMonthHeading(monthLabel) {
  if (!monthLabel) return "";
  const [year, month] = monthLabel.split("-");
  const date = new Date(`${year}-${month}-01T00:00:00`);
  return new Intl.DateTimeFormat("it-IT", { month: "long", year: "numeric" }).format(date);
}

function formatShortMonth(monthLabel) {
  if (!monthLabel) return "";
  const [year, month] = monthLabel.split("-");
  const date = new Date(`${year}-${month}-01T00:00:00`);
  return new Intl.DateTimeFormat("it-IT", { month: "short" }).format(date);
}

function formatCurrency(value) {
  return new Intl.NumberFormat("it-IT", { style: "currency", currency: "EUR" }).format(Number(value || 0));
}

function formatCompactCurrency(value) {
  return `${Number(value || 0).toLocaleString("it-IT", { maximumFractionDigits: 0 })} €`;
}

function roundCurrency(value) {
  return Math.round(Number(value || 0) * 100) / 100;
}
