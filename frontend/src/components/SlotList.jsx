function formatSlot(slot) {
  const start = new Date(slot.start_at);
  return start.toLocaleString([], {
    weekday: "long",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export default function SlotList({
  slots,
  onSelect,
  disabled,
  pendingSlotId,
  selectedWeekday,
}) {
  if (!slots.length) {
    return null;
  }

  return (
    <section className="slot-panel glass-card" aria-label="Available appointments">
      <div className="slot-panel-header">
        <p className="section-kicker">Available times</p>
        <h3>Select an appointment</h3>
        <p className="slot-panel-copy">
          {selectedWeekday
            ? `Showing the current ${selectedWeekday} view. Choose a time, then confirm it in chat.`
            : "Choose a time card, then confirm the appointment in chat before it is booked."}
        </p>
      </div>
      <div className="slot-grid">
        {slots.map((slot) => (
          <button
            key={slot.slot_id}
            type="button"
            className={`slot-card${pendingSlotId === slot.slot_id ? " slot-card-pending" : ""}`}
            onClick={() => onSelect(slot.slot_id)}
            disabled={disabled}
          >
            <span>{formatSlot(slot)}</span>
            <strong>{slot.appointment_type.replaceAll("_", " ")}</strong>
            <span className="slot-card-meta">
              {pendingSlotId === slot.slot_id ? "Pending your confirmation" : "Tap to hold this time"}
            </span>
            {pendingSlotId === slot.slot_id ? <em>Awaiting confirmation</em> : null}
          </button>
        ))}
      </div>
    </section>
  );
}
