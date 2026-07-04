import { useEffect, useState } from "react";
import { Dialog } from "../components/Dialog";
import { FeedbackBanner } from "../components/FeedbackBanner";
import { StatusView } from "../components/StatusView";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";

export function AdminUsersPage() {
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState("");
  const [dialogMode, setDialogMode] = useState(null);
  const [selectedUser, setSelectedUser] = useState(null);
  const [form, setForm] = useState(createAdminUserForm());
  const [formError, setFormError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    let isMounted = true;

    async function loadUsers() {
      try {
        const response = await api.get("/api/admin/users");
        if (isMounted) {
          setData(response);
        }
      } catch (requestError) {
        if (isMounted) {
          setError(requestError.message || "Impossibile caricare gli utenti.");
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    setIsLoading(true);
    setError("");
    loadUsers();

    return () => {
      isMounted = false;
    };
  }, []);

  if (!user?.is_admin) {
    return <StatusView title="Area admin" message="Questa sezione e riservata all'account admin." />;
  }

  if (isLoading) {
    return <StatusView title="Area admin" message="Sto caricando gli utenti locali." />;
  }

  if (error) {
    return <StatusView title="Errore admin" message={error} />;
  }

  return (
    <section className="page admin-workspace">
      <section className="expenses-top-shell panel compact-panel">
        <div className="expenses-top-shell__copy">
          <p className="eyebrow">Admin</p>
          <h2 className="expenses-top-shell__title">Utenti locali</h2>
        </div>
      </section>

      <FeedbackBanner type="success" message={feedback} />
      <FeedbackBanner type="error" message={!dialogMode ? formError : ""} />

      <div className="transaction-feed">
        {(data?.items || []).map((item) => (
          <article key={item.id} className="transaction-row-card admin-user-row-card">
            <div className="transaction-date">#{item.id}</div>
            <div className="transaction-main">
              <strong>{item.full_name || item.username}</strong>
              <span>{item.email || "Nessuna email"}</span>
            </div>
            <span className="transaction-chip">{item.username}</span>
            <span className="transaction-chip">{item.account_type === "personal" ? "Personale" : "Coppia"}</span>
            <span className="transaction-chip">{item.couple_id || "Nessuna coppia"}</span>
            <span className="transaction-chip">{item.partner_invite || "Nessun invito"}</span>
            <span className={`transaction-chip${item.is_admin ? " admin-user-chip" : ""}`}>
              {item.is_admin ? "Admin" : "Utente"}
            </span>
            <div className="transaction-actions">
              <button type="button" className="text-button" onClick={() => openEditDialog(item)}>
                Modifica
              </button>
              <button type="button" className="text-button" onClick={() => openDeleteDialog(item)}>
                Elimina
              </button>
            </div>
          </article>
        ))}
      </div>

      {dialogMode === "edit" ? (
        <Dialog
          title="Modifica utente"
          onClose={closeDialog}
          footer={
            <>
              <button type="button" className="secondary-button" onClick={closeDialog}>
                Annulla
              </button>
              <button type="button" className="primary-button" onClick={handleSubmitUser} disabled={isSubmitting}>
                {isSubmitting ? "Salvataggio..." : "Salva modifiche"}
              </button>
            </>
          }
        >
          <div className="stack-list">
            {formError ? <p className="error-message">{formError}</p> : null}

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
              <span>Tipo account</span>
              <select
                value={form.account_type}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    account_type: event.target.value,
                    partner_invite: event.target.value === "personal" ? "" : current.partner_invite,
                  }))
                }
              >
                <option value="couple">Coppia</option>
                <option value="personal">Personale</option>
              </select>
            </label>

            {form.account_type === "couple" ? (
              <label className="field">
                <span>Partner invite</span>
                <input
                  type="text"
                  value={form.partner_invite}
                  onChange={(event) => setForm((current) => ({ ...current, partner_invite: event.target.value }))}
                  placeholder="Username partner"
                />
              </label>
            ) : null}

            <label className="field">
              <span>Nuova password</span>
              <input
                type="password"
                value={form.new_password}
                onChange={(event) => setForm((current) => ({ ...current, new_password: event.target.value }))}
                placeholder="Lascia vuoto per mantenerla"
              />
            </label>

            <label className="field">
              <span>Ruolo admin</span>
              <input
                type="checkbox"
                checked={form.is_admin}
                onChange={(event) => setForm((current) => ({ ...current, is_admin: event.target.checked }))}
              />
            </label>
          </div>
        </Dialog>
      ) : null}

      {dialogMode === "delete" ? (
        <Dialog
          title="Conferma eliminazione"
          onClose={closeDialog}
          footer={
            <>
              <button type="button" className="secondary-button" onClick={closeDialog}>
                Annulla
              </button>
              <button type="button" className="primary-button danger-button" onClick={handleDeleteUser} disabled={isSubmitting}>
                {isSubmitting ? "Eliminazione..." : "Elimina utente"}
              </button>
            </>
          }
        >
          {formError ? <p className="error-message">{formError}</p> : null}
          <p>
            L&apos;utente <strong>{selectedUser?.username || "-"}</strong> verra eliminato insieme ai movimenti associati.
          </p>
        </Dialog>
      ) : null}
    </section>
  );

  function openEditDialog(item) {
    setSelectedUser(item);
    setForm({
      full_name: item.full_name || "",
      username: item.username || "",
      email: item.email || "",
      account_type: item.account_type || "couple",
      partner_invite: item.partner_invite || "",
      is_admin: Boolean(item.is_admin),
      new_password: "",
    });
    setFormError("");
    setDialogMode("edit");
  }

  function openDeleteDialog(item) {
    setSelectedUser(item);
    setFormError("");
    setDialogMode("delete");
  }

  function closeDialog() {
    setDialogMode(null);
    setSelectedUser(null);
    setForm(createAdminUserForm());
    setFormError("");
    setIsSubmitting(false);
  }

  async function handleSubmitUser() {
    if (!selectedUser?.id) {
      return;
    }
    const validationMessage = validateAdminUserForm(form);
    if (validationMessage) {
      setFormError(validationMessage);
      return;
    }
    setIsSubmitting(true);
    setFormError("");
    setFeedback("");
    try {
      const response = await api.put(`/api/admin/users/${selectedUser.id}`, {
        ...form,
        full_name: form.full_name.trim(),
        username: form.username.trim(),
        email: form.email.trim(),
        partner_invite: form.account_type === "couple" ? form.partner_invite.trim() : "",
        new_password: form.new_password,
      });
      setData((current) => ({
        ...(current || { items: [] }),
        items: (current?.items || []).map((item) =>
          item.id === selectedUser.id ? { ...item, ...response.user } : item,
        ),
      }));
      setFeedback(response.message || "Utente aggiornato con successo.");
      closeDialog();
    } catch (requestError) {
      setFormError(requestError.message || "Impossibile aggiornare l'utente.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleDeleteUser() {
    if (!selectedUser?.id) {
      return;
    }
    setIsSubmitting(true);
    setFormError("");
    setFeedback("");
    try {
      const response = await api.delete(`/api/admin/users/${selectedUser.id}`);
      setData((current) => ({
        ...(current || { items: [] }),
        items: (current?.items || []).filter((item) => item.id !== selectedUser.id),
      }));
      setFeedback(response.message || "Utente eliminato con successo.");
      closeDialog();
    } catch (requestError) {
      setFormError(requestError.message || "Impossibile eliminare l'utente.");
    } finally {
      setIsSubmitting(false);
    }
  }
}

function createAdminUserForm() {
  return {
    full_name: "",
    username: "",
    email: "",
    account_type: "couple",
    partner_invite: "",
    is_admin: false,
    new_password: "",
  };
}

function validateAdminUserForm(form) {
  if (!form.full_name.trim()) {
    return "Il nome completo è obbligatorio.";
  }
  if (!form.username.trim()) {
    return "Lo username è obbligatorio.";
  }
  return "";
}
