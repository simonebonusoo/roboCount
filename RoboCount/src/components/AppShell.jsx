import { useEffect, useMemo, useRef, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { Dialog } from "./Dialog";
import { useAuth } from "../context/AuthContext";
import { ThemeToggle } from "./ThemeToggle";
import { useThemePreference } from "../hooks/useThemePreference";
import { api, notifyAppDataChanged } from "../lib/api";
import { useMetaOptionsQuery } from "../hooks/useAppData";
import { getRobotAvatar } from "../utils/avatars";
import {
  ExpenseForm,
  buildExpensePayload,
  createDefaultExpenseForm,
  getDefaultDateForMonth,
  validateExpenseForm,
} from "../pages/ExpensesPage";
import { IncomeForm, buildIncomePayload, createDefaultIncomeForm, validateIncomeForm } from "../pages/IncomesPage";

const navigation = [
  { to: "/home", label: "Home", icon: HomeIcon },
  { to: "/calendar", label: "Calendario", icon: CalendarIcon },
  { to: "/couple-balance", label: "Saldo di coppia", icon: CoupleIcon },
  { to: "/incomes", label: "Entrate", icon: IncomeIcon },
  { to: "/expenses", label: "Uscite", icon: ExpenseIcon },
  { to: "/report", label: "Report", icon: ReportIcon },
];

function getCategoryName(category) {
  return typeof category === "string" ? category : category?.name || category?.label || category?.categoryName || "";
}

export function AppShell() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const { theme, setTheme } = useThemePreference();
  const [isProfileMenuOpen, setIsProfileMenuOpen] = useState(false);
  const [isExpenseDialogOpen, setIsExpenseDialogOpen] = useState(false);
  const [isIncomeDialogOpen, setIsIncomeDialogOpen] = useState(false);
  const [isAddChoiceOpen, setIsAddChoiceOpen] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [expenseMeta, setExpenseMeta] = useState(null);
  const [expenseForm, setExpenseForm] = useState(createDefaultExpenseForm("", "couple"));
  const [incomeForm, setIncomeForm] = useState(createDefaultIncomeForm());
  const [expenseFormError, setExpenseFormError] = useState("");
  const [incomeFormError, setIncomeFormError] = useState("");
  const [isExpenseSubmitting, setIsExpenseSubmitting] = useState(false);
  const [isIncomeSubmitting, setIsIncomeSubmitting] = useState(false);
  const profileMenuRef = useRef(null);
  const {
    data: metaOptions,
    refetch: refetchMetaOptions,
  } = useMetaOptionsQuery({ enabled: false });
  const isPersonalAccount = user?.account_type === "personal";
  const visibleNavigation = isPersonalAccount
    ? navigation.filter((item) => item.to !== "/couple-balance")
    : navigation;
  const isHomeRoute = location.pathname.startsWith("/home");
  const isIncomeRoute = location.pathname.startsWith("/incomes");
  const isExpenseRoute = location.pathname.startsWith("/expenses");
  const payerOptions = useMemo(() => {
    const usernames = expenseMeta?.usernames?.length
      ? expenseMeta.usernames
      : (expenseMeta?.couple_members || []).map((member) => member?.username);
    const uniqueUsernames = new Map();
    [user?.username, ...usernames].forEach((username) => {
      const cleanUsername = String(username || "").trim();
      if (cleanUsername) {
        uniqueUsernames.set(cleanUsername.toLowerCase(), cleanUsername);
      }
    });
    return Array.from(uniqueUsernames.values());
  }, [expenseMeta, user?.username]);
  const categoryOptions = expenseMeta?.category_items || expenseMeta?.categories || [];
  const splitOptions = expenseMeta?.split_options || ["equal", "custom"];
  const expenseTypeOptions = expenseMeta?.expense_types || ["Personale", "Condivisa"];

  useEffect(() => {
    function handlePointerDown(event) {
      if (!profileMenuRef.current?.contains(event.target)) {
        setIsProfileMenuOpen(false);
      }
    }

    document.addEventListener("mousedown", handlePointerDown);

    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
    };
  }, []);

  useEffect(() => {
    function handleKeyDown(event) {
      if (event.key === "Escape") {
        setIsSidebarOpen(false);
        setIsProfileMenuOpen(false);
        setIsAddChoiceOpen(false);
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  useEffect(() => {
    setIsSidebarOpen(false);
    setIsProfileMenuOpen(false);
    setIsAddChoiceOpen(false);
    setIsExpenseDialogOpen(false);
    setIsIncomeDialogOpen(false);
    setExpenseFormError("");
    setIncomeFormError("");
    setIsExpenseSubmitting(false);
    setIsIncomeSubmitting(false);
  }, [location.pathname, location.search]);

  useEffect(() => {
    if (!user?.username) {
      return;
    }
    setExpenseForm(createDefaultExpenseForm(user.username, user.account_type));
    setIncomeForm(createDefaultIncomeForm());
  }, [user]);

  useEffect(() => {
    if (metaOptions) {
      setExpenseMeta(metaOptions);
    }
  }, [metaOptions]);

  async function handleLogout() {
    try {
      await logout();
    } finally {
      navigate("/login", { replace: true });
    }
  }

  async function handleTopbarCreateAction() {
    if (isHomeRoute) {
      setIsAddChoiceOpen(true);
      return;
    }

    if (isIncomeRoute) {
      navigate("/incomes?action=new");
      return;
    }

    if (isExpenseRoute) {
      navigate("/expenses?action=new");
      return;
    }

    await openExpenseDialog();
  }

  function handleTopbarSearchKeyDown(event) {
    if (event.key !== "Enter") {
      return;
    }

    const searchTerm = event.currentTarget.value.trim().toLowerCase();
    if (!searchTerm) {
      return;
    }

    const searchableRoutes = [
      ...visibleNavigation,
      { to: "/profile", label: "Profilo" },
      ...(user?.is_admin ? [{ to: "/admin/users", label: "Admin" }] : []),
    ];
    const match = searchableRoutes.find((item) => item.label.toLowerCase().includes(searchTerm));
    if (!match) {
      return;
    }

    event.currentTarget.value = "";
    navigate(match.to);
  }

  async function handleAddChoice(type) {
    setIsAddChoiceOpen(false);

    if (type === "income") {
      if (isIncomeRoute) {
        navigate("/incomes?action=new");
        return;
      }

      setIncomeForm(createDefaultIncomeForm());
      setIncomeFormError("");
      setIsIncomeDialogOpen(true);
      return;
    }

    await openExpenseDialog();
  }

  function handleExpenseCategoryCreated(category) {
    const categoryName = getCategoryName(category);
    if (!categoryName) {
      return;
    }
    setExpenseMeta((current) => {
      if (!current) {
        return current;
      }
      const alreadyExists = (current.categories || []).some((item) => getCategoryName(item).toLowerCase() === categoryName.toLowerCase());
      const categoryItemExists = (current.category_items || []).some((item) => getCategoryName(item).toLowerCase() === categoryName.toLowerCase());
      return {
        ...current,
        categories: alreadyExists ? current.categories : [...(current.categories || []), categoryName],
        category_items: categoryItemExists || typeof category === "string"
          ? current.category_items
          : [...(current.category_items || []), category],
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

  async function openExpenseDialog() {
    const activeMonth = new URLSearchParams(location.search).get("month_label") || "";
    setExpenseForm(createDefaultExpenseForm(
      user?.username || "",
      user?.account_type,
      getDefaultDateForMonth(activeMonth),
    ));
    setExpenseFormError("");
    setIsExpenseDialogOpen(true);

    if (expenseMeta) {
      return;
    }

    try {
      const response = await refetchMetaOptions();
      if (response.data) {
        setExpenseMeta(response.data);
      }
      if (response.error) {
        setExpenseFormError(response.error.message || "Impossibile caricare le opzioni per la nuova spesa.");
      }
    } catch (requestError) {
      setExpenseFormError(requestError.message || "Impossibile caricare le opzioni per la nuova spesa.");
    }

  }

  function closeExpenseDialog() {
    setIsExpenseDialogOpen(false);
    setExpenseFormError("");
    setIsExpenseSubmitting(false);
  }

  function closeIncomeDialog() {
    setIsIncomeDialogOpen(false);
    setIncomeFormError("");
    setIsIncomeSubmitting(false);
  }

  async function handleSubmitTopbarExpense() {
    const validationMessage = validateExpenseForm(expenseForm, user?.username || "");
    if (validationMessage) {
      setExpenseFormError(validationMessage);
      return;
    }

    setIsExpenseSubmitting(true);
    setExpenseFormError("");

    try {
      const payload = buildExpensePayload(expenseForm, user?.username || "");
      await api.post("/api/expenses", payload);
      notifyAppDataChanged({ scope: "expenses" });
      closeExpenseDialog();
    } catch (requestError) {
      setExpenseFormError(requestError.message || "Impossibile salvare la spesa.");
    } finally {
      setIsExpenseSubmitting(false);
    }
  }

  async function handleSubmitTopbarIncome() {
    const validationMessage = validateIncomeForm(incomeForm);
    if (validationMessage) {
      setIncomeFormError(validationMessage);
      return;
    }

    setIsIncomeSubmitting(true);
    setIncomeFormError("");

    try {
      const payload = buildIncomePayload(incomeForm);
      await api.post("/api/incomes", payload);
      notifyAppDataChanged({ scope: "incomes" });
      closeIncomeDialog();
    } catch (requestError) {
      setIncomeFormError(requestError.message || "Impossibile salvare l'entrata.");
    } finally {
      setIsIncomeSubmitting(false);
    }
  }

  return (
    <div className="app-shell">
      <div
        className={`sidebar-backdrop${isSidebarOpen ? " active" : ""}`}
        onClick={() => setIsSidebarOpen(false)}
        aria-hidden={!isSidebarOpen}
      />

      <aside className={`sidebar${isSidebarOpen ? " is-open" : ""}`}>
        <div className="sidebar__brand">
          <span className="sidebar__brand-mark">
            <BrandIcon />
          </span>
          <span className="sidebar__brand-text">
            <strong>RoboCount</strong>
            <span>v1.2.0</span>
          </span>
        </div>

        <nav className="sidebar__nav" aria-label="Navigazione principale">
          {visibleNavigation.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) => `sidebar__nav-link${isActive ? " active" : ""}`}
                onClick={() => setIsSidebarOpen(false)}
              >
                <Icon />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
          {user?.is_admin ? (
            <NavLink
              to="/admin/users"
              className={({ isActive }) => `sidebar__nav-link${isActive ? " active" : ""}`}
              onClick={() => setIsSidebarOpen(false)}
            >
              <AdminIcon />
              <span>Admin</span>
            </NavLink>
          ) : null}
        </nav>

        <div className="sidebar__footer">
          <ProfileAvatar user={user} className="sidebar__footer-avatar" />
          <div className="sidebar__footer-copy">
            <strong>{user?.full_name || user?.username || "Utente"}</strong>
            <span>{user?.is_admin ? "Amministratore" : "@".concat(user?.username || "-")}</span>
          </div>
        </div>
      </aside>

      <div className="shell-content">
        <header className="top-shell">
          <div className="top-shell__frame">
            <div className="top-shell__bar">
              <button
                type="button"
                className="top-shell__menu-button"
                onClick={() => setIsSidebarOpen(true)}
                aria-label="Apri menu laterale"
              >
                <MenuIcon />
              </button>

              <button
                type="button"
                className="top-shell__brand-trigger"
                onClick={() => navigate("/home")}
                aria-label="Torna alla home"
              >
                <span className="top-shell__brand-mark">
                  <BrandIcon />
                </span>
                <span className="top-shell__brand-text">
                  <strong>RoboCount</strong>
                </span>
              </button>

              <label className="top-shell__search" aria-label="Cerca o vai a una sezione">
                <SearchIcon />
                <input type="search" placeholder="Cerca o vai a..." onKeyDown={handleTopbarSearchKeyDown} />
                <kbd>Cmd K</kbd>
              </label>

              <div className="top-shell__right">
                <ThemeToggle theme={theme} setTheme={setTheme} />
                <button
                  type="button"
                  className="top-shell__cta-button"
                  onClick={handleTopbarCreateAction}
                  aria-label="Aggiungi movimento"
                >
                  <PlusIcon />
                </button>

                <div className="top-shell__profile-menu" ref={profileMenuRef}>
                  <button
                    type="button"
                    className={`top-shell__avatar-button${isProfileMenuOpen ? " active" : ""}`}
                    onClick={() => setIsProfileMenuOpen((current) => !current)}
                    aria-label="Apri menu profilo"
                    aria-expanded={isProfileMenuOpen}
                  >
                    <ProfileAvatar user={user} className="top-shell__profile-avatar" />
                  </button>

                  {isProfileMenuOpen ? (
                    <div className="top-shell__profile-popover" role="menu" aria-label="Menu profilo">
                      <div className="top-shell__profile-card">
                        <span className="top-shell__profile-name">{user?.full_name || "Utente"}</span>
                        <span className="top-shell__profile-meta">@{user?.username || "-"}</span>
                      </div>
                      <button
                        type="button"
                        className="top-shell__profile-item"
                        onClick={() => {
                          setIsProfileMenuOpen(false);
                          navigate("/profile");
                        }}
                      >
                        Profilo
                      </button>
                      <button
                        type="button"
                        className="top-shell__profile-item"
                        onClick={handleLogout}
                      >
                        Logout
                      </button>
                    </div>
                  ) : null}
                </div>
              </div>
            </div>
          </div>
        </header>

        <main className="main-content shell-main">
          <Outlet />
        </main>
      </div>

      {isExpenseDialogOpen ? (
        <Dialog
          title="Nuova spesa"
          onClose={closeExpenseDialog}
          footer={(
            <>
              <button type="button" className="secondary-button" onClick={closeExpenseDialog}>
                Annulla
              </button>
              <button type="button" className="primary-button" onClick={handleSubmitTopbarExpense} disabled={isExpenseSubmitting}>
                {isExpenseSubmitting ? "Salvataggio..." : "Crea spesa"}
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
            onCategoryCreated={handleExpenseCategoryCreated}
            onCategoryDeleted={handleExpenseCategoryDeleted}
          />
        </Dialog>
      ) : null}

      {isIncomeDialogOpen ? (
        <Dialog
          title="Nuova entrata"
          onClose={closeIncomeDialog}
          footer={(
            <>
              <button type="button" className="secondary-button" onClick={closeIncomeDialog}>
                Annulla
              </button>
              <button type="button" className="primary-button" onClick={handleSubmitTopbarIncome} disabled={isIncomeSubmitting}>
                {isIncomeSubmitting ? "Salvataggio..." : "Crea entrata"}
              </button>
            </>
          )}
        >
          <IncomeForm form={incomeForm} setForm={setIncomeForm} formError={incomeFormError} />
        </Dialog>
      ) : null}

      {isAddChoiceOpen ? (
        <Dialog
          title="Aggiungi movimento"
          onClose={() => setIsAddChoiceOpen(false)}
          footer={(
            <button type="button" className="secondary-button" onClick={() => setIsAddChoiceOpen(false)}>
              Chiudi
            </button>
          )}
        >
          <div className="add-choice-dialog">
            <button type="button" className="add-choice-card" onClick={() => handleAddChoice("income")}>
              <IncomeIcon />
              <div>
                <strong>Entrata</strong>
                <span>Registra un nuovo movimento in ingresso.</span>
              </div>
            </button>
            <button type="button" className="add-choice-card" onClick={() => handleAddChoice("expense")}>
              <ExpenseIcon />
              <div>
                <strong>Uscita</strong>
                <span>Apri il form di spesa gia usato nell'app.</span>
              </div>
            </button>
          </div>
        </Dialog>
      ) : null}
    </div>
  );
}

function MenuIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5.25 7.25h13.5M5.25 12h13.5M5.25 16.75h13.5" />
    </svg>
  );
}

function BrandIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 3.75 14.35 9.65 20.25 12 14.35 14.35 12 20.25 9.65 14.35 3.75 12 9.65 9.65Z" />
    </svg>
  );
}

function HomeIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4.75 10.75 12 4.75l7.25 6" />
      <path d="M6.25 9.75v8.5h4.25v-5h3v5h4.25v-8.5" />
    </svg>
  );
}

function CalendarIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="4.5" y="6.5" width="15" height="13" rx="3" />
      <path d="M8 4.75v3.5M16 4.75v3.5M4.5 10.25h15" />
    </svg>
  );
}

function CoupleIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="8.25" cy="9" r="2.75" />
      <circle cx="15.75" cy="9" r="2.75" />
      <path d="M3.75 18.5c.95-2.3 2.8-3.75 4.5-3.75 1.1 0 2.25.4 3.1 1.2" />
      <path d="M12.65 15.95c.85-.8 2-1.2 3.1-1.2 1.7 0 3.55 1.45 4.5 3.75" />
    </svg>
  );
}

function IncomeIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 18.5V5.5" />
      <path d="M7 10.5 12 5.5l5 5" />
      <path d="M5.5 18.5h13" />
    </svg>
  );
}

function ExpenseIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 5.5v13" />
      <path d="m17 13.5-5 5-5-5" />
      <path d="M5.5 5.5h13" />
    </svg>
  );
}

function ReportIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5.5 18.5V5.5" />
      <path d="M5.5 18.5h13" />
      <path d="M8.25 15.25v-3.5" />
      <path d="M12 15.25V8.75" />
      <path d="M15.75 15.25v-5" />
    </svg>
  );
}

function AdminIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 4.25 18.5 6.5v5.25c0 3.55-2.2 6.2-6.5 8-4.3-1.8-6.5-4.45-6.5-8V6.5Z" />
    </svg>
  );
}

function PlusIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 5.5v13M5.5 12h13" />
    </svg>
  );
}

function SearchIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="10.75" cy="10.75" r="5.75" />
      <path d="m15.25 15.25 4 4" />
    </svg>
  );
}

function ProfileAvatar({ user, className }) {
  const avatar = getRobotAvatar(user?.avatar_id);
  return <span className={className}><img src={avatar.src} alt="" /></span>;
}
