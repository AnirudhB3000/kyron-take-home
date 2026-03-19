import { useState } from "react";

const ACTIVE_FIELD_HINTS = {
  first_name: "Use the patient's legal first name.",
  last_name: "Use the patient's legal last name.",
  date_of_birth: "Format the date as YYYY-MM-DD.",
  phone_number: "A valid phone number unlocks the phone handoff.",
  email: "This is where the appointment confirmation email will be sent.",
  appointment_reason: "Describe the body part or issue in plain language, such as knee pain or sinus pressure.",
};

export default function ChatComposer({ disabled, onSubmit, workflowLabel, activeField }) {
  const [value, setValue] = useState("");

  function submitCurrentValue() {
    if (!value.trim() || disabled) {
      return;
    }

    onSubmit(value);
    setValue("");
  }

  function handleSubmit(event) {
    event.preventDefault();
    submitCurrentValue();
  }

  function handleKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submitCurrentValue();
    }
  }

  return (
    <form className="composer" onSubmit={handleSubmit}>
      <div className="composer-header">
        <label className="composer-label" htmlFor="message">
          Tell us how we can help
        </label>
        <span className="composer-stage">{workflowLabel}</span>
      </div>
      <p className="composer-hint">
        {ACTIVE_FIELD_HINTS[activeField] || "The assistant can handle scheduling, office information, refill requests, and phone handoff."}
      </p>
      <textarea
        id="message"
        name="message"
        rows="4"
        placeholder="I need an appointment for my knee."
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
      />
      <button type="submit" disabled={disabled || !value.trim()}>
        Send
      </button>
    </form>
  );
}
