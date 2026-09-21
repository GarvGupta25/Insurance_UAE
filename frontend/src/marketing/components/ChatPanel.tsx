import { useState, useEffect, useRef } from "react";
import "./ChatPanel.css";

const GREETING_TEXT = "Welcome to Helm Ai";
const SUGGESTED_QUESTIONS = [
  "Do I need this if I'm self-sponsored?",
  "What does a waiting period mean?",
  "How does Helm AI's process work?",
];

type ChatMessage = { role: "assistant" | "user"; text: string };

export function ChatPanel({ onClose }: { onClose: () => void }) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: "assistant", text: GREETING_TEXT },
    {
      role: "assistant",
      text: "Ask me anything about UAE health insurance basics, or tap a suggestion below.",
    },
  ]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Focus close button on mount
  useEffect(() => {
    closeButtonRef.current?.focus();
  }, []);

  // Handle Escape to close
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        onClose();
      }
    }
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  // Auto-scroll to latest message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isSending]);

  async function send(text: string) {
    if (!text.trim() || isSending) return;
    setMessages((m) => [...m, { role: "user", text }]);
    setInput("");
    setIsSending(true);
    setError(null);
    try {
      const res = await fetch("/api/public/assistant/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });
      if (res.status === 429) {
        setError("You've reached the message limit for now — please try again shortly.");
        return;
      }
      if (!res.ok) {
        setError("The assistant is unavailable right now. Please try again.");
        return;
      }
      const data = await res.json();
      setMessages((m) => [...m, { role: "assistant", text: data.reply }]);
    } catch {
      setError("Could not reach the assistant. Please check your connection.");
    } finally {
      setIsSending(false);
    }
  }

  const showSuggestions = messages.length <= 2;

  return (
    <div 
      className="chat-panel" 
      role="dialog" 
      aria-label="Helm AI assistant"
      ref={containerRef}
    >
      <div className="chat-panel__header">
        <span>Helm AI Assistant</span>
        <button 
          ref={closeButtonRef}
          type="button" 
          aria-label="Close assistant" 
          onClick={onClose}
        >
          ×
        </button>
      </div>

      <div className="chat-panel__messages">
        {messages.map((m, i) => (
          <div
            key={i}
            className={`chat-panel__message chat-panel__message--${m.role}`}
          >
            {i === 0 && m.role === "assistant" ? <strong>{m.text}</strong> : m.text}
          </div>
        ))}
        {isSending && (
          <div className="chat-panel__message chat-panel__message--assistant">
            Thinking…
          </div>
        )}
        {error && <div className="chat-panel__error">{error}</div>}
        <div ref={messagesEndRef} />
      </div>

      {showSuggestions && (
        <div className="chat-panel__suggestions">
          {SUGGESTED_QUESTIONS.map((q) => (
            <button key={q} type="button" onClick={() => send(q)}>
              {q}
            </button>
          ))}
        </div>
      )}

      <form
        className="chat-panel__composer"
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
      >
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              send(input);
            }
          }}
          placeholder="Ask a question..."
          aria-label="Type your message"
          disabled={isSending}
          rows={1}
        />
        <button type="submit" disabled={isSending || !input.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}
