import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, notifyAppDataChanged, subscribeAppDataChanged } from "../lib/api";
import { StatusView } from "../components/StatusView";
import { useAuth } from "../context/AuthContext";
import { MonthNavigation } from "../components/MonthNavigation";
import { getRobotAvatar } from "../utils/avatars";

const STATUS_OPTIONS = [
  { value: "open", label: "Da regolare" },
  { value: "settled", label: "Regolate" },
  { value: "all", label: "Tutte" },
];

export function CoupleBalancePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [memberProfiles, setMemberProfiles] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [updatingExpenseId, setUpdatingExpenseId] = useState(null);
  const [expandedExpenseId, setExpandedExpenseId] = useState(null);
  const [reloadKey, setReloadKey] = useState(0);
  const monthLabel = searchParams.get("month_label") || "";
  const statusFilter = searchParams.get("status_filter") || "open";

  useEffect(() => {
    let isMounted = true;

    async function loadBalance() {
      setIsLoading(true);
      setError("");

      try {
        const [response, metaResponse] = await Promise.all([
          fetchBalance(),
          api.get("/api/meta/options"),
        ]);
        if (isMounted) {
          setData(response);
          setMemberProfiles(metaResponse.couple_members || []);
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
  }, [monthLabel, statusFilter, reloadKey]);

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

  useEffect(() => subscribeAppDataChanged(() => setReloadKey((current) => current + 1)), []);

  const partnerName = useMemo(() => getPartnerName(data?.items || [], user?.username || ""), [data, user]);
  const partnerProfile = useMemo(
    () => memberProfiles.find((profile) => profile.username === partnerName) || { username: partnerName, avatar_id: "1" },
    [memberProfiles, partnerName],
  );
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
    <section className="page couple-balance-workspace">
      <section className="couple-page-header">
        <div className="couple-page-header__main">
          <div className="couple-page-header__copy">
            <h1>Saldo di coppia</h1>
            <p>{formatMonthHeading(monthLabel)} · Spese condivise</p>
          </div>

          {monthLabel ? (
            <div className="couple-page-header__month">
              <MonthNavigation
                label={formatMonthHeading(monthLabel)}
                onPrevious={() => shiftSelectedMonth(-1)}
                onNext={() => shiftSelectedMonth(1)}
              />
            </div>
          ) : null}
        </div>
      </section>

      <section className="couple-balance-hero-system">
        <HeroBalanceCard
          currentUser={user}
          partnerUser={partnerProfile}
          balance={data.summary?.balance || 0}
          statusLabel={getCoupleHeroStatusLabel(data.summary?.balance || 0)}
          description={getCoupleHeroDescription(data.summary?.balance || 0, partnerProfile?.username || partnerName)}
          settleDisabled={Number(data.summary?.open_items || 0) === 0 || Number(data.summary?.balance || 0) === 0}
          stats={[
            {
              icon: "wallet",
              tone: "positive",
              title: "Totale condiviso",
              value: formatCurrency(data.summary?.shared_total || 0),
              description: "Totale delle spese condivise",
              onClick: () => updateParams({ status_filter: "all" }),
            },
            {
              icon: "receipt",
              tone: "warning",
              title: "Da regolare",
              value: formatCurrency(Math.abs(data.summary?.balance || 0)),
              description: "Importo netto ancora da saldare",
              onClick: () => updateParams({ status_filter: "open" }),
            },
            {
              icon: "check",
              tone: "closed",
              title: "Spese chiuse",
              value: String(data.summary?.settled_items || 0),
              description: "Spese gia regolate",
              onClick: () => updateParams({ status_filter: "settled" }),
            },
            {
              icon: "list",
              tone: "saving",
              title: "Spese aperte",
              value: String(data.summary?.open_items || 0),
              description: "Spese ancora da regolare",
              onClick: () => updateParams({ status_filter: "open" }),
            },
          ]}
          onSettle={() => {
            updateParams({ status_filter: "open" });
          }}
        />
      </section>

      <section id="couple-balance-list" className="panel couple-expense-panel">
        <div className="couple-expense-panel__head">
          <div>
            <h2>{getListTitle(statusFilter)}</h2>
            <p>{data.summary?.filtered_items || 0} movimenti visualizzati</p>
          </div>
        </div>

        {data.items?.length ? (
          <div className="couple-expense-list">
            {groupExpensesByDay(data.items).map((group) => (
              <section key={group.dateKey} className="couple-day-group">
                <div className="couple-day-header">
                  <strong>{formatDayGroupLabel(group.dateKey)}</strong>
                  <span className={group.total >= 0 ? "credit" : "debit"}>{formatSignedCurrency(group.total)}</span>
                </div>

                <div className="couple-day-card">
                  {group.items.map((item) => {
                    return (
                      <article key={item.id} className="couple-expense-row">
                        <div className="couple-row-category-icon" style={{ "--category-color": getCategoryColor(item.category) }}>
                          {renderCategoryGlyph(item.category)}
                        </div>

                        <div className="couple-row-main">
                          <strong>{item.name || item.description || "Spesa condivisa"}</strong>
                          <span>{item.category || "Senza categoria"}</span>
                          <span className="couple-row-paid-by">
                            <i style={{ "--payer-color": getPayerColor(item.paid_by, user?.username || "") }} />
                            Pagata da {item.paid_by || "-"}
                          </span>
                        </div>

                        <div className={`couple-row-impact${Number(item.balance_impact || 0) >= 0 ? " credit" : " debit"}`}>
                          {!item.is_settled ? <span>{getDirectionLabel(item)}</span> : null}
                          <strong>{formatCurrency(Math.abs(item.balance_impact || 0))}</strong>
                          <small>{formatShortDayLabel(item.expense_date)}</small>
                        </div>

                        <div className="couple-row-actions">
                          <button
                            type="button"
                            className={`couple-ok-button${item.is_settled ? " is-reopen" : ""}`}
                            disabled={updatingExpenseId === item.id}
                            onClick={() => handleToggleSettled(item)}
                          >
                            {updatingExpenseId === item.id ? "..." : item.is_settled ? "Riapri" : "OK"}
                          </button>
                        </div>
                      </article>
                    );
                  })}
                </div>
              </section>
            ))}
          </div>
        ) : (
          <EmptyBalanceState statusFilter={statusFilter} summary={data.summary} />
        )}
      </section>
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

  async function fetchBalance() {
    const params = new URLSearchParams({
      month_label: monthLabel || "Tutti",
      status_filter: statusFilter,
    });
    return api.get(`/api/couple-balance?${params.toString()}`);
  }

  async function handleToggleSettled(item) {
    setUpdatingExpenseId(item.id);
    setError("");
    try {
      await api.patch(`/api/couple-balance/${item.id}/settled`, {
        is_settled: !item.is_settled,
      });
      notifyAppDataChanged({ scope: "expenses" });
      const response = await fetchBalance();
      setData(response);
    } catch (requestError) {
      setError(requestError.message || "Impossibile aggiornare lo stato della spesa.");
    } finally {
      setUpdatingExpenseId(null);
    }
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

function SummaryCard({ icon, tone = "positive", title, value, description, onClick }) {
  return (
    <button type="button" className={`couple-summary-card ${tone}`} onClick={onClick}>
      <span className="couple-summary-card__icon" aria-hidden="true">{renderKpiIcon(icon)}</span>
      <span className="couple-summary-card__copy">
        <small>{title}</small>
        <strong>{value}</strong>
        <em>{description}</em>
      </span>
    </button>
  );
}

function HeroBalanceCard({ currentUser, partnerUser, balance, statusLabel, description, stats = [], onSettle, settleDisabled }) {
  const amount = Math.abs(Number(balance || 0));
  const currentAvatar = getRobotAvatar(currentUser?.avatar_id || currentUser?.avatarId || "1");
  const partnerAvatar = getRobotAvatar(partnerUser?.avatar_id || partnerUser?.avatarId || "1");
  const tone = Number(balance || 0) > 0 ? "credit" : Number(balance || 0) < 0 ? "debit" : "even";

  return (
    <section className={`couple-premium-hero is-${tone}`}>
      <div className="couple-premium-hero__backdrop" aria-hidden="true" />
      <div className="couple-premium-hero__avatar couple-premium-hero__avatar--left">
        <img src={currentAvatar.src} alt="" />
        <span><strong>Tu</strong>{currentUser?.username || currentUser?.name || "Utente"}</span>
      </div>

      <div className="couple-premium-hero__content">
        <p>{statusLabel}</p>
        <strong>{formatCurrency(amount)}</strong>
        <span>{description}</span>
        <div className="couple-premium-hero__actions">
          <button type="button" className="primary-button" disabled={settleDisabled} onClick={onSettle}>
            Segna come regolato
          </button>
          <a className="secondary-button" href="#couple-balance-list">
            Vedi dettaglio
          </a>
        </div>
      </div>

      <div className="couple-premium-hero__avatar couple-premium-hero__avatar--right">
        <img src={partnerAvatar.src} alt="" />
        <span><strong>Partner</strong>{partnerUser?.username || partnerUser?.name || "Partner"}</span>
      </div>

      <aside className="couple-kpi-grid" aria-label="Statistiche saldo di coppia">
        {stats.map((item) => (
          <SummaryCard
            key={item.title}
            icon={item.icon}
            tone={item.tone}
            title={item.title}
            value={item.value}
            description={item.description}
            onClick={item.onClick}
          />
        ))}
      </aside>
    </section>
  );
}

function EmptyBalanceState({ statusFilter, summary }) {
  const isBalanced = Number(summary?.balance || 0) === 0;
  const title = statusFilter === "open" || isBalanced ? "Tutto regolato" : "Nessun movimento";
  const message = statusFilter === "open"
    ? "Non ci sono spese condivise aperte per questo periodo."
    : "Non ci sono spese condivise con i filtri correnti.";

  return (
    <div className="couple-empty-state">
      <span aria-hidden="true">✓</span>
      <h3>{isBalanced ? "Saldo in equilibrio" : title}</h3>
      <p>{message}</p>
    </div>
  );
}

function formatCurrency(value) {
  return new Intl.NumberFormat("it-IT", {
    style: "currency",
    currency: "EUR",
  }).format(Number(value || 0));
}

function formatSignedCurrency(value) {
  const amount = Number(value || 0);
  if (amount > 0) {
    return `+${formatCurrency(amount)}`;
  }
  if (amount < 0) {
    return `-${formatCurrency(Math.abs(amount))}`;
  }
  return formatCurrency(0);
}

function formatDay(value) {
  const date = new Date(`${value}T00:00:00`);
  return new Intl.DateTimeFormat("it-IT", { day: "2-digit" }).format(date);
}

function formatMonthShort(value) {
  const date = new Date(`${value}T00:00:00`);
  return new Intl.DateTimeFormat("it-IT", { month: "short" }).format(date).replace(".", "").toUpperCase();
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

function formatDayGroupLabel(value) {
  if (!value) {
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

function groupExpensesByDay(items) {
  const groupsByDate = new Map();
  (items || []).forEach((item) => {
    const dateKey = item.expense_date || item.date || "Senza data";
    if (!groupsByDate.has(dateKey)) {
      groupsByDate.set(dateKey, { dateKey, items: [], total: 0 });
    }
    const group = groupsByDate.get(dateKey);
    group.items.push(item);
    group.total += Number(item.balance_impact || 0);
  });

  return Array.from(groupsByDate.values())
    .sort((left, right) => String(right.dateKey).localeCompare(String(left.dateKey)))
    .map((group) => ({
      ...group,
      total: Number(group.total.toFixed(2)),
    }));
}

function buildSplitLabel(item) {
  const payerShare = formatCurrency(item.payer_share || 0);
  const partnerShare = formatCurrency(item.partner_share || 0);
  const splitLabel = item.split_type === "custom" ? "Divisione personalizzata" : "Divisione 50/50";
  return `${splitLabel} · chi paga ${payerShare} · partner ${partnerShare}`;
}

function getDirectionLabel(item) {
  return Number(item.balance_impact || 0) >= 0 ? "Ti spetta" : "Devi";
}

function buildSettlementHelp(item) {
  if (Number(item.balance_impact || 0) >= 0) {
    return item.is_settled
      ? "Questa spesa risulta gia chiusa."
      : "Segnala questa voce come regolata quando hai ricevuto il rimborso.";
  }
  return item.is_settled
    ? "Questa spesa risulta gia chiusa."
    : "Segnala questa voce come regolata quando hai restituito la tua quota.";
}

function formatMonthHeading(monthLabel) {
  if (!monthLabel) {
    return "Tutti i mesi";
  }
  const [year, month] = monthLabel.split("-");
  const date = new Date(`${year}-${month}-01T00:00:00`);
  return new Intl.DateTimeFormat("it-IT", { month: "long", year: "numeric" }).format(date);
}

function getStatusSubtitle(statusFilter) {
  if (statusFilter === "settled") {
    return "Spese condivise regolate";
  }
  if (statusFilter === "all") {
    return "Tutte le spese condivise";
  }
  return "Spese condivise da regolare";
}

function getListTitle(statusFilter) {
  if (statusFilter === "settled") {
    return "Spese regolate";
  }
  if (statusFilter === "all") {
    return "Tutte le spese condivise";
  }
  return "Spese da regolare";
}

function getCoupleHeroStatusLabel(balance) {
  const amount = Number(balance || 0);
  if (amount > 0) {
    return "TI DEVONO";
  }
  if (amount < 0) {
    return "DEVI DARE";
  }
  return "SIETE IN PARI";
}

function getCoupleHeroDescription(balance, partnerName) {
  const amount = Number(balance || 0);
  const counterpart = partnerName || "Partner";

  if (amount > 0) {
    return `${counterpart} deve versarti ${formatCurrency(Math.abs(amount))} per pareggiare il saldo.`;
  }
  if (amount < 0) {
    return `Devi versare ${formatCurrency(Math.abs(amount))} a ${counterpart} per pareggiare il saldo.`;
  }
  return "Non ci sono importi da regolare in questo momento.";
}

function getPartnerName(items, currentUsername) {
  const counterpart = items.find((item) => item.counterpart)?.counterpart;
  if (counterpart) {
    return counterpart;
  }
  const payer = items.find((item) => item.paid_by && item.paid_by !== currentUsername)?.paid_by;
  return payer || "Partner";
}

function renderKpiIcon(icon) {
  return <MiniIcon name={icon} />;
}

function renderCategoryGlyph(category) {
  const normalized = String(category || "").toLowerCase();
  if (normalized.includes("casa")) return <MiniIcon name="home" />;
  if (normalized.includes("spesa") || normalized.includes("ristor")) return <MiniIcon name="cart" />;
  if (normalized.includes("trasport")) return <MiniIcon name="car" />;
  if (normalized.includes("svago")) return <MiniIcon name="sparkle" />;
  return <MiniIcon name="receipt" />;
}

function getCategoryColor(category) {
  const normalized = String(category || "").toLowerCase();
  if (normalized.includes("casa")) return "#63d72a";
  if (normalized.includes("spesa") || normalized.includes("ristor")) return "#f59e0b";
  if (normalized.includes("trasport")) return "#a855f7";
  if (normalized.includes("svago")) return "#3b82f6";
  return "#6b7280";
}

function getPayerColor(payer, currentUsername) {
  return payer === currentUsername ? "#63d72a" : "#a855f7";
}

function MiniIcon({ name }) {
  const paths = {
    wallet: <path d="M4 7.5A2.5 2.5 0 0 1 6.5 5H19v14H6.5A2.5 2.5 0 0 1 4 16.5ZM17 12h3v4h-3a2 2 0 0 1 0-4Z" />,
    receipt: <path d="M6 3h12v18l-2-1.2-2 1.2-2-1.2-2 1.2-2-1.2L6 21ZM9 8h6M9 12h6M9 16h4" />,
    list: <path d="M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01" />,
    check: <path d="M20 6 9 17l-5-5" />,
    home: <path d="m4 11 8-7 8 7v8.5a1.5 1.5 0 0 1-1.5 1.5H15v-6H9v6H5.5A1.5 1.5 0 0 1 4 19.5Z" />,
    cart: <path d="M5 5h1.6l1.2 9.2a2 2 0 0 0 2 1.8h6.9a2 2 0 0 0 1.9-1.4L20 9H7.1M10 20h.01M17 20h.01" />,
    car: <path d="m5 14 1.6-4.2A2.8 2.8 0 0 1 9.2 8h5.6a2.8 2.8 0 0 1 2.6 1.8L19 14M6 18h.01M18 18h.01M4 14h16v4H4Z" />,
    sparkle: <path d="m12 3 1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9Z" />,
  };
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      {paths[name] || paths.receipt}
    </svg>
  );
}
