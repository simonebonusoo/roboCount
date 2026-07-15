export function MonthNavigation({ label, onPrevious, onNext }) {
  return (
    <div className="month-navigation">
      <button type="button" className="month-navigation-button" onClick={onPrevious} aria-label="Mese precedente">
        ←
      </button>
      <div className="month-navigation-label">
        <CalendarGlyph />
        <span>{label}</span>
      </div>
      <button type="button" className="month-navigation-button" onClick={onNext} aria-label="Mese successivo">
        →
      </button>
    </div>
  );
}

function CalendarGlyph() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M7 3.75v3M17 3.75v3" />
      <path d="M5.25 6.25h13.5a1.5 1.5 0 0 1 1.5 1.5v10.5a1.5 1.5 0 0 1-1.5 1.5H5.25a1.5 1.5 0 0 1-1.5-1.5V7.75a1.5 1.5 0 0 1 1.5-1.5Z" />
      <path d="M4 10h16" />
    </svg>
  );
}
