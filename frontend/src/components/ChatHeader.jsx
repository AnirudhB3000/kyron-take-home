import StatusBadge from "./StatusBadge";

export default function ChatHeader({
  status,
  onContinueByPhone,
  phoneDisabled,
  handoffSubmitting,
  workflowLabel,
}) {
  return (
    <header className="chat-header">
      <div className="chat-heading">
        <p className="section-kicker">Live system</p>
        <h2>Patient conversation</h2>
        <p className="chat-heading-copy">
          {workflowLabel} is live. The assistant should stay calm, explicit, and recoverable.
        </p>
      </div>
      <div className="chat-actions">
        <StatusBadge label={status.label} tone={status.tone} />
        <button
          type="button"
          onClick={onContinueByPhone}
          disabled={phoneDisabled || handoffSubmitting}
        >
          {handoffSubmitting ? "Preparing phone handoff..." : "Continue by phone"}
        </button>
      </div>
    </header>
  );
}
