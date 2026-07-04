import heroDefault from "../assets/heroes/hero-default.png";
import { getRobotAvatar } from "../utils/avatars";

// Temporary mapping: avatar images are used as visible hero fallbacks until final hero1...hero9 assets exist.
export const avatarHeroMap = {
  1: getRobotAvatar("1").src,
  2: getRobotAvatar("2").src,
  3: getRobotAvatar("3").src,
  4: getRobotAvatar("4").src,
  5: getRobotAvatar("5").src,
  6: getRobotAvatar("6").src,
  7: getRobotAvatar("7").src,
  8: getRobotAvatar("8").src,
  9: heroDefault,
};

export function getHomeHeroImage(avatarId) {
  return avatarHeroMap[Number(avatarId)] || heroDefault;
}

export function HomeHeroCard({ avatarId }) {
  const hasAvatarHero = Boolean(avatarHeroMap[Number(avatarId)]);
  const visibleAvatarId = hasAvatarHero ? String(avatarId) : "default";
  const heroImage = getHomeHeroImage(avatarId);

  return (
    <section className="hero-surface hero-visual-surface home-visual-card">
      <div className="hero-image-frame">
        <img src={heroImage} alt="Monitor Spese hero" className="hero-image" />
        <span className="home-hero-debug-label">Avatar hero: {visibleAvatarId || "default"}</span>
      </div>
    </section>
  );
}
