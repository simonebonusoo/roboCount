import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { StatusView } from "../components/StatusView";

export function LoginPage() {
  const { login, isAuthenticated, isLoading } = useAuth();
  const [form, setForm] = useState({ username: "", password: "" });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  if (isLoading) {
    return <StatusView title="Caricamento sessione" message="Sto verificando il tuo accesso." />;
  }

  if (isAuthenticated) {
    return <Navigate to={location.state?.from || "/home"} replace />;
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");

    try {
      await login(form);
      navigate(location.state?.from || "/home", { replace: true });
    } catch (requestError) {
      setError(requestError.message || "Accesso non riuscito.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="status-view">
      <form className="panel auth-panel" onSubmit={handleSubmit}>
        <p className="eyebrow">Accesso</p>
        <h1>Accedi al monitor spese</h1>
        <p className="muted">
          Il frontend React usa la sessione backend esistente via cookie HTTP-only. Nessuna logica
          finanziaria viene spostata nel browser.
        </p>

        <label className="field">
          <span>Username</span>
          <input
            type="text"
            value={form.username}
            onChange={(event) => setForm((current) => ({ ...current, username: event.target.value }))}
            autoComplete="username"
          />
        </label>

        <label className="field">
          <span>Password</span>
          <input
            type="password"
            value={form.password}
            onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))}
            autoComplete="current-password"
          />
        </label>

        {error ? <p className="error-message">{error}</p> : null}

        <button type="submit" className="primary-button" disabled={submitting}>
          {submitting ? "Accesso in corso..." : "Accedi"}
        </button>

        <p className="helper-text">Demo locale: `io` con password vuota, `compagna` con `demo123`.</p>
      </form>
    </div>
  );
}
