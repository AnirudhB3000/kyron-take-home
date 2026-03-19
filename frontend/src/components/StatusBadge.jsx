export default function StatusBadge({ label, tone }) {
  return (
    <span className={`status-badge status-${tone}`}>
      <span className="status-dot" aria-hidden="true" />
      {label}
    </span>
  );
}
