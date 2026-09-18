import { useEffect, useRef, useState } from "react";
import { DotLottie } from "@lottiefiles/dotlottie-web";
import { ChatPanel } from "./ChatPanel";
import "./ChatbotLauncher.css";

// Bundled locally under frontend/public/assets/
const LOTTIE_SRC = "/assets/robot.json";
const GREETING_TEXT = "Welcome to Helm Ai";
const GREETING_DELAY_MS = 60000; // 60 seconds

export function ChatbotLauncher() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const dotLottieRef = useRef<DotLottie | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [showGreeting, setShowGreeting] = useState(true);

  useEffect(() => {
    if (!canvasRef.current) return;
    dotLottieRef.current = new DotLottie({
      autoplay: true,
      loop: true,
      canvas: canvasRef.current,
      src: LOTTIE_SRC,
    });

    const showTimer = window.setInterval(() => setShowGreeting(true), GREETING_DELAY_MS);

    return () => {
      window.clearInterval(showTimer);
      dotLottieRef.current?.destroy();
    };
  }, []);

  const markInteracted = () => {
    setShowGreeting(false);
  };

  const handleOpen = () => {
    setIsOpen(true);
    markInteracted();
  };

  const handleDismiss = (e: React.MouseEvent) => {
    e.stopPropagation();
    markInteracted();
  };

  return (
    <div className="chatbot-launcher-root">
      {isOpen && <ChatPanel onClose={() => setIsOpen(false)} />}

      <div className="chatbot-launcher">
        {showGreeting && !isOpen && (
          <button
            type="button"
            className="chatbot-greeting-card"
            onClick={handleOpen}
            aria-label={`${GREETING_TEXT} — open the Helm AI assistant`}
          >
            <div
              className="chatbot-greeting-card__close"
              onClick={handleDismiss}
              aria-label="Dismiss message"
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  handleDismiss(e as any);
                }
              }}
            >
              &times;
            </div>
            <span className="chatbot-greeting-card__eyebrow">
              <span className="chatbot-greeting-card__status-dot" />
              Helm AI Assistant
            </span>
            <span className="chatbot-greeting-card__headline">
              {GREETING_TEXT}
              <span className="chatbot-greeting-card__wave" aria-hidden="true">
                👋
              </span>
            </span>
            <span className="chatbot-greeting-card__subtext">
              Your guide to UAE health cover — ask me anything.
            </span>
            <span className="chatbot-greeting-card__tail" aria-hidden="true" />
          </button>
        )}
        <button
          type="button"
          className="chatbot-launcher__button"
          aria-label="Open the Helm AI assistant"
          aria-expanded={isOpen}
          onClick={handleOpen}
        >
          <canvas
            ref={canvasRef}
            width={120}
            height={120}
            className="chatbot-launcher__canvas"
            aria-hidden="true"
          />
        </button>
      </div>
    </div>
  );
}
