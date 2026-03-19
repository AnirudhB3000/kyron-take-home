import { useEffect, useRef } from "react";

export default function MessageList({ messages }) {
  const endRef = useRef(null);

  useEffect(() => {
    if (typeof endRef.current?.scrollIntoView === "function") {
      endRef.current.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [messages]);

  return (
    <div className="message-list" aria-live="polite">
      {messages.map((message) => (
        <article
          key={message.id}
          className={`message ${message.role}-message`}
        >
          <span className="message-role">
            {message.role === "assistant" ? "Kyron assistant" : "Patient"}
          </span>
          <p>{message.content}</p>
        </article>
      ))}
      <div ref={endRef} aria-hidden="true" />
    </div>
  );
}
