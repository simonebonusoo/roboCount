import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { FeedbackBanner } from "../components/FeedbackBanner";
import { StatusView } from "../components/StatusView";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import { ROBOT_AVATARS, getRobotAvatar } from "../utils/avatars";

export function ProfilePage() {
  const { clearAuthState, logout, refreshUser } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    full_name: "",
    username: "",
    email: "",
    new_password: "",
    avatar_id: "1",
  });
  const [partnerName, setPartnerName] = useState("");
  const [stats, setStats] = useState({ savings: 0, memberSince: "Attivo", monthlyAverage: 0 });
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [initialUsername, setInitialUsername] = useState("");
  const [initialAvatarId, setInitialAvatarId] = useState("1");
  const [defaultCategories, setDefaultCategories] = useState([]);
  const [monthlyCategories, setMonthlyCategories] = useState([]);
  const [selectedCategoryMonth, setSelectedCategoryMonth] = useState(getCurrentMonthLabel());
  const [categoryDraft, setCategoryDraft] = useState({ name: "", color: "#63d72a", icon: "tag", scope: "user_default" });
  const [editingCategoryId, setEditingCategoryId] = useState("");
  const [categoryEditDraft, setCategoryEditDraft] = useState({ name: "", color: "#63d72a", icon: "tag" });
  const [deleteCandidate, setDeleteCandidate] = useState(null);
  const [redistributeTarget, setRedistributeTarget] = useState("");
  const [categoryMessage, setCategoryMessage] = useState("");
  const [categoryPicker, setCategoryPicker] = useState(null);
  const [categoryOverrides, setCategoryOverrides] = useState(loadCategoryOverrides);

  const avatar = getRobotAvatar(form.avatar_id);
  const validationMessage = useMemo(() => validateProfileForm(form), [form]);
  const canSubmit = !validationMessage && !isSaving;

  useEffect(() => {
    let isMounted = true;

    async function loadProfile() {
      setIsLoading(true);
      setError("");

      try {
        const [profileResponse, expensesResponse, incomesResponse, metaResponse, monthCategoriesResponse] = await Promise.all([
          api.get("/api/profile"),
          api.get("/api/expenses?month_label=Tutti"),
          api.get("/api/incomes?month_label=Tutti"),
          api.get("/api/meta/options"),
          api.get(`/api/categories?month_label=${encodeURIComponent(selectedCategoryMonth)}`).catch(() => ({ category_items: [], items: [] })),
        ]);
        const categoriesResponse = await api.get(`/api/profile/categories?month_label=${encodeURIComponent(selectedCategoryMonth)}`).catch(() => ({ defaults: [], monthly: [] }));

        if (!isMounted) return;

        const user = profileResponse.user || {};
        const avatarId = user.avatar_id || "1";
        setForm({
          full_name: user.full_name || "",
          username: user.username || "",
          email: user.email || "",
          new_password: "",
          avatar_id: avatarId,
        });
        setInitialUsername(user.username || "");
        setInitialAvatarId(avatarId);

        const expenses = expensesResponse.items || [];
        const incomes = incomesResponse.items || [];
        const totalExpenses = expenses.reduce((sum, item) => sum + Number(item.user_share ?? item.amount ?? 0), 0);
        const totalIncomes = incomes.reduce((sum, item) => sum + Number(item.amount || 0), 0);
        const monthCount = new Set([
          ...expenses.map((item) => item.month_label).filter(Boolean),
          ...incomes.map((item) => item.month_label).filter(Boolean),
        ]).size || 1;
        setStats({
          savings: totalIncomes - totalExpenses,
          memberSince: "Account attivo",
          monthlyAverage: (totalIncomes - totalExpenses) / monthCount,
        });

        const partner = (metaResponse.couple_members || []).find((item) => item.username && item.username !== user.username);
        setPartnerName(partner?.username || "");
        const profileDefaultItems = mapCategoryList(
          categoriesResponse.userDefaultCategories || categoriesResponse.defaults || [],
          "user_default",
        );
        const defaultCategoriesForView = buildDefaultCategoriesForView(profileDefaultItems, expenses, selectedCategoryMonth);
        setDefaultCategories(applyCategoryOverrides(defaultCategoriesForView, categoryOverrides, selectedCategoryMonth));
        setMonthlyCategories(
          applyCategoryOverrides(
            buildMonthlyCategoriesForView({
              expenses,
              monthLabel: selectedCategoryMonth,
              defaultCategories: defaultCategoriesForView,
              profileDefaultCategories: profileDefaultItems,
              monthlyCategories: categoriesResponse.monthlyCustomCategories || categoriesResponse.monthly || [],
              monthCategoryItems: monthCategoriesResponse.category_items || monthCategoriesResponse.items || [],
            }),
            categoryOverrides,
            selectedCategoryMonth,
          ),
        );
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
  }, [selectedCategoryMonth, categoryOverrides]);

  async function handleSubmit(event) {
    event.preventDefault();
    const currentValidation = validateProfileForm(form);
    if (currentValidation) {
      setError(currentValidation);
      setMessage("");
      return;
    }

    setIsSaving(true);
    setError("");
    setMessage("");

    try {
      let profileResponse = null;
      if (form.avatar_id !== initialAvatarId) {
        await api.put("/api/profile/avatar", { avatar_id: form.avatar_id });
      }

      profileResponse = await api.put("/api/profile", {
        full_name: form.full_name,
        username: form.username,
        email: form.email,
        new_password: form.new_password,
      });

      if (profileResponse.sessions_revoked) {
        clearAuthState();
        navigate("/login", { replace: true });
        return;
      }

      const refreshedUser = await refreshUser();
      const nextAvatarId = refreshedUser.avatar_id || form.avatar_id;
      setForm({
        full_name: profileResponse.user.full_name || refreshedUser.full_name || "",
        username: profileResponse.user.username || refreshedUser.username || "",
        email: profileResponse.user.email || refreshedUser.email || "",
        new_password: "",
        avatar_id: nextAvatarId,
      });
      setInitialUsername(profileResponse.user.username || refreshedUser.username || "");
      setInitialAvatarId(nextAvatarId);
      setMessage(
        profileResponse.user.username !== initialUsername
          ? "Profilo aggiornato. Username e sessione frontend sono stati riallineati."
          : "Profilo aggiornato con successo.",
      );
    } catch (requestError) {
      setError(requestError.message || "Impossibile aggiornare il profilo.");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleLogout() {
    await logout();
    navigate("/login", { replace: true });
  }

  async function handleAddCategory(event) {
    event.preventDefault();
    const cleanName = categoryDraft.name.trim();
    if (!cleanName) {
      setError("Inserisci un nome categoria.");
      return;
    }
    setError("");
    setCategoryMessage("");
    try {
      const isMonthly = categoryDraft.scope === "monthly_custom";
      const endpoint = isMonthly ? "/api/profile/monthly-categories" : "/api/profile/categories";
      const response = await api.post(endpoint, {
        ...categoryDraft,
        name: cleanName,
        month_label: selectedCategoryMonth,
      });
      const savedCategory = normalizeCategory(response.category, isMonthly ? "monthly_custom" : "user_default");
      if (isMonthly) {
        setMonthlyCategories((current) => [...current, savedCategory].filter((item) => item.id));
      } else {
        setDefaultCategories((current) => [...current, savedCategory].filter((item) => item.id));
      }
      setCategoryDraft({ name: "", color: "#63d72a", icon: "tag", scope: categoryDraft.scope });
      setCategoryMessage(response.message || "Categoria aggiunta.");
    } catch (requestError) {
      setError(requestError.message || "Impossibile aggiungere la categoria.");
    }
  }

  async function handleDeleteCategory(category) {
    const item = normalizeCategory(category, category.scope);
    if (item.scope === "user_default") {
      setDefaultCategories((current) => current.filter((categoryItem) => categoryItem.id !== item.id));
      setCategoryMessage("Categoria rimossa dalle predefinite.");
      api.delete(`/api/profile/categories/${encodeURIComponent(item.id)}`).catch(() => null);
      return;
    }
    setError("");
    setCategoryMessage("");
    try {
      const endpoint = item.scope === "monthly_custom"
        ? `/api/profile/monthly-categories/${encodeURIComponent(item.id)}`
        : `/api/profile/categories/${encodeURIComponent(item.id)}`;
      const response = await api.delete(endpoint);
      if (item.scope === "monthly_custom") {
        setMonthlyCategories((current) => current.filter((categoryItem) => categoryItem.id !== item.id));
      } else {
        setDefaultCategories((current) => current.filter((categoryItem) => categoryItem.id !== item.id));
      }
      setCategoryMessage(response.message || "Categoria eliminata.");
    } catch (requestError) {
      setError(requestError.message || "Impossibile eliminare la categoria.");
    }
  }

  async function handleUpdateCategory(category, updates) {
    const item = normalizeCategory(category, category.scope);
    const nextCategory = { ...item, ...updates };
    setError("");
    setCategoryMessage("");
    setCategoryOverrides((current) => {
      const nextOverrides = {
        ...current,
        [getCategoryOverrideKey(item, selectedCategoryMonth)]: {
          ...(current[getCategoryOverrideKey(item, selectedCategoryMonth)] || {}),
          ...updates,
        },
      };
      saveCategoryOverrides(nextOverrides);
      return nextOverrides;
    });
    if (item.scope === "monthly_custom") {
      setMonthlyCategories((current) => current.map((categoryItem) => (categoryItem.id === item.id ? { ...categoryItem, ...updates } : categoryItem)));
    } else {
      setDefaultCategories((current) => current.map((categoryItem) => (categoryItem.id === item.id ? { ...categoryItem, ...updates } : categoryItem)));
    }
    try {
      const endpoint = item.scope === "monthly_custom"
        ? `/api/profile/monthly-categories/${encodeURIComponent(item.id)}`
        : `/api/profile/categories/${encodeURIComponent(item.id)}`;
      const response = await api.put(endpoint, {
        name: item.name,
        color: nextCategory.color,
        icon: nextCategory.icon,
      });
      const savedCategory = {
        ...normalizeCategory(response.category, item.scope),
        expenseCount: item.expenseCount,
      };
      if (item.scope === "monthly_custom") {
        setMonthlyCategories((current) => current.map((categoryItem) => (categoryItem.id === item.id ? savedCategory : categoryItem)));
      } else {
        setDefaultCategories((current) => current.map((categoryItem) => (categoryItem.id === item.id ? savedCategory : categoryItem)));
      }
      setCategoryMessage(response.message || "Categoria aggiornata.");
    } catch (requestError) {
      setCategoryMessage("Modifica applicata.");
    }
    setCategoryPicker(null);
  }

  async function handleResetCategories() {
    setError("");
    setCategoryMessage("");
    try {
      const response = await api.post("/api/profile/categories/reset");
      setDefaultCategories(mapCategoryList(response.userDefaultCategories || response.defaults || response.items, "user_default"));
      setCategoryMessage(response.message || "Categorie ripristinate.");
    } catch (requestError) {
      setError(requestError.message || "Impossibile ripristinare le categorie.");
    }
  }

  async function handleConfirmRedistribution() {
    if (!deleteCandidate) {
      return;
    }
    setError("");
    setCategoryMessage("");
    try {
      const response = await api.post(`/api/profile/categories/${encodeURIComponent(deleteCandidate.id)}/delete`, {
        destination_category: redistributeTarget,
      });
      setDefaultCategories((current) => current.filter((item) => item.id !== deleteCandidate.id));
      setDeleteCandidate(null);
      setRedistributeTarget("");
      setCategoryMessage(response.message || "Categoria eliminata e spese redistribuite.");
    } catch (requestError) {
      setError(requestError.message || "Impossibile eliminare la categoria.");
    }
  }

  function getRedistributionOptions(category) {
    return [...defaultCategories, ...monthlyCategories]
      .map((item) => normalizeCategory(item, item.scope))
      .filter((item) => item.id !== category.id);
  }

  if (isLoading) {
    return <StatusView title="Profilo" message="Sto caricando il profilo utente." />;
  }

  if (error && !form.username) {
    return <StatusView title="Errore profilo" message={error} />;
  }

  return (
    <section className="page profile-page">
      <div className="profile-page__header">
        <div>
          <p className="eyebrow">Profilo utente</p>
          <h1>Impostazioni personali</h1>
        </div>
      </div>

      <FeedbackBanner type="error" message={error} />
      <FeedbackBanner type="success" message={message} />

      <div className="profile-layout">
        <aside className="profile-card profile-card--identity">
          <button
            type="button"
            className="profile-avatar-picker"
            onClick={() => {
              const currentIndex = ROBOT_AVATARS.findIndex((item) => item.id === form.avatar_id);
              const nextAvatar = ROBOT_AVATARS[(currentIndex + 1 + ROBOT_AVATARS.length) % ROBOT_AVATARS.length];
              setFormValue(setForm, "avatar_id", nextAvatar.id);
            }}
            aria-label="Cambia avatar"
          >
            <img src={avatar.src} alt="" />
            <span className="profile-avatar-picker__overlay">
              <CameraIcon />
              Cambia
            </span>
          </button>

          <div className="profile-identity-copy">
            <h2>{form.full_name || form.username || "Utente"}</h2>
            <p>{form.email || "Email non impostata"}</p>
          </div>

          <div className="profile-avatar-options" aria-label="Seleziona avatar">
            {ROBOT_AVATARS.map((item) => (
              <button
                key={item.id}
                type="button"
                className={`profile-avatar-option${form.avatar_id === item.id ? " active" : ""}`}
                onClick={() => setFormValue(setForm, "avatar_id", item.id)}
                aria-label={`Scegli ${item.label}`}
              >
                <img src={item.src} alt="" />
              </button>
            ))}
          </div>

          <div className="profile-stats">
            <ProfileStat label="Risparmi totali" value={formatCurrency(stats.savings)} />
            <ProfileStat label="Membro da" value={stats.memberSince} />
            <ProfileStat label="Media mensile" value={formatCurrency(stats.monthlyAverage)} />
          </div>
        </aside>

        <form className="profile-card profile-form-card" onSubmit={handleSubmit}>
          <div className="profile-form-card__head">
            <div>
              <p className="eyebrow">Modifica profilo</p>
              <h2>Dati account</h2>
            </div>
            {validationMessage ? <span>{validationMessage}</span> : <strong>Pronto</strong>}
          </div>

          <div className="profile-form-grid">
            <ProfileField label="Nome" error={!form.full_name.trim() ? "Richiesto" : ""}>
              <input
                type="text"
                value={form.full_name}
                onChange={(event) => setFormValue(setForm, "full_name", event.target.value)}
                autoComplete="name"
              />
            </ProfileField>

            <ProfileField label="Username" error={!form.username.trim() ? "Richiesto" : ""}>
              <input
                type="text"
                value={form.username}
                onChange={(event) => setFormValue(setForm, "username", event.target.value)}
                autoComplete="username"
              />
            </ProfileField>

            <ProfileField label="Email" error={form.email && !isValidEmail(form.email) ? "Email non valida" : ""}>
              <input
                type="email"
                value={form.email}
                onChange={(event) => setFormValue(setForm, "email", event.target.value)}
                autoComplete="email"
              />
            </ProfileField>

            <ProfileField label="Password">
              <div className="profile-password-field">
                <input
                  type={showPassword ? "text" : "password"}
                  value={form.new_password}
                  onChange={(event) => setFormValue(setForm, "new_password", event.target.value)}
                  placeholder="Nuova password"
                  autoComplete="new-password"
                />
                <button type="button" onClick={() => setShowPassword((current) => !current)}>
                  {showPassword ? "Nascondi" : "Mostra"}
                </button>
              </div>
            </ProfileField>

            <ProfileField label="Partner collegato">
              <input type="text" value={partnerName || "Nessun partner collegato"} readOnly />
            </ProfileField>
          </div>

          <div className="profile-actions">
            <button type="button" className="profile-ghost-button" onClick={handleLogout}>
              Logout
            </button>
            <button type="submit" className="profile-primary-button" disabled={!canSubmit}>
              {isSaving ? "Salvataggio..." : "Salva modifiche"}
            </button>
          </div>
        </form>

        <section className="profile-card profile-categories-card">
          <div className="profile-form-card__head">
            <div>
              <p className="eyebrow">Categorie</p>
              <h2>Gestione categorie</h2>
              <p className="profile-category-subtitle">Gestisci le categorie predefinite del tuo profilo e quelle create per il mese corrente.</p>
            </div>
          </div>

          <div className="profile-category-panels">
            <div className="profile-category-panel">
              <div className="profile-category-panel__head">
                <div>
                  <h3>Categorie predefinite</h3>
                  <p>Queste categorie sono disponibili ogni mese nel tuo profilo.</p>
                </div>
                <button type="button" className="profile-ghost-button profile-category-reset" onClick={handleResetCategories}>
                  Ripristina predefinite
                </button>
              </div>
              <div className="profile-category-list">
                {defaultCategories.length ? (
                  defaultCategories.map((category) => renderCategoryRow(category, "default"))
                ) : (
                  <p className="profile-category-empty">Nessuna categoria predefinita personalizzata.</p>
                )}
              </div>
            </div>

            <div className="profile-category-panel">
              <div className="profile-category-panel__head">
                <div>
                  <h3>Categorie custom mensili</h3>
                  <p>Valgono solo per il mese selezionato e si azzerano nei mesi successivi.</p>
                </div>
                <select
                  className="profile-category-month"
                  value={selectedCategoryMonth}
                  onChange={(event) => setSelectedCategoryMonth(event.target.value)}
                >
                  {buildProfileMonthOptions().map((month) => (
                    <option key={month} value={month}>{formatMonthLabel(month)}</option>
                  ))}
                </select>
              </div>
              <div className="profile-category-list">
                {monthlyCategories.length ? (
                  monthlyCategories.map((category) => renderCategoryRow(category, "monthly"))
                ) : (
                  <p className="profile-category-empty">Nessuna categoria custom per questo mese.</p>
                )}
              </div>
            </div>
          </div>

          <form className="profile-category-create" onSubmit={handleAddCategory}>
            <select
              value={categoryDraft.scope}
              onChange={(event) => setCategoryDraft((current) => ({ ...current, scope: event.target.value }))}
            >
              <option value="user_default">Predefinita</option>
              <option value="monthly_custom">Custom</option>
            </select>
            <input
              type="text"
              value={categoryDraft.name}
              placeholder="Nuova categoria"
              onChange={(event) => setCategoryDraft((current) => ({ ...current, name: event.target.value }))}
            />
            <CategoryIconSelect
              value={categoryDraft.icon}
              onChange={(value) => setCategoryDraft((current) => ({ ...current, icon: value }))}
            />
            <CategoryColorSelect
              value={categoryDraft.color}
              onChange={(value) => setCategoryDraft((current) => ({ ...current, color: value }))}
            />
            <button type="submit" className="profile-primary-button">
              {categoryDraft.scope === "monthly_custom" ? "Aggiungi custom" : "Aggiungi predefinita"}
            </button>
          </form>
          {categoryMessage ? <p className="profile-category-message">{categoryMessage}</p> : null}
        </section>
      </div>
      {categoryPicker ? (
        <button
          type="button"
          className="profile-category-picker-backdrop"
          aria-label="Chiudi selezione categoria"
          onClick={() => setCategoryPicker(null)}
        />
      ) : null}
      {deleteCandidate ? (
        <div className="profile-category-modal" role="dialog" aria-modal="true" aria-label="Eliminare categoria?">
          <div className="profile-category-modal__card">
            <p className="eyebrow">Eliminare categoria?</p>
            <h2>Questa categoria contiene spese associate.</h2>
            <p>Le spese verranno redistribuite automaticamente in altre categorie.</p>
            <strong>{Number(deleteCandidate.expenseCount || deleteCandidate.usedCount || 0)} spese coinvolte</strong>
            <label>
              Sposta spese in
              <select value={redistributeTarget} onChange={(event) => setRedistributeTarget(event.target.value)}>
                {getRedistributionOptions(deleteCandidate).map((category) => (
                  <option key={category.id} value={category.name}>{category.name}</option>
                ))}
              </select>
            </label>
            <div className="profile-category-modal__actions">
              <button type="button" className="profile-ghost-button" onClick={() => setDeleteCandidate(null)}>Annulla</button>
              <button type="button" className="profile-primary-button" onClick={handleConfirmRedistribution}>Elimina e redistribuisci</button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );

  function renderCategoryRow(category, listType) {
    const item = normalizeCategory(category, listType === "monthly" ? "monthly_custom" : "user_default");
    const isMonthly = listType === "monthly";
    const expenseCount = item.expenseCount;
    const iconPickerOpen = categoryPicker?.id === item.id && categoryPicker?.type === "icon";
    const colorPickerOpen = categoryPicker?.id === item.id && categoryPicker?.type === "color";
    return (
      <div key={item.id || item.name} className="profile-category-row">
        <button
          type="button"
          className="profile-category-mark profile-category-mark--editable"
          style={{ "--category-color": item.color }}
          title="Cambia icona"
          onClick={() => setCategoryPicker(iconPickerOpen ? null : { id: item.id, type: "icon" })}
        >
          <CategoryGlyph icon={item.icon} />
        </button>
        {iconPickerOpen ? (
          <div className="profile-category-picker profile-category-picker--icons" role="menu" aria-label={`Scegli icona ${item.name}`}>
            {CATEGORY_ICON_OPTIONS.map((option) => (
              <button
                key={option.value}
                type="button"
                className={option.value === item.icon ? "active" : ""}
                onClick={() => handleUpdateCategory(item, { icon: option.value })}
                title={option.label}
              >
                <CategoryGlyph icon={option.value} />
              </button>
            ))}
          </div>
        ) : null}
        <div className="profile-category-copy">
          <strong>{item.name}</strong>
          <small>
            {isMonthly
              ? `Custom · ${expenseCount} spese`
              : `Predefinita · ${expenseCount} spese`}
          </small>
        </div>
        <button
          type="button"
          className="profile-category-color-dot"
          style={{ "--category-color": item.color }}
          title="Cambia colore"
          onClick={() => setCategoryPicker(colorPickerOpen ? null : { id: item.id, type: "color" })}
        />
        {colorPickerOpen ? (
          <div className="profile-category-picker profile-category-picker--colors" role="menu" aria-label={`Scegli colore ${item.name}`}>
            {CATEGORY_COLOR_OPTIONS.map((option) => (
              <button
                key={option.value}
                type="button"
                className={option.value === item.color ? "active" : ""}
                style={{ "--category-color": option.value }}
                onClick={() => handleUpdateCategory(item, { color: option.value })}
                title={option.label}
              />
            ))}
          </div>
        ) : null}
        <span className="profile-category-count">{expenseCount} spese</span>
        <div className="profile-category-actions">
          <button
            type="button"
            className="profile-category-trash"
            title="Elimina categoria"
            onClick={() => handleDeleteCategory(item)}
          >
            <TrashIcon />
          </button>
        </div>
      </div>
    );
  }
}

function ProfileField({ label, error = "", children }) {
  return (
    <label className={`profile-field${error ? " has-error" : ""}`}>
      <span>
        {label}
        {error ? <em>{error}</em> : null}
      </span>
      {children}
    </label>
  );
}

function ProfileStat({ label, value }) {
  return (
    <div className="profile-stat-pill">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

const DEFAULT_PROFILE_CATEGORIES = [
  { id: "casa", name: "Casa", color: "#63d72a", icon: "home", isSystemDefault: false, deletable: true },
  { id: "spesa", name: "Spesa", color: "#f59e0b", icon: "shopping-cart", isSystemDefault: false, deletable: true },
  { id: "trasporti", name: "Trasporti", color: "#a855f7", icon: "car", isSystemDefault: false, deletable: true },
  { id: "svago", name: "Svago", color: "#3b82f6", icon: "film", isSystemDefault: false, deletable: true },
  { id: "altro", name: "Altro", color: "#6b7280", icon: "more-horizontal", isSystemDefault: false, deletable: true },
];

const CATEGORY_ICON_OPTIONS = [
  { value: "home", label: "Casa" },
  { value: "shopping-cart", label: "Carrello" },
  { value: "car", label: "Auto" },
  { value: "utensils", label: "Forchetta" },
  { value: "gift", label: "Regalo" },
  { value: "heart", label: "Cuore" },
  { value: "plane", label: "Aereo" },
  { value: "music", label: "Musica" },
  { value: "film", label: "Film" },
  { value: "book-open", label: "Libro" },
  { value: "tag", label: "Tag" },
  { value: "more-horizontal", label: "Altro" },
];

const CATEGORY_COLOR_OPTIONS = [
  { value: "#63d72a", label: "Verde" },
  { value: "#f59e0b", label: "Arancio" },
  { value: "#a855f7", label: "Viola" },
  { value: "#3b82f6", label: "Blu" },
  { value: "#ef4444", label: "Rosso" },
  { value: "#6b7280", label: "Grigio" },
  { value: "#22c55e", label: "Smeraldo" },
  { value: "#14b8a6", label: "Teal" },
  { value: "#06b6d4", label: "Ciano" },
  { value: "#8b5cf6", label: "Indaco" },
  { value: "#ec4899", label: "Rosa" },
  { value: "#facc15", label: "Giallo" },
];

function CategoryIconSelect({ value, onChange, compact = false }) {
  const selected = CATEGORY_ICON_OPTIONS.find((option) => option.value === value) || CATEGORY_ICON_OPTIONS[10];
  return (
    <label className={`profile-category-select${compact ? " profile-category-select--compact" : ""}`}>
      <span className="profile-category-select__icon">
        <CategoryGlyph icon={selected.value} />
      </span>
      <select value={selected.value} onChange={(event) => onChange(event.target.value)} aria-label="Icona categoria">
        {CATEGORY_ICON_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function CategoryColorSelect({ value, onChange, compact = false }) {
  const selected = CATEGORY_COLOR_OPTIONS.find((option) => option.value === value) || CATEGORY_COLOR_OPTIONS[0];
  return (
    <label className={`profile-category-select profile-category-color-picker${compact ? " profile-category-select--compact" : ""}`}>
      <span className="profile-category-select__swatch" style={{ "--category-color": selected.value }} />
      <select value={selected.value} onChange={(event) => onChange(event.target.value)} aria-label="Colore categoria">
        {CATEGORY_COLOR_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function CategoryGlyph({ icon }) {
  const pathByIcon = {
    home: <path d="m4 11 8-7 8 7v8.5a1.5 1.5 0 0 1-1.5 1.5H15v-6H9v6H5.5A1.5 1.5 0 0 1 4 19.5Z" />,
    "shopping-cart": <path d="M5 5h1.6l1.2 9.2a2 2 0 0 0 2 1.8h6.9a2 2 0 0 0 1.9-1.4L20 9H7.1M10 20h.01M17 20h.01" />,
    car: <path d="m5 14 1.6-4.2A2.8 2.8 0 0 1 9.2 8h5.6a2.8 2.8 0 0 1 2.6 1.8L19 14M6 18h.01M18 18h.01M4 14h16v4H4Z" />,
    utensils: <path d="M7 3v8M4 3v8M10 3v8M4 11h6M7 11v10M16 3v18M16 3c3 1.5 4 4 4 7v2h-4" />,
    gift: <path d="M20 12v8H4v-8M3 8h18v4H3ZM12 8v12M7.5 8C5.8 8 5 7 5 5.8S6 4 7.2 4C9 4 10.3 6 12 8c1.7-2 3-4 4.8-4C18 4 19 4.8 19 5.8S18.2 8 16.5 8" />,
    heart: <path d="M20.3 5.7a5 5 0 0 0-7.1 0L12 6.9l-1.2-1.2a5 5 0 1 0-7.1 7.1L12 21l8.3-8.2a5 5 0 0 0 0-7.1Z" />,
    plane: <path d="m22 2-8.5 20-4-8.5-8.5-4Z" />,
    music: <path d="M9 18V5l11-2v13M9 18a3 3 0 1 1-3-3 3 3 0 0 1 3 3ZM20 16a3 3 0 1 1-3-3 3 3 0 0 1 3 3Z" />,
    film: <path d="M5 4h14a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2ZM8 4v16M16 4v16M3 9h5M16 9h5M3 15h5M16 15h5" />,
    "book-open": <path d="M12 6.5A6.5 6.5 0 0 0 5.5 4H4v15h1.5A6.5 6.5 0 0 1 12 21m0-14.5A6.5 6.5 0 0 1 18.5 4H20v15h-1.5A6.5 6.5 0 0 0 12 21" />,
    tag: <path d="M20 13 13 20 4 11V4h7Z M7.5 7.5h.01" />,
    "more-horizontal": <path d="M5 12h.01M12 12h.01M19 12h.01" />,
  };

  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      {pathByIcon[icon] || pathByIcon.tag}
    </svg>
  );
}

function mapCategoryList(items, fallbackScope) {
  return (Array.isArray(items) ? items : [])
    .map((category) => normalizeCategory(category, fallbackScope))
    .filter((category) => category.id || category.name);
}

function buildDefaultCategoriesForView(profileDefaultCategories, expenses, monthLabel) {
  const profileByName = new Map(profileDefaultCategories.map((category) => [normalizeCategoryKey(category.name), category]));
  const expenseCounts = buildExpenseCountByCategory(expenses, monthLabel);
  return mapCategoryList(DEFAULT_PROFILE_CATEGORIES, "user_default").map((baseCategory) => {
    const profileCategory = profileByName.get(normalizeCategoryKey(baseCategory.name));
    const item = profileCategory ? { ...baseCategory, ...profileCategory } : baseCategory;
    return normalizeCategory(
      {
        ...item,
        expenseCount: expenseCounts.get(normalizeCategoryKey(baseCategory.name)) || 0,
        isSystemDefault: false,
        deletable: true,
      },
      "user_default",
    );
  });
}

function buildMonthlyCategoriesForView({ expenses, monthLabel, defaultCategories, profileDefaultCategories, monthlyCategories, monthCategoryItems }) {
  const defaultNames = new Set(defaultCategories.map((category) => normalizeCategoryKey(category.name)));
  const expenseCounts = buildExpenseCountByCategory(expenses, monthLabel);
  const apiMonthlyItems = mapCategoryList(monthlyCategories, "monthly_custom");
  const extraProfileItems = mapCategoryList(profileDefaultCategories, "monthly_custom")
    .filter((category) => !defaultNames.has(normalizeCategoryKey(category.name)));
  const monthOnlyItems = mapCategoryList(monthCategoryItems, "monthly_custom")
    .filter((category) => !defaultNames.has(normalizeCategoryKey(category.name)));
  const usedMonthlyItems = buildMonthlyCategoriesFromExpenses(expenses, monthLabel, defaultCategories);
  return mergeCategoriesByName(apiMonthlyItems, extraProfileItems, monthOnlyItems, usedMonthlyItems)
    .map((category) => {
      const expenseCount = Math.max(category.expenseCount || 0, expenseCounts.get(normalizeCategoryKey(category.name)) || 0);
      return {
        ...category,
        scope: "monthly_custom",
        isMonthlyCustom: true,
        expenseCount,
        deletable: expenseCount === 0 && category.deletable !== false,
      };
    })
    .filter((category) => category.expenseCount > 0);
}

function buildMonthlyCategoriesFromExpenses(expenses, monthLabel, defaultCategories) {
  const defaultNames = new Set(defaultCategories.map((category) => normalizeCategoryKey(category.name)));
  const monthlyUsage = new Map();
  (Array.isArray(expenses) ? expenses : []).forEach((expense) => {
    if (expense.month_label !== monthLabel || !expense.category) {
      return;
    }
    const key = normalizeCategoryKey(expense.category);
    if (!key || defaultNames.has(key)) {
      return;
    }
    const current = monthlyUsage.get(key) || {
      id: `monthly-used-${key}`,
      name: expense.category,
      color: "#6b7280",
      icon: "tag",
      scope: "monthly_custom",
      isMonthlyCustom: true,
      deletable: false,
      expenseCount: 0,
    };
    current.expenseCount += 1;
    monthlyUsage.set(key, current);
  });
  return mapCategoryList([...monthlyUsage.values()], "monthly_custom");
}

function mergeCategoriesByName(...categoryGroups) {
  const merged = new Map();
  categoryGroups.flat().forEach((category) => {
    const item = normalizeCategory(category, category.scope);
    const key = normalizeCategoryKey(item.name);
    if (!key) {
      return;
    }
    const previous = merged.get(key);
    merged.set(key, previous ? { ...previous, ...item, expenseCount: Math.max(previous.expenseCount || 0, item.expenseCount || 0) } : item);
  });
  return [...merged.values()];
}

function applyCategoryOverrides(categories, overrides, monthLabel) {
  return categories.map((category) => {
    const item = normalizeCategory(category, category.scope);
    const override = overrides[getCategoryOverrideKey(item, monthLabel)] || {};
    return {
      ...item,
      icon: override.icon || item.icon,
      color: override.color || item.color,
    };
  });
}

function getCategoryOverrideKey(category, monthLabel = "") {
  const item = normalizeCategory(category, category.scope);
  const monthPart = item.scope === "monthly_custom" ? item.monthLabel || monthLabel || "mese" : "sempre";
  return `${item.scope}:${monthPart}:${normalizeCategoryKey(item.name)}`;
}

function loadCategoryOverrides() {
  try {
    return JSON.parse(window.localStorage.getItem("monitor-spese-category-overrides") || "{}");
  } catch {
    return {};
  }
}

function saveCategoryOverrides(overrides) {
  try {
    window.localStorage.setItem("monitor-spese-category-overrides", JSON.stringify(overrides));
  } catch {
    // Local persistence is a UI enhancement; failing here should not block edits.
  }
}

function buildExpenseCountByCategory(expenses, monthLabel) {
  const counts = new Map();
  (Array.isArray(expenses) ? expenses : []).forEach((expense) => {
    if (expense.month_label !== monthLabel || !expense.category) {
      return;
    }
    const key = normalizeCategoryKey(expense.category);
    counts.set(key, (counts.get(key) || 0) + 1);
  });
  return counts;
}

function normalizeCategory(category = {}, fallbackScope = "user_default") {
  const isMonthlyCustom = Boolean(category.isMonthlyCustom ?? category.is_monthly_custom);
  const scope = category.scope || (isMonthlyCustom ? "monthly_custom" : fallbackScope);
  const normalizedColor = normalizeCategoryColor(category.color);
  const name = String(category.name || category.label || category.categoryName || category.category_name || "").trim();
  return {
    ...category,
    id: String(category.id ?? category.category_id ?? category.categoryId ?? name),
    name,
    icon: normalizeCategoryIcon(category.icon),
    color: normalizedColor,
    expenseCount: Number(category.expenseCount ?? category.expense_count ?? category.usedCount ?? category.used_count ?? 0),
    scope,
    isSystemDefault: Boolean(category.isSystemDefault ?? category.is_system_default),
    deletable: Boolean(category.deletable ?? (!category.isSystemDefault && !category.is_system_default)),
  };
}

function normalizeCategoryIcon(icon) {
  const value = String(icon || "tag").trim().toLowerCase();
  const aliases = {
    receipt: "tag",
    gamepad: "film",
    shopping: "shopping-cart",
  };
  const normalizedValue = aliases[value] || value;
  return CATEGORY_ICON_OPTIONS.some((option) => option.value === normalizedValue) ? normalizedValue : "tag";
}

function normalizeCategoryColor(color) {
  const value = String(color || "").trim();
  const namedColors = {
    verde: "#63d72a",
    arancio: "#f59e0b",
    viola: "#a855f7",
    blu: "#3b82f6",
    rosso: "#ef4444",
    grigio: "#6b7280",
  };
  const lowerValue = value.toLowerCase();
  if (namedColors[lowerValue]) {
    return namedColors[lowerValue];
  }
  return CATEGORY_COLOR_OPTIONS.some((option) => option.value.toLowerCase() === lowerValue) ? value : "#63d72a";
}

function getCategoryColorName(color) {
  return CATEGORY_COLOR_OPTIONS.find((option) => option.value.toLowerCase() === String(color).toLowerCase())?.label || "Colore";
}

function normalizeCategoryKey(value) {
  return String(value || "").trim().toLowerCase();
}

function getCurrentMonthLabel() {
  return new Date().toISOString().slice(0, 7);
}

function buildProfileMonthOptions() {
  const current = new Date(`${getCurrentMonthLabel()}-01T00:00:00`);
  return Array.from({ length: 7 }, (_, index) => {
    const date = new Date(current.getFullYear(), current.getMonth() + index - 3, 1);
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
  }).reverse();
}

function formatMonthLabel(monthLabel) {
  const [year, month] = String(monthLabel || "").split("-");
  if (!year || !month) {
    return monthLabel;
  }
  return new Intl.DateTimeFormat("it-IT", { month: "long", year: "numeric" }).format(new Date(`${year}-${month}-01T00:00:00`));
}

function CameraIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M8.4 6.5 9.8 4.75h4.4l1.4 1.75h2.65A2.75 2.75 0 0 1 21 9.25v7.25a2.75 2.75 0 0 1-2.75 2.75H5.75A2.75 2.75 0 0 1 3 16.5V9.25A2.75 2.75 0 0 1 5.75 6.5Z" />
      <circle cx="12" cy="13" r="3.25" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 7h16M10 11v6M14 11v6M9 7l1-3h4l1 3M6 7l1 13h10l1-13" />
    </svg>
  );
}

function setFormValue(setForm, key, value) {
  setForm((current) => ({ ...current, [key]: value }));
}

function validateProfileForm(form) {
  if (!form.full_name.trim()) return "Il nome e obbligatorio.";
  if (!form.username.trim()) return "Lo username e obbligatorio.";
  if (form.email && !isValidEmail(form.email)) return "Email non valida.";
  if (form.new_password && form.new_password.length < 8) return "Password minima 8 caratteri.";
  return "";
}

function isValidEmail(value) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

function formatCurrency(value) {
  return new Intl.NumberFormat("it-IT", { style: "currency", currency: "EUR" }).format(Number(value || 0));
}
