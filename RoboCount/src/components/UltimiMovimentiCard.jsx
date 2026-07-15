const CATEGORY_STYLES = {
  casa: { color: "#22c55e", icon: "home" },
  spesa: { color: "#f59e0b", icon: "cart" },
  trasporti: { color: "#a855f7", icon: "car" },
  salute: { color: "#22c55e", icon: "heart" },
  svago: { color: "#3b82f6", icon: "sparkle" },
  armoniche: { color: "#f59e0b", icon: "cart" },
  ristorante: { color: "#f59e0b", icon: "cart" },
  ristoranti: { color: "#f59e0b", icon: "cart" },
  carburante: { color: "#a855f7", icon: "car" },
  stipendio: { color: "#22c55e", icon: "wallet" },
};

export function UltimiMovimentiCard({ movements = [], currentUsername = "", onSelectMovement, onViewAll }) {
  const visibleMovements = movements.slice(0, 4);

  return (
    <section className="ultimi-movimenti-card" aria-labelledby="ultimi-movimenti-title">
      <h2 id="ultimi-movimenti-title" className="ultimi-movimenti-card__title">
        Ultimi movimenti
      </h2>

      <div className="ultimi-movimenti-card__list">
        {visibleMovements.length ? (
          visibleMovements.map((movement) => {
            const meta = getMovementMeta(movement, currentUsername);
            return (
              <button
                key={movement.id || `${meta.title}-${movement.expense_date}`}
                type="button"
                className="ultimi-movimenti-card__row"
                onClick={() => onSelectMovement?.(movement)}
              >
                <span className="ultimi-movimenti-card__icon" style={{ background: meta.color }}>
                  <MovementIcon name={meta.icon} />
                </span>
                <span className="ultimi-movimenti-card__copy">
                  <strong>{meta.title}</strong>
                  <span>{meta.subtitle}</span>
                </span>
                <span className="ultimi-movimenti-card__amount">
                  <strong className={meta.isPositive ? "positive" : ""}>{meta.amount}</strong>
                  <span>{meta.date}</span>
                </span>
              </button>
            );
          })
        ) : (
          <div className="ultimi-movimenti-card__empty">Nessun movimento recente</div>
        )}
      </div>

      <button type="button" className="ultimi-movimenti-card__footer" onClick={onViewAll}>
        <span>Vedi tutte le spese</span>
        <span aria-hidden="true">›</span>
      </button>
    </section>
  );
}

function getMovementMeta(movement, currentUsername) {
  const category = String(movement.category || "").toLowerCase();
  const style = CATEGORY_STYLES[category] || CATEGORY_STYLES.spesa;
  const rawAmount = Number(movement.amount || 0);
  const isIncomeLike = rawAmount < 0 || category.includes("stipendio");
  const title = movement.description || movement.name || movement.category || "Spesa";
  const subtitle = getMovementSubtitle(movement, currentUsername);

  return {
    amount: `${isIncomeLike ? "+" : "-"}${formatCurrency(Math.abs(rawAmount))}`,
    color: style.color,
    date: formatMovementDate(movement.expense_date || movement.date || movement.created_at),
    icon: style.icon,
    isPositive: isIncomeLike,
    subtitle,
    title,
  };
}

function getMovementSubtitle(movement, currentUsername) {
  const expenseType = String(movement.expense_type || movement.type || "").toLowerCase();
  const payer = movement.paid_by || movement.payer || "";

  if (expenseType.includes("condiv") || expenseType.includes("shared")) {
    return "Condivisa";
  }
  if (expenseType.includes("personal") || expenseType.includes("personale")) {
    return "Tu";
  }
  if (payer && payer === currentUsername) {
    return "Tu";
  }
  return payer || "Tu";
}

function formatCurrency(value) {
  return new Intl.NumberFormat("it-IT", {
    currency: "EUR",
    style: "currency",
  }).format(value);
}

function formatMovementDate(value) {
  if (!value) {
    return "";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const movementDay = new Date(date);
  movementDay.setHours(0, 0, 0, 0);
  const diffDays = Math.round((today.getTime() - movementDay.getTime()) / 86400000);

  if (diffDays === 0) {
    return "Oggi";
  }
  if (diffDays === 1) {
    return "Ieri";
  }

  return new Intl.DateTimeFormat("it-IT", {
    day: "numeric",
    month: "short",
  }).format(date);
}

function MovementIcon({ name }) {
  const commonProps = {
    fill: "none",
    height: "20",
    stroke: "currentColor",
    strokeLinecap: "round",
    strokeLinejoin: "round",
    strokeWidth: "2",
    viewBox: "0 0 24 24",
    width: "20",
  };

  if (name === "cart") {
    return (
      <svg {...commonProps} aria-hidden="true">
        <path d="M5 5h1.6l1.2 9.2a2 2 0 0 0 2 1.8h6.9a2 2 0 0 0 1.9-1.4L20 9H7.1M10 20h.01M17 20h.01" />
      </svg>
    );
  }

  if (name === "sparkle") {
    return (
      <svg {...commonProps} aria-hidden="true">
        <path d="m12 3 1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9Z" />
      </svg>
    );
  }

  if (name === "car") {
    return (
      <svg {...commonProps} aria-hidden="true">
        <path d="m5 14 1.6-4.2A2.8 2.8 0 0 1 9.2 8h5.6a2.8 2.8 0 0 1 2.6 1.8L19 14M6 18h.01M18 18h.01M4 14h16v4H4Z" />
      </svg>
    );
  }

  if (name === "home") {
    return (
      <svg {...commonProps} aria-hidden="true">
        <path d="m4 11 8-7 8 7v8.5a1.5 1.5 0 0 1-1.5 1.5H15v-6H9v6H5.5A1.5 1.5 0 0 1 4 19.5Z" />
      </svg>
    );
  }

  if (name === "heart") {
    return (
      <svg {...commonProps} aria-hidden="true">
        <path d="M20.4 5.6a5 5 0 0 0-7.1 0L12 6.9l-1.3-1.3a5 5 0 1 0-7.1 7.1L12 21l8.4-8.3a5 5 0 0 0 0-7.1Z" />
      </svg>
    );
  }

  return (
    <svg {...commonProps} aria-hidden="true">
      <path d="M6 3h12v18l-2-1.2-2 1.2-2-1.2-2 1.2-2-1.2L6 21ZM9 8h6M9 12h6M9 16h4" />
    </svg>
  );
}
