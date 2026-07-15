export function FeedbackBanner({ type = "info", message }) {
  if (!message) {
    return null;
  }

  return <div className={`feedback-banner ${type}`}>{message}</div>;
}
