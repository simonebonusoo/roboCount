export function MonthNavigation({ label, onPrevious, onNext }) {
  return (
    <div className="month-navigation">
      <button type="button" className="month-navigation-button" onClick={onPrevious} aria-label="Mese precedente">
        ←
      </button>
      <div className="month-navigation-label">{label}</div>
      <button type="button" className="month-navigation-button" onClick={onNext} aria-label="Mese successivo">
        →
      </button>
    </div>
  );
}
