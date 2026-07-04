import { useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { StatusView } from "../components/StatusView";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";

const GREEN = "#63d72a";
const INCOME_GREEN = "#22c55e";
const EXPENSE_ORANGE = "#f59e0b";
const NEGATIVE_RED = "#ef4444";
const CATEGORY_COLORS = {
  casa: "#22c55e",
  spesa: "#facc15",
  trasporti: "#a855f7",
  svago: "#3b82f6",
  altro: "#6b7280",
};
const MONTHS = ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"];

export function ReportPage() {
  const { user } = useAuth();
  const [expenses, setExpenses] = useState([]);
  const [incomes, setIncomes] = useState([]);
  const [period, setPeriod] = useState("Mensile");
  const [selectedYear, setSelectedYear] = useState(String(new Date().getFullYear()));
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let isMounted = true;

    async function loadReportData() {
      setIsLoading(true);
      setError("");

      try {
        const [expensesResponse, incomesResponse] = await Promise.all([
          api.get("/api/expenses?month_label=Tutti"),
          api.get("/api/incomes?month_label=Tutti"),
        ]);

        if (!isMounted) {
          return;
        }

        setExpenses(expensesResponse.items || []);
        setIncomes(incomesResponse.items || []);
      } catch (requestError) {
        if (isMounted) {
          setError(requestError.message || "Impossibile caricare i report.");
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    loadReportData();

    return () => {
      isMounted = false;
    };
  }, []);

  const yearOptions = useMemo(() => buildYearOptions(expenses, incomes), [expenses, incomes]);

  useEffect(() => {
    if (yearOptions.length && !yearOptions.includes(selectedYear)) {
      setSelectedYear(yearOptions[0]);
    }
  }, [selectedYear, yearOptions]);

  const reportData = useMemo(
    () => buildReportData({ expenses, incomes, year: selectedYear, currentUsername: user?.username || "" }),
    [expenses, incomes, selectedYear, user],
  );
  const previousData = useMemo(
    () => buildReportData({ expenses, incomes, year: String(Number(selectedYear) - 1), currentUsername: user?.username || "" }),
    [expenses, incomes, selectedYear, user],
  );
  const insight = useMemo(() => buildReportInsight(reportData.monthly), [reportData]);

  if (isLoading) {
    return <StatusView title="Report" message="Sto preparando gli analytics avanzati." />;
  }

  if (error) {
    return <StatusView title="Errore report" message={error} />;
  }

  const hasData = reportData.monthly.some((item) => item.incomes || item.expenses);

  return (
    <section className="page report-page">
      <header className="report-page__header">
        <div>
          <p className="eyebrow">Analytics</p>
          <h1>Report</h1>
          <p>Analizza entrate, uscite e risparmi</p>
        </div>
        <div className="report-page__filters" aria-label="Filtri report">
          <label>
            <span>Periodo</span>
            <select value={period} onChange={(event) => setPeriod(event.target.value)}>
              <option>Mensile</option>
              <option>Annuale</option>
            </select>
          </label>
          <label>
            <span>Anno</span>
            <select value={selectedYear} onChange={(event) => setSelectedYear(event.target.value)}>
              {yearOptions.map((year) => (
                <option key={year} value={year}>{year}</option>
              ))}
            </select>
          </label>
        </div>
      </header>

      {!hasData ? (
        <section className="report-empty-card">
          <p className="eyebrow">Dati insufficienti</p>
          <h2>Non ci sono ancora dati sufficienti per creare un report.</h2>
        </section>
      ) : (
        <>
          <section className="report-kpi-grid" aria-label="Indicatori report">
            <ReportKpi
              label="Entrate totali"
              value={formatCurrency(reportData.summary.totalIncomes)}
              variation={buildVariation(reportData.summary.totalIncomes, previousData.summary.totalIncomes)}
              tone="positive"
              icon={<TrendUpIcon />}
            />
            <ReportKpi
              label="Uscite totali"
              value={formatCurrency(reportData.summary.totalExpenses)}
              variation={buildVariation(reportData.summary.totalExpenses, previousData.summary.totalExpenses)}
              tone="expense"
              icon={<TrendDownIcon />}
            />
            <ReportKpi
              label="Risparmi totali"
              value={formatCurrency(reportData.summary.totalSavings)}
              variation={buildVariation(reportData.summary.totalSavings, previousData.summary.totalSavings)}
              tone={reportData.summary.totalSavings >= 0 ? "positive" : "negative"}
              icon={<SavingsIcon />}
            />
            <ReportKpi
              label="Media risparmio mensile"
              value={formatCurrency(reportData.summary.averageSavings)}
              variation={buildVariation(reportData.summary.averageSavings, previousData.summary.averageSavings)}
              tone={reportData.summary.averageSavings >= 0 ? "positive" : "negative"}
              icon={<AverageIcon />}
            />
          </section>

          <section className="report-chart-grid">
            <article className="report-chart-card report-chart-card--wide">
              <ReportChartHead title="Andamento entrate vs uscite" />
              <div className="report-chart-shell">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={reportData.monthly} margin={{ top: 12, right: 18, left: 0, bottom: 0 }}>
                    <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.08)" />
                    <XAxis dataKey="shortLabel" axisLine={false} tickLine={false} tick={{ fill: "rgba(255,255,255,0.45)", fontSize: 11 }} />
                    <YAxis axisLine={false} tickLine={false} tick={{ fill: "rgba(255,255,255,0.45)", fontSize: 11 }} width={58} tickFormatter={formatCompactCurrency} />
                    <Tooltip content={<ReportTooltip />} cursor={{ stroke: "rgba(255,255,255,0.12)" }} />
                    <Line type="monotone" dataKey="incomes" name="Entrate" stroke={GREEN} strokeWidth={3} dot={{ r: 3, fill: GREEN, strokeWidth: 0 }} activeDot={{ r: 5, fill: GREEN }} />
                    <Line type="monotone" dataKey="expenses" name="Uscite" stroke={EXPENSE_ORANGE} strokeWidth={3} dot={{ r: 3, fill: EXPENSE_ORANGE, strokeWidth: 0 }} activeDot={{ r: 5, fill: EXPENSE_ORANGE }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <ChartLegend items={[{ label: "Entrate", color: GREEN }, { label: "Uscite", color: EXPENSE_ORANGE }]} />
            </article>

            <article className="report-chart-card">
              <ReportChartHead title="Risparmio mensile" description="Quanto riesci a risparmiare ogni mese" />
              <div className="report-chart-shell">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={reportData.monthly} margin={{ top: 12, right: 10, left: -8, bottom: 0 }}>
                    <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.08)" />
                    <XAxis dataKey="shortLabel" axisLine={false} tickLine={false} tick={{ fill: "rgba(255,255,255,0.45)", fontSize: 11 }} />
                    <YAxis axisLine={false} tickLine={false} tick={{ fill: "rgba(255,255,255,0.45)", fontSize: 11 }} width={54} tickFormatter={formatCompactCurrency} />
                    <Tooltip content={<ReportTooltip valueKey="savings" />} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
                    <Bar dataKey="savings" name="Risparmio" radius={[10, 10, 6, 6]}>
                      {reportData.monthly.map((item) => (
                        <Cell key={item.month} fill={item.savings >= 0 ? GREEN : NEGATIVE_RED} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </article>

            <article className="report-chart-card report-category-card">
              <ReportChartHead title="Spese per categoria" />
              <div className="report-category-layout">
                <div className="report-donut-shell">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Tooltip content={<CategoryTooltip />} />
                      <Pie data={reportData.categories} dataKey="value" nameKey="label" innerRadius={58} outerRadius={88} stroke="none">
                        {reportData.categories.map((item) => (
                          <Cell key={item.label} fill={item.color} />
                        ))}
                      </Pie>
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="report-donut-center">
                    <span>Totale</span>
                    <strong>{formatCompactCurrency(reportData.summary.totalExpenses)}</strong>
                  </div>
                </div>
                <div className="report-category-list">
                  {reportData.categories.map((item) => (
                    <div key={item.label} className="report-category-row">
                      <span>
                        <i style={{ "--category-color": item.color }}><CategoryIcon label={item.label} /></i>
                        {item.label}
                      </span>
                      <strong>{item.percentage}% · {formatCurrency(item.value)}</strong>
                    </div>
                  ))}
                </div>
              </div>
            </article>

            <article className="report-chart-card">
              <ReportChartHead title="Andamento saldo" description="Come cresce il tuo saldo nel tempo" />
              <div className="report-chart-shell">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={reportData.monthly} margin={{ top: 12, right: 18, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="reportCumulativeFill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={GREEN} stopOpacity={0.28} />
                        <stop offset="95%" stopColor={GREEN} stopOpacity={0.02} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.08)" />
                    <XAxis dataKey="shortLabel" axisLine={false} tickLine={false} tick={{ fill: "rgba(255,255,255,0.45)", fontSize: 11 }} />
                    <YAxis axisLine={false} tickLine={false} tick={{ fill: "rgba(255,255,255,0.45)", fontSize: 11 }} width={58} tickFormatter={formatCompactCurrency} />
                    <Tooltip content={<ReportTooltip valueKey="cumulative" />} cursor={{ stroke: "rgba(255,255,255,0.12)" }} />
                    <Area type="monotone" dataKey="cumulative" name="Saldo cumulativo" stroke={GREEN} strokeWidth={3} fill="url(#reportCumulativeFill)" dot={{ r: 3, fill: GREEN, strokeWidth: 0 }} activeDot={{ r: 5, fill: GREEN }} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </article>
          </section>

          <section className={`report-insight-card ${insight.tone}`}>
            <span className="report-insight-card__icon"><InsightIcon /></span>
            <div>
              <p className="eyebrow">Insight</p>
              <strong>{insight.title}</strong>
              <p>{insight.text}</p>
            </div>
          </section>
        </>
      )}
    </section>
  );
}

function ReportKpi({ label, value, variation, tone, icon }) {
  return (
    <article className={`report-kpi-card ${tone}`}>
      <span className="report-kpi-card__icon">{icon}</span>
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
        <em className={variation.tone}>{variation.label}</em>
      </div>
    </article>
  );
}

function ReportChartHead({ title, description }) {
  return (
    <header className="report-chart-head">
      <h2>{title}</h2>
      {description ? <p>{description}</p> : null}
    </header>
  );
}

function ChartLegend({ items }) {
  return (
    <div className="report-chart-legend">
      {items.map((item) => (
        <span key={item.label}><i style={{ background: item.color }} />{item.label}</span>
      ))}
    </div>
  );
}

function ReportTooltip({ active, payload, label, valueKey }) {
  if (!active || !payload?.length) {
    return null;
  }

  const visiblePayload = valueKey ? payload.filter((item) => item.dataKey === valueKey) : payload;

  return (
    <div className="report-tooltip">
      <span>{label}</span>
      {visiblePayload.map((item) => (
        <strong key={item.dataKey} style={{ color: item.color || item.stroke }}>
          {item.name}: {formatCurrency(item.value)}
        </strong>
      ))}
    </div>
  );
}

function CategoryTooltip({ active, payload }) {
  if (!active || !payload?.length) {
    return null;
  }
  const item = payload[0]?.payload;
  return (
    <div className="report-tooltip">
      <span>{item?.label}</span>
      <strong>{formatCurrency(item?.value)}</strong>
      <em>{item?.percentage}% delle uscite</em>
    </div>
  );
}

function buildReportData({ expenses, incomes, year, currentUsername }) {
  const monthlyMap = new Map(
    MONTHS.map((month) => {
      const key = `${year}-${month}`;
      return [key, { month: key, incomes: 0, expenses: 0 }];
    }),
  );

  incomes
    .filter((item) => getMonthLabel(item.income_date || item.month_label).startsWith(year))
    .forEach((item) => {
      const month = getMonthLabel(item.income_date || item.month_label);
      const group = monthlyMap.get(month);
      if (group) {
        group.incomes += Number(item.amount || 0);
      }
    });

  expenses
    .filter((item) => getMonthLabel(item.expense_date || item.month_label).startsWith(year))
    .forEach((item) => {
      const month = getMonthLabel(item.expense_date || item.month_label);
      const group = monthlyMap.get(month);
      if (group) {
        group.expenses += getExpenseShare(item, currentUsername);
      }
    });

  let cumulative = 0;
  const monthly = Array.from(monthlyMap.values()).map((item) => {
    const savings = item.incomes - item.expenses;
    cumulative += savings;
    return {
      ...item,
      label: formatMonthHeading(item.month),
      shortLabel: formatShortMonth(item.month),
      incomes: roundCurrency(item.incomes),
      expenses: roundCurrency(item.expenses),
      savings: roundCurrency(savings),
      cumulative: roundCurrency(cumulative),
    };
  });

  const summary = buildReportSummary(monthly);
  const categories = buildCategoryDistribution(expenses, year, currentUsername);

  return { monthly, summary, categories };
}

function buildReportSummary(monthly) {
  const activeMonths = monthly.filter((item) => item.incomes || item.expenses);
  const totalIncomes = monthly.reduce((sum, item) => sum + item.incomes, 0);
  const totalExpenses = monthly.reduce((sum, item) => sum + item.expenses, 0);
  const totalSavings = totalIncomes - totalExpenses;

  return {
    totalIncomes: roundCurrency(totalIncomes),
    totalExpenses: roundCurrency(totalExpenses),
    totalSavings: roundCurrency(totalSavings),
    averageSavings: activeMonths.length ? roundCurrency(totalSavings / activeMonths.length) : 0,
  };
}

function buildCategoryDistribution(expenses, year, currentUsername) {
  const groups = new Map();
  expenses
    .filter((item) => getMonthLabel(item.expense_date || item.month_label).startsWith(year))
    .forEach((item) => {
      const label = normalizeCategoryLabel(item.category);
      groups.set(label, (groups.get(label) || 0) + getExpenseShare(item, currentUsername));
    });

  const total = Array.from(groups.values()).reduce((sum, value) => sum + value, 0);

  return Array.from(groups.entries())
    .filter(([, value]) => Number(value || 0) > 0)
    .sort((left, right) => right[1] - left[1])
    .map(([label, value]) => ({
      label,
      value: roundCurrency(value),
      percentage: total ? Math.round((value / total) * 100) : 0,
      color: CATEGORY_COLORS[label.toLowerCase()] || CATEGORY_COLORS.altro,
    }));
}

function buildYearOptions(expenses, incomes) {
  const years = new Set([String(new Date().getFullYear())]);
  [...expenses, ...incomes].forEach((item) => {
    const month = getMonthLabel(item.expense_date || item.income_date || item.month_label);
    if (month) {
      years.add(month.slice(0, 4));
    }
  });
  return Array.from(years).sort((left, right) => right.localeCompare(left));
}

function buildVariation(currentValue, previousValue) {
  if (!previousValue) {
    return { label: "Confronto non disponibile", tone: "neutral" };
  }
  const percentage = ((currentValue - previousValue) / Math.abs(previousValue)) * 100;
  return {
    label: `${percentage >= 0 ? "+" : ""}${percentage.toLocaleString("it-IT", { maximumFractionDigits: 1 })}% vs periodo precedente`,
    tone: percentage >= 0 ? "positive" : "negative",
  };
}

function buildReportInsight(monthly) {
  const active = monthly.filter((item) => item.incomes || item.expenses);
  if (active.length < 2) {
    return {
      tone: "neutral",
      title: "Insight in preparazione",
      text: "Aggiungi altri movimenti per confrontare i risparmi tra periodi.",
    };
  }

  const latest = active[active.length - 1];
  const previous = active[active.length - 2];
  if (!previous.savings) {
    return {
      tone: latest.savings >= 0 ? "positive" : "negative",
      title: latest.savings >= 0 ? "Mese in positivo" : "Mese sotto pressione",
      text: `${latest.label}: risparmio netto di ${formatCurrency(latest.savings)}.`,
    };
  }

  const delta = ((latest.savings - previous.savings) / Math.abs(previous.savings)) * 100;
  return {
    tone: delta >= 0 ? "positive" : "negative",
    title: delta >= 0 ? "Risparmio in crescita" : "Risparmio in calo",
    text: `Stai risparmiando ${Math.abs(delta).toLocaleString("it-IT", { maximumFractionDigits: 1 })}% ${delta >= 0 ? "in piu" : "in meno"} rispetto al mese precedente.`,
  };
}

function getExpenseShare(item, currentUsername) {
  const amount = Number(item?.amount || 0);
  if (!item || item.expense_type !== "Condivisa") {
    return amount;
  }
  const payerShareRatio = item.split_type === "custom" ? Number(item.split_ratio ?? 0.5) : 0.5;
  return item.paid_by === currentUsername ? amount * payerShareRatio : amount * (1 - payerShareRatio);
}

function normalizeCategoryLabel(category) {
  const normalized = String(category || "Altro").trim().toLowerCase();
  if (["casa", "spesa", "trasporti", "svago"].includes(normalized)) {
    return normalized.charAt(0).toUpperCase() + normalized.slice(1);
  }
  return "Altro";
}

function getMonthLabel(dateValue) {
  if (!dateValue) {
    return "";
  }
  return String(dateValue).slice(0, 7);
}

function formatMonthHeading(monthLabel) {
  if (!monthLabel) {
    return "";
  }
  const [year, month] = monthLabel.split("-");
  const date = new Date(`${year}-${month}-01T00:00:00`);
  return new Intl.DateTimeFormat("it-IT", { month: "long", year: "numeric" }).format(date);
}

function formatShortMonth(monthLabel) {
  if (!monthLabel) {
    return "";
  }
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

function TrendUpIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4.75 16.5 9.5 11.75l3.25 3.25 6.5-7.5" /><path d="M14.25 7.5h5v5" /></svg>;
}

function TrendDownIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4.75 7.5 9.5 12.25l3.25-3.25 6.5 7.5" /><path d="M14.25 16.5h5v-5" /></svg>;
}

function SavingsIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7.25 9.25h9.5a4 4 0 0 1 0 8h-9.5a4 4 0 0 1 0-8Z" /><path d="M8.75 9.25V7.5a3.25 3.25 0 0 1 6.5 0v1.75" /></svg>;
}

function AverageIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5.5 18.5V5.5" /><path d="M5.5 18.5h13" /><path d="M8.25 15.25 11 12.5l2.25 1.75 4.25-5.5" /></svg>;
}

function InsightIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 18.25h6" /><path d="M9.75 21h4.5" /><path d="M8 14.75c-1.45-1.15-2.25-2.75-2.25-4.65a6.25 6.25 0 0 1 12.5 0c0 1.9-.8 3.5-2.25 4.65-.85.7-1.25 1.45-1.25 2.25h-5.5c0-.8-.4-1.55-1.25-2.25Z" /></svg>;
}

function CategoryIcon({ label }) {
  const normalized = String(label || "").toLowerCase();
  if (normalized === "casa") {
    return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4.75 10.75 12 4.75l7.25 6" /><path d="M6.25 9.75v8.5h4.25v-5h3v5h4.25v-8.5" /></svg>;
  }
  if (normalized === "spesa") {
    return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6.5 7.25h12l-1.2 7.1a2 2 0 0 1-2 1.65H9.15a2 2 0 0 1-1.95-1.55L5.7 5.75H3.9" /><path d="M9.25 19.25h.01M16 19.25h.01" /></svg>;
  }
  if (normalized === "trasporti") {
    return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 16.5V8.75C6 6.95 7.45 5.5 9.25 5.5h5.5C16.55 5.5 18 6.95 18 8.75v7.75" /><path d="M7.25 13.25h9.5M8.25 9h7.5" /><path d="M8.5 18.75h.01M15.5 18.75h.01" /></svg>;
  }
  if (normalized === "svago") {
    return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8.25 14.25h7.5" /><path d="M9.2 10.1h.01M14.8 10.1h.01" /><path d="M7.25 18.25h9.5a3 3 0 0 0 2.95-3.55l-1-5.45A3 3 0 0 0 15.75 6.8h-7.5A3 3 0 0 0 5.3 9.25l-1 5.45a3 3 0 0 0 2.95 3.55Z" /></svg>;
  }
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6.75 7.25h10.5v10.5H6.75Z" /><path d="M9.25 10h5.5M9.25 13.25h5.5" /></svg>;
}
