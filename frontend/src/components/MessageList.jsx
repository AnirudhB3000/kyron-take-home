import { useEffect, useRef } from "react";

export default function MessageList({ messages }) {
  const listRef = useRef(null);

  useEffect(() => {
    const listElement = listRef.current;
    if (!listElement) {
      return;
    }

    const targetTop = listElement.scrollHeight;
    if (typeof listElement.scrollTo === "function") {
      listElement.scrollTo({ top: targetTop, behavior: "smooth" });
      return;
    }

    listElement.scrollTop = targetTop;
  }, [messages]);

  return (
    <div ref={listRef} className="message-list" aria-live="polite">
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
    </div>
  );
}
