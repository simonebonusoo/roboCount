import { useNavigate } from "react-router-dom";

export function PlaceholderPage({ eyebrow, title, message, actionLabel = "Torna alla Home", actionTo = "/home" }) {
  const navigate = useNavigate();

  return (
    <section className="page">
      <div className="hero-surface placeholder-surface">
        <div className="hero-copy">
          <p className="eyebrow">{eyebrow}</p>
          <h2>{title}</h2>
          <p className="hero-description">{message}</p>
        </div>
        <div className="placeholder-actions">
          <button type="button" className="secondary-button" onClick={() => navigate(actionTo)}>
            {actionLabel}
          </button>
        </div>
      </div>
    </section>
  );
}
