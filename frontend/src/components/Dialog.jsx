export function Dialog({ title, subtitle, icon, children, onClose, footer, className = "" }) {
  return (
    <div className="dialog-backdrop" role="presentation" onClick={onClose}>
      <div
        className={`dialog${className ? ` ${className}` : ""}`}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="dialog-header">
          <div className="dialog-title-group">
            {icon ? <span className="dialog-title-icon" aria-hidden="true">{icon}</span> : null}
            <div>
              <h3>{title}</h3>
              {subtitle ? <p>{subtitle}</p> : null}
            </div>
          </div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Chiudi dialog">
            ×
          </button>
        </div>
        <div className="dialog-body">{children}</div>
        {footer ? <div className="dialog-footer">{footer}</div> : null}
      </div>
    </div>
  );
}
