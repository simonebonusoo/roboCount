export function ThemeToggle({ theme, setTheme }) {
  const nextTheme = theme === "dark" ? "light" : "dark";
  const label = theme === "dark" ? "Attiva tema chiaro" : "Attiva tema scuro";

  return (
    <button
      type="button"
      className="theme-toggle__icon"
      onClick={() => setTheme(nextTheme)}
      aria-label={label}
      title={label}
    >
      {theme === "dark" ? <SunIcon /> : <MoonIcon />}
    </button>
  );
}

function SunIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="4.25" />
      <path d="M12 2.5v2.25M12 19.25v2.25M4.5 12h2.25M17.25 12h2.25M5.9 5.9l1.6 1.6M16.5 16.5l1.6 1.6M18.1 5.9l-1.6 1.6M7.5 16.5l-1.6 1.6" />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M18.2 14.6A7.6 7.6 0 0 1 9.4 5.8a7.9 7.9 0 1 0 8.8 8.8Z" />
    </svg>
  );
}
