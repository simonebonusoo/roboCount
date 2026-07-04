import { useNavigate } from "react-router-dom";
import { getRobotAvatar } from "../utils/avatars";
import "./CoupleHeroCard.css";

function getHeroAvatar(avatarId) {
  return getRobotAvatar(avatarId).src;
}

function formatHeroBalance(value) {
  const amount = Number(value || 0);

  if (amount > 0) {
    return `+${formatCurrency(amount)}`;
  }
  if (amount < 0) {
    return `-${formatCurrency(Math.abs(amount))}`;
  }
  return "Saldo in equilibrio";
}

function formatCurrency(value) {
  return new Intl.NumberFormat("it-IT", {
    style: "currency",
    currency: "EUR",
  }).format(Number(value || 0));
}

function getHeroStatusLabel(value) {
  const amount = Number(value || 0);
  if (amount > 0) {
    return "DEVI RICEVERE";
  }
  if (amount < 0) {
    return "DEVI DARE";
  }
  return "SIETE IN PARI";
}

export function CoupleHeroCard({ currentUser, partnerUser, balance, statusLabel, description, onSelectUser, onInvitePartner }) {
  const navigate = useNavigate();
  const userAvatarId = currentUser?.avatar_id || currentUser?.avatarId;
  const partnerAvatarId = partnerUser?.avatar_id || partnerUser?.avatarId;
  const userAvatar = getHeroAvatar(userAvatarId);
  const partnerAvatar = getHeroAvatar(partnerAvatarId);
  const hasPartner = Boolean(partnerUser);

  return (
    <section className="hero-surface hero-visual-surface home-visual-card couple-hero-card" aria-label="Saldo di coppia">
      <div className="hero-bg" aria-hidden="true">
        <svg className="hero-bg__lines" viewBox="0 0 1000 520" preserveAspectRatio="none">
          <path d="M -40 340 C 210 250, 385 310, 520 230" />
          <path d="M 1040 300 C 820 230, 640 310, 500 245" />
          <path d="M 80 470 C 310 390, 620 430, 920 350" />
        </svg>
        <span className="hero-bg__center-glow" />
        <span className="hero-bg__particle hero-bg__particle--one" />
        <span className="hero-bg__particle hero-bg__particle--two" />
        <span className="hero-bg__particle hero-bg__particle--three" />
        <span className="hero-bg__particle hero-bg__particle--four" />
        <span className="hero-bg__particle hero-bg__particle--five" />
        <span className="hero-bg__particle hero-bg__particle--six" />
        <span className="hero-bg__particle hero-bg__particle--seven" />
        <span className="hero-bg__particle hero-bg__particle--eight" />
      </div>


      <header className="couple-hero-card__header">
        <span>{statusLabel || getHeroStatusLabel(balance)}</span>
        <strong>{formatHeroBalance(balance)}</strong>
        {description ? <p>{description}</p> : null}
      </header>

      <div className="couple-hero-card__body">
        <button
          type="button"
          className="couple-hero-card__avatar-button couple-hero-card__avatar-button--left"
          onClick={() => onSelectUser?.(currentUser?.username || currentUser?.name || "")}
          aria-label="Apri anteprima utente"
        >
          <img src={userAvatar} className="couple-hero-card__avatar couple-hero-card__avatar--left" alt="" />
        </button>

        <div className="couple-hero-center">
          <button
            type="button"
            className="couple-hero-coins"
            onClick={() => navigate("/couple-balance")}
            aria-label="Apri saldo di coppia"
          >
            <span className="couple-hero-glow" />
            <span className="couple-hero-coin-base" />
            <span className="couple-hero-coin couple-hero-coin--one" />
            <span className="couple-hero-coin couple-hero-coin--two" />
            <span className="couple-hero-coin couple-hero-coin--three" />
            <span className="couple-hero-coin couple-hero-coin--four" />
            <span className="couple-hero-coin couple-hero-coin--five" />
          </button>
        </div>

        <button
          type="button"
          className="couple-hero-card__avatar-button couple-hero-card__avatar-button--right"
          onClick={() => (hasPartner ? onSelectUser?.(partnerUser?.username || partnerUser?.name || "") : onInvitePartner?.())}
          aria-label={hasPartner ? "Apri anteprima partner" : "Invita partner"}
        >
          <img
            src={partnerAvatar}
            className={`couple-hero-card__avatar couple-hero-card__avatar--right${hasPartner ? "" : " is-placeholder"}`}
            alt=""
          />
        </button>
      </div>

      <footer className="couple-hero-card__footer">
        <button type="button" onClick={() => onSelectUser?.(currentUser?.username || currentUser?.name || "")}>
          <span>{currentUser?.username || currentUser?.name || "Tu"}</span>
        </button>
        <button type="button" onClick={() => (hasPartner ? onSelectUser?.(partnerUser?.username || partnerUser?.name || "") : onInvitePartner?.())}>
          <span>{partnerUser?.username || partnerUser?.name || "Partner"}</span>
        </button>
      </footer>
    </section>
  );
}
