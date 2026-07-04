import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const navigation = [
  { to: "/home", label: "Home" },
  { to: "/calendar", label: "Calendario" },
  { to: "/couple-balance", label: "Saldo di coppia" },
  { to: "/incomes", label: "Entrate" },
  { to: "/expenses", label: "Uscite" },
];

export function AppShell() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const isIncomeRoute = location.pathname.startsWith("/incomes");
  const ctaLabel = isIncomeRoute ? "Nuova entrata" : "Nuova spesa";

  async function handleLogout() {
    try {
      await logout();
    } finally {
      navigate("/login", { replace: true });
    }
  }

  return (
    <div className="app-shell">
      <header className="top-shell">
        <div className="top-shell__frame">
          <div className="top-shell__row top-shell__row--meta">
            <div className="top-shell__user">
              <span className="top-shell__user-label">Connesso come:</span>
              <span className="top-shell__user-value">{user?.full_name || "Utente"} ({user?.username || "-"})</span>
            </div>

            <div className="top-shell__actions">
              <button type="button" className="top-shell__action-button" onClick={() => navigate("/profile")}>
                Profilo
              </button>
              <button type="button" className="top-shell__action-button" onClick={handleLogout}>
                Logout
              </button>
            </div>
          </div>

          <div className="top-shell__row top-shell__row--nav">
            <div className="top-shell__nav-left">
              <nav className="top-shell__nav-pill" aria-label="Sezioni principali">
                {navigation.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    className={({ isActive }) => `top-shell__nav-link${isActive ? " active" : ""}`}
                  >
                    {item.label}
                  </NavLink>
                ))}
              </nav>
            </div>

            <div className="top-shell__nav-right">
              <button
                type="button"
                className="top-shell__cta-button"
                onClick={() => navigate(isIncomeRoute ? "/incomes?action=new" : "/expenses?action=new")}
              >
                {ctaLabel}
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="main-content shell-main">
        <Outlet />
      </main>
    </div>
  );
}
