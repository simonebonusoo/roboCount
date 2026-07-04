import { useEffect, useMemo, useState } from "react";
import { Navigate, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import { StatusView } from "../components/StatusView";
import { ThemeToggle } from "../components/ThemeToggle";
import { useThemePreference } from "../hooks/useThemePreference";
import loginRobot from "../assets/login-robot-optimized.png";
import signupRobot from "../assets/signup-robot-optimized.png";
import { DEFAULT_AVATAR_ID, ROBOT_AVATARS, getRobotAvatar } from "../utils/avatars";

const ONBOARDING_STEPS = [
  { key: "register", label: "Dati personali" },
  { key: "avatar", label: "Avatar" },
  { key: "invite", label: "Invita partner" },
];

const AVATAR_STORAGE_KEY = "monitor-spese:robot-avatar";

export function LoginPage() {
  const { login, register, refreshUser, isAuthenticated, isLoading } = useAuth();
  const { theme, setTheme } = useThemePreference();
  const [step, setStep] = useState("login");
  const [form, setForm] = useState({
    full_name: "",
    username: "",
    email: "",
    password: "",
    account_type: "couple",
    partner_invite: "",
  });
  const [selectedAvatar, setSelectedAvatar] = useState(DEFAULT_AVATAR_ID);
  const [registeredUser, setRegisteredUser] = useState(null);
  const [inviteFeedback, setInviteFeedback] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const isOnboarding = step === "register" || step === "avatar" || step === "invite";
  const inviteUsername = registeredUser?.username || form.username;
  const inviteToken = searchParams.get("invite_token") || searchParams.get("invited_by") || "";
  const inviteUrl = useMemo(() => buildInviteUrl(inviteToken), [inviteToken]);

  useEffect(() => {
    if (searchParams.get("mode") !== "register") {
      return;
    }
    setStep("register");
    setForm((current) => ({
      ...current,
      account_type: searchParams.get("type") === "personal" ? "personal" : "couple",
      partner_invite: searchParams.get("invite_token") || searchParams.get("invited_by") || current.partner_invite,
    }));
  }, [searchParams]);

  if (isLoading && step === "login") {
    return <StatusView title="Caricamento sessione" message="Sto verificando il tuo accesso." />;
  }

  if (isAuthenticated && !isOnboarding) {
    return <Navigate to={location.state?.from || "/home"} replace />;
  }

  async function handleLoginSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");

    try {
      const user = await login({ username: form.username, password: form.password });
      ensureRobotAvatar(user?.username || form.username);
      navigate(location.state?.from || "/home", { replace: true });
    } catch (requestError) {
      setError(requestError.message || "Accesso non riuscito.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRegisterSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");

    try {
      if (!registeredUser) {
        const user = await register({ ...form, avatar_id: selectedAvatar });
        setRegisteredUser(user);
        saveRobotAvatar(user?.username || form.username, selectedAvatar);
      }
      setStep("avatar");
    } catch (requestError) {
      setError(requestError.message || "Registrazione non riuscita.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleAvatarContinue() {
    saveRobotAvatar(inviteUsername, selectedAvatar);
    await api.put("/api/profile/avatar", { avatar_id: selectedAvatar });
    await refreshUser();
    setStep("invite");
  }

  function completeOnboarding() {
    saveRobotAvatar(inviteUsername, selectedAvatar || DEFAULT_AVATAR_ID);
    navigate(location.state?.from || "/home", { replace: true });
  }

  async function getFreshInviteUrl() {
    const response = await api.post("/api/couple-invite", {});
    return buildInviteUrl(response.invite_token);
  }

  async function copyInviteLink() {
    try {
      const freshInviteUrl = await getFreshInviteUrl();
      await navigator.clipboard.writeText(freshInviteUrl);
      setInviteFeedback("Link copiato");
    } catch (copyError) {
      setInviteFeedback(copyError.message || "Impossibile generare il link invito");
    }
    window.setTimeout(() => setInviteFeedback(""), 4500);
  }

  async function openWhatsAppInvite() {
    try {
      const freshInviteUrl = await getFreshInviteUrl();
      const text = encodeURIComponent("Unisciti a me su Monitor Spese: " + freshInviteUrl);
      window.open("https://wa.me/?text=" + text, "_blank", "noopener,noreferrer");
    } catch (inviteError) {
      setInviteFeedback(inviteError.message || "Impossibile generare il link invito");
    }
  }

  async function openEmailInvite() {
    try {
      const freshInviteUrl = await getFreshInviteUrl();
      const subject = encodeURIComponent("Invito a Monitor Spese");
      const body = encodeURIComponent("Ciao, gestiamo insieme le spese su Monitor Spese. Usa questo link: " + freshInviteUrl);
      window.location.href = "mailto:?subject=" + subject + "&body=" + body;
    } catch (inviteError) {
      setInviteFeedback(inviteError.message || "Impossibile generare il link invito");
    }
  }

  return (
    <main className="auth-flow-shell">
      <div className="auth-flow-theme">
        <ThemeToggle theme={theme} setTheme={setTheme} />
      </div>

      {step === "login" ? (
        <LoginStep form={form} setForm={setForm} error={error} submitting={submitting} onSubmit={handleLoginSubmit} onCreateAccount={() => { setError(""); setStep("register"); }} />
      ) : null}

      {step === "register" ? (
        <RegisterStep form={form} setForm={setForm} error={error} submitting={submitting} registeredUser={registeredUser} onSubmit={handleRegisterSubmit} onBack={() => { setError(""); setStep("login"); }} onLogin={() => { setError(""); setStep("login"); }} />
      ) : null}

      {step === "avatar" ? (
        <AvatarStep selectedAvatar={selectedAvatar} setSelectedAvatar={setSelectedAvatar} onBack={() => setStep("register")} onContinue={handleAvatarContinue} />
      ) : null}

      {step === "invite" ? (
        <InvitePartnerStep inviteFeedback={inviteFeedback} onBack={() => setStep("avatar")} onWhatsApp={openWhatsAppInvite} onCopyLink={copyInviteLink} onEmail={openEmailInvite} onSkip={completeOnboarding} />
      ) : null}
    </main>
  );
}

function LoginStep({ form, setForm, error, submitting, onSubmit, onCreateAccount }) {
  return (
    <section className="auth-step-card auth-login-card">
      <BrandMark />
      <div className="auth-robot-stage auth-robot-stage-login"><img src={loginRobot} alt="Robot Monitor Spese" /></div>
      <div className="auth-step-copy centered"><h1>Bentornato!</h1><p>Accedi al tuo account</p></div>
      <form className="auth-step-form" onSubmit={onSubmit}>
        <AuthField label="Email o username" type="text" value={form.username} autoComplete="username" onChange={(value) => setForm((current) => ({ ...current, username: value }))} />
        <AuthField label="Password" type="password" value={form.password} autoComplete="current-password" onChange={(value) => setForm((current) => ({ ...current, password: value }))} />
        {error ? <p className="error-message">{error}</p> : null}
        <button type="submit" className="primary-button auth-primary-action" disabled={submitting}>{submitting ? "Accesso..." : "Accedi"}</button>
      </form>
      <div className="auth-divider"><span>oppure</span></div>
      <button type="button" className="secondary-button auth-secondary-action" onClick={onCreateAccount}>Crea nuovo account</button>
      <p className="auth-legal-copy">Continuando accetti i nostri <strong>Termini di servizio</strong> e <strong>Informativa sulla privacy</strong></p>
    </section>
  );
}

function RegisterStep({ form, setForm, error, submitting, registeredUser, onSubmit, onBack, onLogin }) {
  return (
    <section className="auth-step-card auth-onboarding-card">
      <BackButton onClick={onBack} />
      <div className="auth-step-copy centered"><h1>Crea il tuo account</h1><p>Iniziamo! Inserisci i tuoi dati</p></div>
      <StepIndicator current="register" />
      <div className="auth-register-robot"><img src={signupRobot} alt="Robot signup Monitor Spese" /></div>
      <form className="auth-step-form" onSubmit={onSubmit}>
        <AuthField label="Nome" type="text" value={form.full_name} autoComplete="name" onChange={(value) => setForm((current) => ({ ...current, full_name: value }))} />
        <AuthField label="Email" type="email" value={form.email} autoComplete="email" onChange={(value) => setForm((current) => ({ ...current, email: value }))} />
        <AuthField label="Username" type="text" value={form.username} autoComplete="username" onChange={(value) => setForm((current) => ({ ...current, username: value }))} />
        <AuthField label="Password" type="password" value={form.password} autoComplete="new-password" onChange={(value) => setForm((current) => ({ ...current, password: value }))} />
        <div className="auth-account-choice" aria-label="Tipo account">
          <button type="button" className={"auth-choice-button" + (form.account_type === "personal" ? " active" : "")} onClick={() => setForm((current) => ({ ...current, account_type: "personal", partner_invite: "" }))}>Personale</button>
          <button type="button" className={"auth-choice-button" + (form.account_type === "couple" ? " active" : "")} onClick={() => setForm((current) => ({ ...current, account_type: "couple" }))}>Coppia</button>
        </div>
        {form.account_type === "couple" ? <AuthField label="Invita partner" type="text" value={form.partner_invite} placeholder="Codice o link invito" onChange={(value) => setForm((current) => ({ ...current, partner_invite: value }))} /> : <p className="auth-mode-note">Modalita personale: le funzioni di coppia restano disattivate nella tua area.</p>}
        {error ? <p className="error-message">{error}</p> : null}
        <button type="submit" className="primary-button auth-primary-action" disabled={submitting}>{submitting ? "Creazione..." : registeredUser ? "Continua" : "Continua"}</button>
      </form>
      <p className="auth-bottom-link">Hai gia un account? <button type="button" onClick={onLogin}>Accedi</button></p>
    </section>
  );
}

function AvatarStep({ selectedAvatar, setSelectedAvatar, onBack, onContinue }) {
  return (
    <section className="auth-step-card auth-onboarding-card">
      <BackButton onClick={onBack} />
      <div className="auth-step-copy centered"><h1>Crea il tuo avatar</h1><p>Scegli il robot che ti rappresenta</p></div>
      <StepIndicator current="avatar" />
      <div className="auth-avatar-tabs" aria-hidden="true"><span>Stile</span><span>Colori</span></div>
      <div className="auth-avatar-grid">
        {ROBOT_AVATARS.map((avatar) => (
          <button key={avatar.id} type="button" className={"auth-avatar-option" + (selectedAvatar === avatar.id ? " selected" : "")} onClick={() => setSelectedAvatar(avatar.id)} aria-label={"Scegli avatar " + avatar.label}>
            <RobotAvatarCard avatarId={avatar.id} selected={selectedAvatar === avatar.id} />
          </button>
        ))}
      </div>
      <button type="button" className="primary-button auth-primary-action" onClick={onContinue}>Continua</button>
    </section>
  );
}

function InvitePartnerStep({ inviteFeedback, onBack, onWhatsApp, onCopyLink, onEmail, onSkip }) {
  return (
    <section className="auth-step-card auth-onboarding-card auth-invite-card">
      <BackButton onClick={onBack} />
      <div className="auth-step-copy centered"><h1>Invita il tuo partner</h1><p>Condividi Monitor Spese e gestite insieme le vostre spese</p></div>
      <StepIndicator current="invite" />
      <div className="auth-couple-robot-stage auth-couple-robot-stage-local"><img src={loginRobot} alt="Robot Monitor Spese" /><img src={signupRobot} alt="Robot partner Monitor Spese" /></div>
      <div className="auth-invite-options" aria-label="Invita tramite">
        <InviteOption title="WhatsApp" subtitle="Invia un messaggio" icon="W" onClick={onWhatsApp} />
        <InviteOption title="Link" subtitle="Copia il link di invito" icon="L" onClick={onCopyLink} />
        <InviteOption title="Email" subtitle="Invia una email" icon="@" onClick={onEmail} />
      </div>
      {inviteFeedback ? <p className="auth-invite-feedback">{inviteFeedback}</p> : null}
      <button type="button" className="secondary-button auth-secondary-action" onClick={onSkip}>Salta per ora</button>
      <p className="auth-legal-copy">Potrai invitare il tuo partner in un secondo momento dalle impostazioni.</p>
    </section>
  );
}

function StepIndicator({ current }) {
  const currentIndex = ONBOARDING_STEPS.findIndex((step) => step.key === current);
  return <div className="auth-step-indicator">{ONBOARDING_STEPS.map((step, index) => { const isDone = index < currentIndex; const isCurrent = index === currentIndex; return <div key={step.key} className={"auth-step-indicator__item" + (isDone ? " done" : "") + (isCurrent ? " current" : "")}><span>{isDone ? "✓" : index + 1}</span><strong>{step.label}</strong></div>; })}</div>;
}

function AuthField({ label, value, onChange, type = "text", autoComplete, placeholder = "" }) {
  return <label className="field auth-field"><span>{label}</span><input type={type} value={value} autoComplete={autoComplete} placeholder={placeholder} onChange={(event) => onChange(event.target.value)} /></label>;
}

function BrandMark() {
  return <div className="auth-brand-mark"><span>✦</span><strong>Monitor<br />Spese</strong></div>;
}

function BackButton({ onClick }) {
  return <button type="button" className="auth-back-button" onClick={onClick} aria-label="Torna indietro">←</button>;
}

function InviteOption({ title, subtitle, icon, onClick }) {
  return <button type="button" className="auth-invite-option" onClick={onClick}><span>{icon}</span><div><strong>{title}</strong><small>{subtitle}</small></div><i aria-hidden="true">→</i></button>;
}

function RobotAvatarCard({ avatarId, selected = false }) {
  const avatar = getRobotAvatar(avatarId);
  return <div className={"robot-avatar-card" + (selected ? " selected" : "")}><img src={avatar.src} alt="" />{selected ? <span aria-hidden="true">✓</span> : null}</div>;
}

function buildInviteUrl(inviteToken) {
  const safeToken = encodeURIComponent(inviteToken || "");
  if (typeof window === "undefined") {
    return "/login?mode=register&type=couple&invite_token=" + safeToken;
  }
  return window.location.origin + "/login?mode=register&type=couple&invite_token=" + safeToken;
}

function ensureRobotAvatar(username) {
  if (typeof window === "undefined") {
    return;
  }
  const safeUsername = username || "default";
  const userKey = AVATAR_STORAGE_KEY + ":" + safeUsername;
  const current = window.localStorage.getItem(userKey) || DEFAULT_AVATAR_ID;
  window.localStorage.setItem(userKey, current);
  window.localStorage.setItem(AVATAR_STORAGE_KEY + ":current", current);
}

function saveRobotAvatar(username, avatarId) {
  if (typeof window === "undefined") {
    return;
  }
  const safeAvatar = avatarId || DEFAULT_AVATAR_ID;
  const safeUsername = username || "default";
  window.localStorage.setItem(AVATAR_STORAGE_KEY + ":" + safeUsername, safeAvatar);
  window.localStorage.setItem(AVATAR_STORAGE_KEY + ":current", safeAvatar);
}
