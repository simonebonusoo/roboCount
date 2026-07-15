export function StatusView({ title, message, action }) {
  return (
    <div className="status-view">
      <div className="panel">
        <h2>{title}</h2>
        <p>{message}</p>
        {action || null}
      </div>
    </div>
  );
}
