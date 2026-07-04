import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { StatusView } from "../components/StatusView";
import { FeedbackBanner } from "../components/FeedbackBanner";

export function ProfilePage() {
  const { refreshUser } = useAuth();
  const [form, setForm] = useState({
    full_name: "",
    username: "",
    email: "",
    new_password: "",
  });
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [initialUsername, setInitialUsername] = useState("");

  useEffect(() => {
    let isMounted = true;

    async function loadProfile() {
      try {
        const response = await api.get("/api/profile");
        if (!isMounted) {
          return;
        }
        setForm({
          full_name: response.user.full_name || "",
          username: response.user.username || "",
          email: response.user.email || "",
          new_password: "",
        });
        setInitialUsername(response.user.username || "");
      } catch (requestError) {
        if (isMounted) {
          setError(requestError.message || "Impossibile caricare il profilo.");
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    loadProfile();

    return () => {
      isMounted = false;
    };
  }, []);

  async function handleSubmit(event) {
    event.preventDefault();
    const validationMessage = validateProfileForm(form);
    if (validationMessage) {
      setError(validationMessage);
      setMessage("");
      return;
    }
    setIsSaving(true);
    setError("");
    setMessage("");

    try {
      const response = await api.put("/api/profile", form);
      const refreshedUser = await refreshUser();
      setForm({
        full_name: response.user.full_name || refreshedUser.full_name || "",
        username: response.user.username || refreshedUser.username || "",
        email: response.user.email || refreshedUser.email || "",
        new_password: "",
      });
      setInitialUsername(response.user.username || refreshedUser.username || "");
      setMessage(
        response.user.username !== initialUsername
          ? "Profilo aggiornato. Username e sessione frontend sono stati riallineati."
          : response.message || "Profilo aggiornato.",
      );
    } catch (requestError) {
      setError(requestError.message || "Impossibile aggiornare il profilo.");
    } finally {
      setIsSaving(false);
    }
  }

  if (isLoading) {
    return <StatusView title="Profilo" message="Sto caricando il profilo utente." />;
  }

  if (error && !form.username) {
    return <StatusView title="Errore profilo" message={error} />;
  }

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <p className="eyebrow">Profilo</p>
          <h2>Dati utente</h2>
        </div>
      </div>

      <FeedbackBanner type="error" message={error} />
      <FeedbackBanner type="success" message={message} />

      <form className="panel form-panel" onSubmit={handleSubmit}>
        <label className="field">
          <span>Nome completo</span>
          <input
            type="text"
            value={form.full_name}
            onChange={(event) => setForm((current) => ({ ...current, full_name: event.target.value }))}
          />
        </label>

        <label className="field">
          <span>Username</span>
          <input
            type="text"
            value={form.username}
            onChange={(event) => setForm((current) => ({ ...current, username: event.target.value }))}
          />
        </label>

        <label className="field">
          <span>Email</span>
          <input
            type="email"
            value={form.email}
            onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))}
          />
        </label>

        <label className="field">
          <span>Nuova password</span>
          <input
            type="password"
            value={form.new_password}
            onChange={(event) => setForm((current) => ({ ...current, new_password: event.target.value }))}
          />
        </label>

        <button type="submit" className="primary-button" disabled={isSaving}>
          {isSaving ? "Salvataggio..." : "Salva modifiche"}
        </button>
      </form>
    </section>
  );
}

function validateProfileForm(form) {
  if (!form.full_name.trim()) {
    return "Il nome completo è obbligatorio.";
  }
  if (!form.username.trim()) {
    return "Lo username è obbligatorio.";
  }
  return "";
}
