import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, notifyAppDataChanged, subscribeAppDataChanged } from "../lib/api";
import { Dialog } from "../components/Dialog";
import { StatusView } from "../components/StatusView";
import { MonthNavigation } from "../components/MonthNavigation";
import { UltimiMovimentiCard } from "../components/UltimiMovimentiCard";
import { useAuth } from "../context/AuthContext";
import { getRobotAvatar } from "../utils/avatars";
import {
  ExpenseForm,
  buildExpensePayload,
  createDefaultExpenseForm,
  normalizeExpenseForForm,
  validateExpenseForm,
} from "./ExpensesPage";
import {
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

const CHART_COLORS = {
  primary: "var(--chart-primary)",
  primarySoft: "var(--chart-secondary)",
  primaryMuted: "var(--chart-tertiary)",
  primaryPale: "var(--chart-quaternary)",
  accent: "var(--chart-accent)",
  neutral: "var(--chart-neutral)",
  neutralMuted: "var(--chart-axis)",
  neutralSoft: "var(--chart-neutral-soft)",
  cursor: "var(--chart-cursor)",
  barCursor: "var(--chart-bar-cursor)",
  surfaceStroke: "var(--chart-stroke-surface)",
};

export function HomePage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { user, logout } = useAuth();
  const [selectedMonth, setSelectedMonth] = useState(searchParams.get("month_label") || "");
  const [scope, setScope] = useState("Mensile");
  const [dashboardData, setDashboardData] = useState(null);
  const [allExpenses, setAllExpenses] = useState([]);
  const [allIncomes, setAllIncomes] = useState([]);
  const [allSharedExpenses, setAllSharedExpenses] = useState([]);
  const [expenseMeta, setExpenseMeta] = useState(null);
  const [coupleMembers, setCoupleMembers] = useState([]);
  const [coupleMemberProfiles, setCoupleMemberProfiles] = useState([]);
  const [coupleUserCount, setCoupleUserCount] = useState(null);
  const [selectedCoupleMember, setSelectedCoupleMember] = useState("");
  const [selectedCategoryPreview, setSelectedCategoryPreview] = useState(null);
  const [editingExpenseId, setEditingExpenseId] = useState(null);
  const [expenseForm, setExpenseForm] = useState(createDefaultExpenseForm(""));
  const [expenseFormError, setExpenseFormError] = useState("");
  const [isExpenseSubmitting, setIsExpenseSubmitting] = useState(false);
  const [inviteFeedback, setInviteFeedback] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const accountType = user?.account_type || "couple";
  const isPersonalAccount = accountType === "personal";
  const canInvitePartner = accountType === "couple" && Number(coupleUserCount || 0) < 2;
  const payerOptions = useMemo(() => {
    const usernames = expenseMeta?.usernames || [];
    if (!user?.username || usernames.includes(user.username)) {
      return usernames;
    }
    return [user.username, ...usernames];
  }, [expenseMeta, user]);
  const categoryOptions = useMemo(() => expenseMeta?.category_items || expenseMeta?.categories || [], [expenseMeta]);
  const splitOptions = expenseMeta?.split_options || ["equal", "custom"];
  const expenseTypeOptions = expenseMeta?.expense_types || ["Personale", "Condivisa"];

  useEffect(() => {
    if (!user?.username) {
      return;
    }
    setExpenseForm(createDefaultExpenseForm(user.username, user.account_type));
  }, [user]);

  useEffect(() => {
    let isMounted = true;

    async function bootstrap() {
      setIsLoading(true);
      setError("");

      try {
        const [expensesResponse, incomesResponse, sharedResponse, metaResponse] = await Promise.all([
          api.get("/api/expenses?month_label=Tutti"),
          api.get("/api/incomes?month_label=Tutti"),
          isPersonalAccount
            ? Promise.resolve({ items: [] })
            : api.get("/api/couple-balance?month_label=Tutti&status_filter=all"),
          api.get("/api/meta/options"),
        ]);

        if (!isMounted) {
          return;
        }

        setAllExpenses(expensesResponse.items || []);
        setAllIncomes(incomesResponse.items || []);
        setAllSharedExpenses(sharedResponse.items || []);
        setExpenseMeta(metaResponse);
        setCoupleMembers(metaResponse.usernames || []);
        setCoupleMemberProfiles(metaResponse.couple_members || []);
        setCoupleUserCount(metaResponse.couple_member_count ?? (metaResponse.usernames || []).length);

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
  }, [isPersonalAccount, reloadKey]);

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
  }, [selectedMonth, reloadKey]);

  useEffect(() => subscribeAppDataChanged(() => setReloadKey((current) => current + 1)), []);

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

    const totalExpenses = sumExpenseShares(expensePool, user?.username || "");
    const totalIncomes = sumAmounts(incomePool);
    const savings = totalIncomes - totalExpenses;
    const coupleBalance = computeCoupleBalance(sharedPool, user?.username || "");
    const monthComparison = scope === "Mensile"
      ? buildPreviousMonthComparison({
          selectedMonth,
          expenses: allExpenses,
          incomes: allIncomes,
          currentSavings: savings,
          currentUsername: user?.username || "",
        })
      : { label: "Confronto non disponibile", value: "" };

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
      monthComparison,
    };
  }, [allExpenses, allIncomes, allSharedExpenses, scope, selectedMonth, user]);

  const activeAnalyticsExpenses = useMemo(() => {
    const activeYear = selectedMonth ? selectedMonth.split("-")[0] : "";
    return scope === "Annuale"
      ? allExpenses.filter((item) => String(item.month_label || "").startsWith(activeYear))
      : allExpenses.filter((item) => item.month_label === selectedMonth);
  }, [allExpenses, scope, selectedMonth]);

  const chartData = useMemo(() => {
    const activeYear = selectedMonth ? selectedMonth.split("-")[0] : "";
    const activeIncomes = scope === "Annuale"
      ? allIncomes.filter((item) => String(item.month_label || "").startsWith(activeYear))
      : allIncomes.filter((item) => item.month_label === selectedMonth);

    return {
      monthTrend: buildMonthlyTrendChart(activeAnalyticsExpenses, activeIncomes, scope, user?.username || ""),
      expenseTrend: buildExpenseTrendChart(activeAnalyticsExpenses, scope, user?.username || ""),
      categoryDistribution: buildCategoryDistributionChart(activeAnalyticsExpenses, user?.username || ""),
    };
  }, [activeAnalyticsExpenses, allIncomes, scope, selectedMonth, user]);

  const selectedCategoryExpenses = useMemo(() => {
    if (!selectedCategoryPreview?.label) {
      return [];
    }
    const normalizedCategory = normalizeCategoryName(selectedCategoryPreview.label);
    return activeAnalyticsExpenses
      .filter((item) => normalizeCategoryName(item.category || "Altro") === normalizedCategory)
      .map((item) => ({
        ...item,
        userShare: getCurrentUserExpenseShare(item, user?.username || ""),
      }))
      .sort((left, right) => String(right.expense_date).localeCompare(String(left.expense_date)));
  }, [activeAnalyticsExpenses, selectedCategoryPreview, user]);

  const selectedCategoryTotal = useMemo(
    () => selectedCategoryExpenses.reduce((sum, item) => sum + Number(item.userShare || 0), 0),
    [selectedCategoryExpenses],
  );

  const latestMovements = useMemo(() => {
    const selectedExpenses = allExpenses.filter((item) => item.month_label === selectedMonth);
    return [...selectedExpenses]
      .sort((first, second) => {
        const firstDate = new Date(first.expense_date || first.date || first.created_at || 0).getTime();
        const secondDate = new Date(second.expense_date || second.date || second.created_at || 0).getTime();
        if (secondDate !== firstDate) {
          return secondDate - firstDate;
        }
        return Number(second.id || 0) - Number(first.id || 0);
      })
      .slice(0, 4);
  }, [allExpenses, selectedMonth]);

  const partnerUser = useMemo(() => {
    const partnerName = coupleMembers.find((member) => member && member !== user?.username);
    if (!partnerName) {
      return null;
    }
    return coupleMemberProfiles.find((profile) => profile.username === partnerName) || { username: partnerName, avatar_id: "1" };
  }, [coupleMemberProfiles, coupleMembers, user]);
  const balanceView = useMemo(
    () => buildHomeBalanceView(homeSummary.coupleBalance, partnerUser?.username || "Partner"),
    [homeSummary.coupleBalance, partnerUser],
  );
  const monthTrendRows = useMemo(
    () => buildHomeMonthTrendRows({
      selectedMonth,
      expenses: allExpenses,
      incomes: allIncomes,
      currentUsername: user?.username || "",
    }),
    [allExpenses, allIncomes, selectedMonth, user],
  );

  useEffect(() => {
    const requestedMember = searchParams.get("member");
    if (!requestedMember) {
      return;
    }
    if (!coupleMembers.includes(requestedMember)) {
      return;
    }
    setSelectedCoupleMember(requestedMember);
  }, [coupleMembers, searchParams]);

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
      <div className="home-reference-header">
        <div className="home-reference-copy">
          <h1>Bentornato {String(user?.username || "utente").toLowerCase()}</h1>
          <p>Ogni movimento che registri ti avvicina a un mese piu sereno.</p>
        </div>

        <div className="home-saas-month-nav">
          <MonthNavigation
            label={formatMonthHeading(selectedMonth)}
            onPrevious={() => shiftSelectedMonth(-1)}
            onNext={() => shiftSelectedMonth(1)}
          />
        </div>
      </div>

      <div className="home-saas-grid">
        <section className={`home-primary-balance-card ${homeSummary.coupleBalance > 0 ? "is-credit" : homeSummary.coupleBalance < 0 ? "is-debit" : "is-even"}`}>
          <button
            type="button"
            className="home-primary-avatar"
            onClick={() => setSelectedCoupleMember(user?.username || "")}
            aria-label="Apri anteprima profilo"
          >
            <img src={getRobotAvatar(user?.avatar_id || user?.avatarId).src} alt="" />
          </button>
          <div className="home-primary-balance-copy">
            <p>{balanceView.label}</p>
            <strong>{balanceView.amount}</strong>
            <span>{balanceView.description}</span>
            <div className="home-primary-balance-actions">
              <button type="button" className="primary-button" onClick={() => navigate(handleMetricNavigation("balance"))}>
                Vedi saldo di coppia
              </button>
              <button type="button" className="secondary-button" onClick={() => navigate(`${buildExpenseUrl()}&action=new`)}>
                Nuova spesa
              </button>
            </div>
          </div>

          <aside className="home-hero-kpi-panel" aria-label="Indicatori principali">
            {[
              {
                key: "income",
                label: "Entrate",
                value: formatCurrency(homeSummary.totalIncomes),
                row: monthTrendRows.find((item) => item.key === "income"),
                tone: "positive",
                href: buildIncomeUrl(),
              },
              {
                key: "expenses",
                label: "Spese",
                value: formatCurrency(homeSummary.totalExpenses),
                row: monthTrendRows.find((item) => item.key === "expenses"),
                tone: "expense",
                href: handleMetricNavigation("total_month"),
              },
              {
                key: "savings",
                label: "Risparmi",
                value: formatCurrency(homeSummary.savings),
                row: monthTrendRows.find((item) => item.key === "savings"),
                tone: "saving",
                href: "/risparmi",
              },
            ].map((item) => (
              <button
                key={item.key}
                type="button"
                className={`home-hero-kpi-row ${item.tone}`}
                onClick={() => navigate(item.href)}
              >
                <span className="home-hero-kpi-icon"><TrendIcon direction={item.row?.direction} /></span>
                <span className="home-hero-kpi-copy">
                  <small>{item.label}</small>
                  <strong>{item.value}</strong>
                  <em>{item.row?.subtitle || "vs periodo precedente"}</em>
                </span>
                <span className="home-hero-kpi-trend">{item.row?.value || "n.d."}</span>
              </button>
            ))}
          </aside>
        </section>
      </div>

      <div className="home-dashboard-grid home-dashboard-grid--secondary">
        <div className="home-main-column">
          <section className="home-analytics-section panel">
            <section className="home-analytics-categories">
              <h2>DOVE VANNO LE TUE SPESE</h2>
              <div className="home-analytics-category-list">
                {chartData.categoryDistribution.slice(0, 5).map((entry) => (
                  <button
                    key={entry.label}
                    type="button"
                    className="home-analytics-category-row"
                    onClick={() => openCategoryPreview(entry)}
                  >
                    <span className="home-analytics-category-name">
                      <i style={{ "--category-color": entry.color }}>
                        <CategoryIcon label={entry.label} />
                      </i>
                      {entry.label}
                    </span>
                    <strong>{entry.percentage}%</strong>
                  </button>
                ))}
              </div>
            </section>

            <section className="home-analytics-donut">
              <div className="home-analytics-donut__chart">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Tooltip content={<ChartTooltip formatter={formatCurrency} />} />
                    <Pie
                      data={chartData.categoryDistribution}
                      dataKey="value"
                      nameKey="label"
                      innerRadius={54}
                      outerRadius={86}
                      paddingAngle={0}
                      stroke="none"
                      onClick={openCategoryPreview}
                      className="home-analytics-pie"
                    >
                      {chartData.categoryDistribution.map((entry) => (
                        <Cell key={entry.label} fill={entry.color} className="home-analytics-pie-cell" />
                      ))}
                    </Pie>
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </section>

            <section className="home-analytics-line">
              <h2>ANDAMENTO MESE</h2>
              <div className="home-analytics-line__chart">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData.monthTrend} margin={{ top: 12, right: 18, left: 0, bottom: 0 }}>
                    <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.08)" strokeDasharray="0" />
                    <XAxis dataKey="label" axisLine={false} tickLine={false} tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 11 }} />
                    <YAxis axisLine={false} tickLine={false} tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 11 }} width={54} tickCount={4} domain={[0, "dataMax + 100"]} tickFormatter={(value) => `${Number(value).toLocaleString("it-IT")} €`} />
                    <Tooltip content={<ChartTooltip formatter={formatCurrency} />} cursor={{ stroke: "rgba(255,255,255,0.08)", strokeWidth: 1 }} />
                    <Line
                      type="monotone"
                      dataKey="entrate"
                      name="Entrate"
                      stroke="#22c55e"
                      strokeWidth={3}
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      connectNulls
                      dot={{ r: 3, fill: "#22c55e", stroke: "rgba(34,197,94,0.25)", strokeWidth: 3 }}
                      activeDot={{ r: 5, fill: "#22c55e", stroke: "rgba(34,197,94,0.35)", strokeWidth: 4 }}
                    />
                    <Line
                      type="monotone"
                      dataKey="spese"
                      name="Spese"
                      stroke="#f59e0b"
                      strokeWidth={3}
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      connectNulls
                      dot={{ r: 3, fill: "#f59e0b", stroke: "rgba(245,158,11,0.25)", strokeWidth: 3 }}
                      activeDot={{ r: 5, fill: "#f59e0b", stroke: "rgba(245,158,11,0.35)", strokeWidth: 4 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <div className="home-analytics-line__legend" aria-hidden="true">
                <span><i className="income" />Entrate</span>
                <span><i className="expense" />Spese</span>
              </div>
            </section>
          </section>
        </div>

        <div className="home-side-column">
          <UltimiMovimentiCard
            movements={latestMovements}
            currentUsername={user?.username || ""}
            onSelectMovement={openExpenseEditDialog}
            onViewAll={() => navigate(buildExpenseUrl())}
          />
        </div>
      </div>

      {selectedCoupleMember ? (
        <Dialog
          title="Anteprima profilo"
          onClose={closeSelectedMember}
          footer={(
            <button type="button" className="secondary-button" onClick={closeSelectedMember}>
              Chiudi
            </button>
          )}
        >
          <div className="profile-preview-modal">
            <section className="profile-preview-identity">
              <button type="button" className="profile-preview-avatar" onClick={() => navigate("/profile")} aria-label="Modifica avatar">
                <img src={getRobotAvatar((coupleMemberProfiles.find((profile) => profile.username === selectedCoupleMember) || user)?.avatar_id).src} alt="" />
                <span><ProfilePreviewIcon name="camera" /></span>
              </button>
              <div className="profile-preview-copy">
                <h2>{selectedCoupleMember}</h2>
                <span className="profile-preview-badge">{selectedCoupleMember === user?.username ? "Utente" : "Partner"}</span>
                <p>Profilo collegato alla coppia corrente.</p>
              </div>
              <div className="profile-preview-mini-info">
                <ProfilePreviewInfo label="Membro da" value="—" />
                <ProfilePreviewInfo label="Profilo coppia" value={isPersonalAccount ? "Non collegato" : "Collegato"} />
                <ProfilePreviewInfo label="Obiettivi attivi" value="0" />
              </div>
            </section>

            <section className="profile-preview-actions" aria-label="Azioni profilo">
              <ProfilePreviewAction
                icon="user"
                title="Informazioni personali"
                subtitle="Nome, email e preferenze"
                onClick={() => navigate("/profile")}
              />
              <ProfilePreviewAction
                icon="sparkle"
                title="Aspetto e avatar"
                subtitle="Cambia avatar e tema"
                onClick={() => navigate("/profile")}
              />
              <ProfilePreviewAction
                icon="tag"
                title="Categorie personali"
                subtitle="Gestisci le tue categorie predefinite"
                onClick={() => navigate("/profile")}
              />
              <ProfilePreviewAction
                icon="lock"
                title="Privacy e sicurezza"
                subtitle="Password e dati personali"
                onClick={() => navigate("/profile")}
              />
              <ProfilePreviewAction
                danger
                icon="logout"
                title="Esci dal profilo"
                subtitle="Disconnetti questo account"
                onClick={async () => {
                  await logout();
                  navigate("/login", { replace: true });
                }}
              />
            </section>

            <div className="profile-preview-footer">
              <ProfilePreviewIcon name="lock" />
              <span>Le modifiche che fai al tuo profilo sono visibili solo a te e al tuo partner.</span>
            </div>
          </div>
        </Dialog>
      ) : null}

      {selectedCategoryPreview ? (
        <Dialog
          title={`Anteprima ${selectedCategoryPreview.label}`}
          onClose={() => setSelectedCategoryPreview(null)}
          footer={(
            <>
              <button type="button" className="secondary-button" onClick={() => setSelectedCategoryPreview(null)}>
                Chiudi
              </button>
              <button
                type="button"
                className="primary-button"
                onClick={() => openCategoryInExpenses(selectedCategoryPreview.label)}
              >
                Vedi in Uscite
              </button>
            </>
          )}
        >
          <div className="category-preview-card">
            <div className="category-preview-head">
              <span className="category-preview-icon" style={{ "--category-color": selectedCategoryPreview.color }}>
                <CategoryIcon label={selectedCategoryPreview.label} />
              </span>
              <div>
                <p className="eyebrow">Totale categoria</p>
                <h2>{formatCurrency(selectedCategoryTotal)}</h2>
                <span>{selectedCategoryExpenses.length} spese nel periodo</span>
              </div>
            </div>

            <div className="category-preview-list">
              {selectedCategoryExpenses.length ? (
                selectedCategoryExpenses.map((expense) => (
                  <button
                    key={expense.id}
                    type="button"
                    className="category-preview-row"
                    onClick={() => openCategoryInExpenses(selectedCategoryPreview.label)}
                  >
                    <div>
                      <strong>{expense.name || expense.description || "Spesa"}</strong>
                      <span>{formatShortDayLabel(expense.expense_date)} · {expense.paid_by || "-"} · {expense.expense_type || "Spesa"}</span>
                    </div>
                    <strong>{formatCurrency(expense.userShare)}</strong>
                  </button>
                ))
              ) : (
                <p>Nessuna spesa trovata per questa categoria.</p>
              )}
            </div>
          </div>
        </Dialog>
      ) : null}

      {editingExpenseId ? (
        <Dialog
          title="Modifica spesa"
          onClose={closeExpenseEditDialog}
          footer={(
            <>
              <button type="button" className="secondary-button" onClick={closeExpenseEditDialog}>
                Annulla
              </button>
              <button
                type="button"
                className="primary-button"
                onClick={handleSubmitExpenseEdit}
                disabled={isExpenseSubmitting}
              >
                {isExpenseSubmitting ? "Salvataggio..." : "Salva modifiche"}
              </button>
            </>
          )}
        >
          <ExpenseForm
            form={expenseForm}
            setForm={setExpenseForm}
            formError={expenseFormError}
            payerOptions={payerOptions}
            categoryOptions={categoryOptions}
            splitOptions={splitOptions}
            expenseTypeOptions={expenseTypeOptions}
            currentUsername={user?.username || ""}
            monthLabel={selectedMonth}
            onCategoryCreated={handleExpenseCategoryCreated}
            onCategoryDeleted={handleExpenseCategoryDeleted}
          />
        </Dialog>
      ) : null}
    </section>
  );

  function shiftSelectedMonth(delta) {
    const nextMonth = getShiftedMonthLabel(selectedMonth, delta);
    if (!nextMonth) {
      return;
    }
    persistMonth(nextMonth);
  }

  function persistMonth(month) {
    setSelectedMonth(month);
    const next = new URLSearchParams(searchParams);
    next.set("month_label", month);
    setSearchParams(next, { replace: true });
  }

  function handleExpenseCategoryCreated(category) {
    const categoryName = getCategoryName(category);
    setExpenseMeta((current) => {
      const existingNames = (current?.categories || []).map(getCategoryName);
      if (!current || existingNames.some((item) => item.toLowerCase() === categoryName.toLowerCase())) {
        return current;
      }
      return {
        ...current,
        categories: [...(current.categories || []), categoryName],
        category_items: category && typeof category !== "string" ? [...(current.category_items || []), category] : current.category_items,
      };
    });
  }

  function handleExpenseCategoryDeleted(categoryName) {
    setExpenseMeta((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        categories: (current.categories || []).filter((item) => getCategoryName(item).toLowerCase() !== categoryName.toLowerCase()),
        category_items: (current.category_items || []).filter((item) => getCategoryName(item).toLowerCase() !== categoryName.toLowerCase()),
      };
    });
  }

  async function openExpenseEditDialog(movement) {
    if (!movement?.id) {
      return;
    }
    setEditingExpenseId(movement.id);
    setExpenseFormError("");
    setIsExpenseSubmitting(false);
    try {
      const response = await api.get(`/api/expenses/${movement.id}`);
      setExpenseForm(normalizeExpenseForForm(response.item, user?.username || ""));
    } catch (requestError) {
      setEditingExpenseId(null);
      setExpenseFormError("");
      setError(requestError.message || "Impossibile caricare il dettaglio della spesa.");
    }
  }

  function closeExpenseEditDialog() {
    setEditingExpenseId(null);
    setExpenseFormError("");
    setIsExpenseSubmitting(false);
  }

  async function handleSubmitExpenseEdit() {
    const validationMessage = validateExpenseForm(expenseForm, user?.username || "");
    if (validationMessage) {
      setExpenseFormError(validationMessage);
      return;
    }
    setIsExpenseSubmitting(true);
    setExpenseFormError("");
    try {
      const payload = buildExpensePayload(expenseForm, user?.username || "");
      await api.put(`/api/expenses/${editingExpenseId}`, payload);
      notifyAppDataChanged({ scope: "expenses" });
      closeExpenseEditDialog();
    } catch (requestError) {
      setExpenseFormError(requestError.message || "Impossibile salvare la spesa.");
    } finally {
      setIsExpenseSubmitting(false);
    }
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

  function openCategoryInExpenses(categoryLabel) {
    const cleanCategory = String(categoryLabel || "").trim();
    if (!cleanCategory) {
      return;
    }
    setSelectedCategoryPreview(null);
    const params = new URLSearchParams();
    params.set("month_label", selectedMonth);
    params.set("category", cleanCategory);
    params.set("payer", "Tutti");
    params.set("expense_type", "Tutte");
    params.set("search", "");
    params.set("sort", "date_desc");
    navigate(`/expenses?${params.toString()}`);
  }

  function buildIncomeUrl(extraFilters = {}) {
    const params = new URLSearchParams({
      month_label: selectedMonth,
      ...extraFilters,
    });
    return `/incomes?${params.toString()}`;
  }

  function openCategoryPreview(entry) {
    const category = entry?.payload || entry;
    if (!category?.label) {
      return;
    }
    setSelectedCategoryPreview(category);
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

  async function handleInvitePartner() {
    try {
      const response = await api.post("/api/couple-invite", {});
      const inviteUrl = `${window.location.origin}/login?mode=register&type=couple&invite_token=${encodeURIComponent(response.invite_token || "")}`;
      await navigator.clipboard.writeText(inviteUrl);
      setInviteFeedback("Link copiato");
    } catch (error) {
      setInviteFeedback(error.message || "Impossibile generare il link invito");
    }
    window.setTimeout(() => setInviteFeedback(""), 5000);
  }

  function closeSelectedMember() {
    setSelectedCoupleMember("");
    const next = new URLSearchParams(searchParams);
    next.delete("member");
    setSearchParams(next, { replace: true });
  }
}

function ChartTooltip({ active, payload, label, formatter }) {
  if (!active || !payload?.length) {
    return null;
  }

  const visibleItems = payload.filter((item) => item.value !== null && item.value !== undefined);
  if (!visibleItems.length) {
    return null;
  }

  const firstItem = visibleItems[0];
  const tooltipLabel = label || firstItem.name || firstItem.payload?.label;
  return (
    <div className="home-chart-tooltip">
      {tooltipLabel ? <span className="home-chart-tooltip__label">{tooltipLabel}</span> : null}
      {visibleItems.map((item) => (
        <strong key={item.dataKey || item.name} className="home-chart-tooltip__value">
          {item.name ? <span style={{ color: item.color || item.stroke }}>{item.name}</span> : null}
          {formatter(item.value)}
        </strong>
      ))}
    </div>
  );
}

function TrendIcon({ direction }) {
  if (direction === "down") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M4.75 7.5 9.5 12.25l3.25-3.25 6.5 7.5" />
        <path d="M14.25 16.5h5v-5" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4.75 16.5 9.5 11.75l3.25 3.25 6.5-7.5" />
      <path d="M14.25 7.5h5v5" />
    </svg>
  );
}

function buildHomeBalanceView(balance, partnerName) {
  const amount = Math.abs(Number(balance || 0));
  if (balance > 0) {
    return {
      label: "TI DEVONO",
      amount: formatCurrency(amount),
      description: `${partnerName} deve pagarti per pareggiare`,
    };
  }
  if (balance < 0) {
    return {
      label: "DEVI DARE",
      amount: formatCurrency(amount),
      description: `Affrettati a pareggiare con ${partnerName}`,
    };
  }
  return {
    label: "SIETE IN PARI",
    amount: "0,00 €",
    description: "Non ci sono importi da regolare in questo momento",
  };
}

function buildHomeMonthTrendRows({ selectedMonth, expenses, incomes, currentUsername }) {
  const previousMonth = getPreviousMonthLabel(selectedMonth);
  const previousLabel = previousMonth ? formatMonthHeading(previousMonth) : "periodo precedente";
  const previousShortLabel = previousLabel.split(" ")[0] || "prima";
  const currentExpenses = expenses.filter((item) => item.month_label === selectedMonth);
  const previousExpenses = expenses.filter((item) => item.month_label === previousMonth);
  const currentIncomes = incomes.filter((item) => item.month_label === selectedMonth);
  const previousIncomes = incomes.filter((item) => item.month_label === previousMonth);
  const currentIncomeTotal = sumAmounts(currentIncomes);
  const previousIncomeTotal = sumAmounts(previousIncomes);
  const currentExpenseTotal = sumExpenseShares(currentExpenses, currentUsername);
  const previousExpenseTotal = sumExpenseShares(previousExpenses, currentUsername);
  const currentSavings = currentIncomeTotal - currentExpenseTotal;
  const previousSavings = previousIncomeTotal - previousExpenseTotal;

  return [
    {
      key: "income",
      label: "Entrate",
      subtitle: `vs ${previousShortLabel}`,
      value: formatPercentageDelta(currentIncomeTotal, previousIncomeTotal),
      tone: "positive",
      direction: currentIncomeTotal >= previousIncomeTotal ? "up" : "down",
      href: `/incomes?month_label=${encodeURIComponent(selectedMonth)}`,
    },
    {
      key: "expenses",
      label: "Spese",
      subtitle: `vs ${previousShortLabel}`,
      value: formatPercentageDelta(currentExpenseTotal, previousExpenseTotal),
      tone: "expense",
      direction: currentExpenseTotal >= previousExpenseTotal ? "up" : "down",
      href: `/expenses?month_label=${encodeURIComponent(selectedMonth)}&category=Tutte&payer=Tutti&expense_type=Tutte`,
    },
    {
      key: "savings",
      label: "Risparmi",
      subtitle: `vs ${previousShortLabel}`,
      value: formatPercentageDelta(currentSavings, previousSavings),
      tone: "saving",
      direction: currentSavings >= previousSavings ? "up" : "down",
      href: "/risparmi",
    },
  ];
}

function formatPercentageDelta(currentValue, previousValue) {
  if (!previousValue) {
    return "n.d.";
  }
  const percentage = ((currentValue - previousValue) / Math.abs(previousValue)) * 100;
  return `${percentage >= 0 ? "+" : ""}${percentage.toLocaleString("it-IT", { maximumFractionDigits: 0 })}%`;
}

function FinancialCard({ label, value, note, accent, onClick, className = "" }) {
  return (
    <button type="button" className={`financial-card financial-card-${accent} financial-card-button ${className}`.trim()} onClick={onClick}>
      <div className="financial-card-label">{label}</div>
      <div className="financial-card-value">{value}</div>
      <div className="financial-card-note">{note}</div>
    </button>
  );
}

function getMemberSharedTotal(member, expenses) {
  return expenses.reduce((total, expense) => total + getMemberExpenseShare(member, expense), 0);
}

function getMemberExpenseShare(member, expense) {
  if (!member || !expense) {
    return 0;
  }
  if (expense.paid_by === member) {
    return Number(expense.payer_share || 0);
  }
  return Number(expense.partner_share || 0);
}

function normalizeMonthOptions(options, expenses, incomes) {
  const merged = new Set(
    [
      ...options,
      ...expenses.map((item) => item.month_label).filter(Boolean),
      ...incomes.map((item) => item.month_label).filter(Boolean),
    ].filter((item) => item && item !== "Tutti"),
  );

  const normalized = Array.from(merged).sort((left, right) => right.localeCompare(left));
  return normalized.length ? normalized : [getCurrentMonthLabel()];
}

function pickInitialMonth(options) {
  const normalized = Array.from(new Set(options.filter((item) => item && item !== "Tutti"))).sort((left, right) => right.localeCompare(left));
  const currentMonth = getCurrentMonthLabel();
  return normalized.find((item) => item === currentMonth) || normalized[0] || currentMonth;
}

function getCurrentMonthLabel() {
  return new Date().toISOString().slice(0, 7);
}

function sumAmounts(items) {
  return items.reduce((total, item) => total + Number(item.amount || 0), 0);
}

function sumExpenseShares(items, currentUsername) {
  return items.reduce((total, item) => total + getCurrentUserExpenseShare(item, currentUsername), 0);
}

function getCurrentUserExpenseShare(item, currentUsername) {
  const amount = Number(item?.amount || 0);
  if (!item || item.expense_type !== "Condivisa") {
    return amount;
  }

  const payerShareRatio = getPayerShareRatio(item);
  return item.paid_by === currentUsername ? amount * payerShareRatio : amount * (1 - payerShareRatio);
}

function getPayerShareRatio(item) {
  if (item?.split_type === "custom") {
    return Number(item.split_ratio ?? 0.5);
  }
  return 0.5;
}

function computeCoupleBalance(items, currentUsername) {
  if (!currentUsername) {
    return 0;
  }

  return items.reduce((total, item) => {
    if (item?.is_settled) {
      return total;
    }

    const ratio = getPayerShareRatio(item);
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

function normalizeCategoryName(value) {
  return String(value || "").trim().toLowerCase();
}

function getCategoryName(option) {
  return typeof option === "string" ? option : option?.name || option?.label || option?.categoryName || "";
}

function getShiftedMonthLabel(monthLabel, delta) {
  if (!monthLabel) {
    return "";
  }
  const [year, month] = monthLabel.split("-").map(Number);
  if (!year || !month) {
    return "";
  }
  const date = new Date(year, month - 1 + delta, 1);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

function getPreviousMonthLabel(monthLabel) {
  if (!monthLabel) {
    return "";
  }
  const [year, month] = monthLabel.split("-").map(Number);
  const date = new Date(year, month - 2, 1);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

function buildPreviousMonthComparison({ selectedMonth, expenses, incomes, currentSavings, currentUsername }) {
  const previousMonth = getPreviousMonthLabel(selectedMonth);
  if (!previousMonth) {
    return { label: "Confronto non disponibile", value: "", trend: "neutral" };
  }

  const previousExpenses = expenses.filter((item) => item.month_label === previousMonth);
  const previousIncomes = incomes.filter((item) => item.month_label === previousMonth);
  if (!previousExpenses.length && !previousIncomes.length) {
    return { label: `Rispetto a ${formatMonthHeading(previousMonth)}`, value: "Confronto non disponibile", trend: "neutral" };
  }

  const previousSavings = sumAmounts(previousIncomes) - sumExpenseShares(previousExpenses, currentUsername);
  if (previousSavings === 0) {
    return { label: `Rispetto a ${formatMonthHeading(previousMonth)}`, value: "Confronto non disponibile", trend: "neutral" };
  }

  const percentage = ((currentSavings - previousSavings) / Math.abs(previousSavings)) * 100;
  return {
    label: `Rispetto a ${formatMonthHeading(previousMonth)}`,
    value: `${percentage >= 0 ? "+" : ""}${percentage.toLocaleString("it-IT", { maximumFractionDigits: 1 })}%`,
    trend: percentage >= 0 ? "positive" : "negative",
  };
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
    return `Da ricevere: ${formatCurrency(balance)}`;
  }
  if (balance < 0) {
    return `Da pagare: ${formatCurrency(Math.abs(balance))}`;
  }
  return "Niente da regolare";
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
    monthComparison: { label: "Confronto non disponibile", value: "", trend: "neutral" },
  };
}

function buildExpenseTrendChart(expenses, scope, currentUsername) {
  if (!expenses.length) {
    return [{ label: scope === "Annuale" ? "Nessun mese" : "Nessun giorno", value: 0 }];
  }

  const groups = new Map();
  expenses.forEach((item) => {
    const key = scope === "Annuale" ? item.month_label : item.expense_date;
    groups.set(key, (groups.get(key) || 0) + getCurrentUserExpenseShare(item, currentUsername));
  });

  return Array.from(groups.entries())
    .sort(([left], [right]) => String(left).localeCompare(String(right)))
    .map(([key, value]) => ({
      label: scope === "Annuale" ? formatShortMonthLabel(key) : formatShortDayLabel(key),
      value: roundCurrency(value),
    }));
}

function buildMonthlyTrendChart(expenses, incomes, scope, currentUsername) {
  if (!expenses.length && !incomes.length) {
    return [{ label: scope === "Annuale" ? "Nessun mese" : "Nessun giorno", entrate: null, spese: null }];
  }

  const groups = new Map();
  function ensureGroup(key) {
    if (!groups.has(key)) {
      groups.set(key, { entrate: null, spese: null });
    }
    return groups.get(key);
  }

  incomes.forEach((item) => {
    const key = scope === "Annuale" ? item.month_label : item.income_date;
    const group = ensureGroup(key);
    group.entrate = Number(group.entrate || 0) + Number(item.amount || 0);
  });

  expenses.forEach((item) => {
    const key = scope === "Annuale" ? item.month_label : item.expense_date;
    const group = ensureGroup(key);
    group.spese = Number(group.spese || 0) + getCurrentUserExpenseShare(item, currentUsername);
  });

  return Array.from(groups.entries())
    .sort(([left], [right]) => String(left).localeCompare(String(right)))
    .map(([key, value]) => ({
      label: scope === "Annuale" ? formatShortMonthLabel(key) : formatShortDayLabel(key),
      entrate: value.entrate === null ? null : roundCurrency(value.entrate),
      spese: value.spese === null ? null : roundCurrency(value.spese),
    }));
}

function buildCategoryDistributionChart(expenses, currentUsername) {
  const categoryColors = {
    casa: "#22c55e",
    spesa: "#f59e0b",
    ristoranti: "#f59e0b",
    trasporti: "#a855f7",
    abbonamenti: "#3b82f6",
    svago: "#3b82f6",
    regali: "#a855f7",
    "cura persona": "#63d72a",
    altro: "#6b7280",
  };
  const fallbackColors = ["#22c55e", "#f59e0b", "#a855f7", "#3b82f6", "#6b7280", "#63d72a"];
  if (!expenses.length) {
    return [];
  }

  const groups = new Map();
  expenses.forEach((item) => {
    const label = String(item.category || "Altro").trim() || "Altro";
    const normalized = label.toLowerCase();
    const current = groups.get(normalized) || { label, value: 0 };
    current.value += getCurrentUserExpenseShare(item, currentUsername);
    groups.set(normalized, current);
  });

  const total = Array.from(groups.values()).reduce((sum, item) => sum + item.value, 0);

  return Array.from(groups.entries())
    .map(([normalized, entry], index) => ({
      label: entry.label,
      value: entry.value,
      normalized,
      color: categoryColors[normalized] || fallbackColors[index % fallbackColors.length],
    }))
    .filter((entry) => Number(entry.value || 0) > 0)
    .sort((left, right) => right.value - left.value)
    .map((entry) => ({
      label: entry.label,
      value: roundCurrency(entry.value),
      percentage: total ? Math.round((entry.value / total) * 100) : 0,
      color: entry.color,
    }));
}

function CategoryIcon({ label }) {
  const normalized = String(label || "").toLowerCase();
  if (normalized === "casa") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M4.75 10.75 12 4.75l7.25 6" />
        <path d="M6.25 9.75v8.5h4.25v-5h3v5h4.25v-8.5" />
      </svg>
    );
  }
  if (normalized === "spesa") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M6.5 7.25h12l-1.2 7.1a2 2 0 0 1-2 1.65H9.15a2 2 0 0 1-1.95-1.55L5.7 5.75H3.9" />
        <path d="M9.25 19.25h.01M16 19.25h.01" />
      </svg>
    );
  }
  if (normalized === "trasporti") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M6 16.5V8.75C6 6.95 7.45 5.5 9.25 5.5h5.5C16.55 5.5 18 6.95 18 8.75v7.75" />
        <path d="M7.25 13.25h9.5M8.25 9h7.5" />
        <path d="M8.5 18.75h.01M15.5 18.75h.01" />
      </svg>
    );
  }
  if (normalized === "svago") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M8.25 14.25h7.5" />
        <path d="M9.2 10.1h.01M14.8 10.1h.01" />
        <path d="M7.25 18.25h9.5a3 3 0 0 0 2.95-3.55l-1-5.45A3 3 0 0 0 15.75 6.8h-7.5A3 3 0 0 0 5.3 9.25l-1 5.45a3 3 0 0 0 2.95 3.55Z" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M6.75 7.25h10.5v10.5H6.75Z" />
      <path d="M9.25 10h5.5M9.25 13.25h5.5" />
    </svg>
  );
}

function buildCoupleBalanceInsight({ expenses, currentUsername, members }) {
  const partnerName = (members || []).find((member) => member && member !== currentUsername) || "Partner";
  const currentLabel = currentUsername || "Tu";

  if (!expenses.length || !currentUsername) {
    return {
      status: "neutral",
      statusLabel: "Saldo in equilibrio",
      directionText: "Non ci sono spese condivise sufficienti per analizzare il saldo.",
      netAmount: 0,
      currentLabel,
      partnerLabel: partnerName,
      currentPaid: 0,
      partnerPaid: 0,
      currentPercent: 0,
      partnerPercent: 0,
      compensatedAmount: 0,
      compensatedPercent: 0,
      remainingAmount: 0,
      remainingPercent: 0,
      creditorLabel: "Nessuno",
    };
  }

  const currentPaid = roundCurrency(
    expenses
      .filter((item) => item.paid_by === currentUsername)
      .reduce((total, item) => total + Number(item.amount || 0), 0),
  );

  const partnerPaid = roundCurrency(
    expenses
      .filter((item) => item.paid_by && item.paid_by !== currentUsername)
      .reduce((total, item) => total + Number(item.amount || 0), 0),
  );

  const totalPaid = currentPaid + partnerPaid;
  const netBalance = roundCurrency(computeCoupleBalance(expenses, currentUsername));
  const remainingAmount = Math.abs(netBalance);
  const compensatedAmount = Math.max(0, roundCurrency(totalPaid - remainingAmount));

  const currentPercent = totalPaid ? Math.max(8, (currentPaid / totalPaid) * 100) : 0;
  const partnerPercent = totalPaid ? Math.max(8, (partnerPaid / totalPaid) * 100) : 0;
  const compensatedPercent = totalPaid ? (compensatedAmount / totalPaid) * 100 : 0;
  const remainingPercent = totalPaid ? (remainingAmount / totalPaid) * 100 : 0;

  if (netBalance > 0) {
    return {
      status: "positive",
      statusLabel: "Ti devono",
      directionText: `${partnerName} deve versarti ${formatCurrency(netBalance)} per riallineare il saldo.`,
      netAmount: netBalance,
      currentLabel: "Tu",
      partnerLabel: partnerName,
      currentPaid,
      partnerPaid,
      currentPercent,
      partnerPercent,
      compensatedAmount,
      compensatedPercent,
      remainingAmount,
      remainingPercent,
      creditorLabel: "Tu",
    };
  }

  if (netBalance < 0) {
    return {
      status: "negative",
      statusLabel: "Devi pagare",
      directionText: `Devi versare ${formatCurrency(Math.abs(netBalance))} a ${partnerName} per chiudere il delta.`,
      netAmount: Math.abs(netBalance),
      currentLabel: "Tu",
      partnerLabel: partnerName,
      currentPaid,
      partnerPaid,
      currentPercent,
      partnerPercent,
      compensatedAmount,
      compensatedPercent,
      remainingAmount,
      remainingPercent,
      creditorLabel: partnerName,
    };
  }

  return {
    status: "neutral",
    statusLabel: "Saldo equilibrato",
    directionText: "Le spese condivise risultano gia compensate tra voi due.",
    netAmount: 0,
    currentLabel: "Tu",
    partnerLabel: partnerName,
    currentPaid,
    partnerPaid,
    currentPercent,
    partnerPercent,
    compensatedAmount,
    compensatedPercent,
    remainingAmount: 0,
    remainingPercent: 0,
    creditorLabel: "Nessuno",
  };
}

function formatShortDayLabel(value) {
  const date = new Date(`${value}T00:00:00`);
  return new Intl.DateTimeFormat("it-IT", { day: "2-digit", month: "2-digit" }).format(date);
}

function ProfilePreviewInfo({ label, value }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function ProfilePreviewAction({ icon, title, subtitle, onClick, danger = false }) {
  return (
    <button type="button" className={`profile-preview-action${danger ? " is-danger" : ""}`} onClick={onClick}>
      <span className="profile-preview-action__icon"><ProfilePreviewIcon name={icon} /></span>
      <span className="profile-preview-action__copy">
        <strong>{title}</strong>
        <small>{subtitle}</small>
      </span>
      <span className="profile-preview-action__chevron"><ProfilePreviewIcon name="chevron" /></span>
    </button>
  );
}

function ProfilePreviewIcon({ name }) {
  const paths = {
    camera: <path d="M8.4 6.5 9.8 4.75h4.4l1.4 1.75h2.65A2.75 2.75 0 0 1 21 9.25v7.25a2.75 2.75 0 0 1-2.75 2.75H5.75A2.75 2.75 0 0 1 3 16.5V9.25A2.75 2.75 0 0 1 5.75 6.5Z M12 16.25A3.25 3.25 0 1 0 12 9.75a3.25 3.25 0 0 0 0 6.5Z" />,
    user: <path d="M20 21a8 8 0 0 0-16 0M12 13a5 5 0 1 0 0-10 5 5 0 0 0 0 10Z" />,
    sparkle: <path d="m12 3 1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9ZM19 15l.9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9Z" />,
    tag: <path d="M20 13 13 20 4 11V4h7Z M7.5 7.5h.01" />,
    lock: <path d="M6 10h12v10H6ZM8 10V7a4 4 0 0 1 8 0v3" />,
    logout: <path d="M10 17 15 12l-5-5M15 12H3M21 3v18h-6" />,
    chevron: <path d="m9 18 6-6-6-6" />,
  };
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      {paths[name] || paths.chevron}
    </svg>
  );
}

function formatShortMonthLabel(value) {
  const [year, month] = String(value || "").split("-");
  if (!year || !month) {
    return value;
  }
  const date = new Date(`${year}-${month}-01T00:00:00`);
  return new Intl.DateTimeFormat("it-IT", { month: "short" }).format(date);
}

function roundCurrency(value) {
  return Math.round(Number(value || 0) * 100) / 100;
}
