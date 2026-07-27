"use client";

import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import type { ChatMessage } from "@/lib/chat";

type AiChatSidebarProps = {
  className?: string;
  errorMessage: string;
  isSubmitting: boolean;
  messages: ChatMessage[];
  onSubmit: (message: string) => Promise<boolean>;
};

export const AiChatSidebar = ({
  className,
  errorMessage,
  isSubmitting,
  messages,
  onSubmit,
}: AiChatSidebarProps) => {
  const [message, setMessage] = useState("");
  const formRef = useRef<HTMLFormElement | null>(null);
  const messagesRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const element = messagesRef.current;
    if (!element) {
      return;
    }

    element.scrollTop = element.scrollHeight;
  }, [isSubmitting, messages]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmedMessage = message.trim();
    if (!trimmedMessage || isSubmitting) {
      return;
    }

    const didSend = await onSubmit(trimmedMessage);
    if (didSend) {
      setMessage("");
    }
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== "Enter" || event.shiftKey) {
      return;
    }

    event.preventDefault();
    formRef.current?.requestSubmit();
  };

  return (
    <aside
      className={`flex h-full min-h-[500px] max-h-[calc(100vh-5rem)] flex-col rounded-[32px] border border-[var(--stroke)] bg-white p-5 shadow-[var(--shadow)] ${className ?? ""}`}
    >
      <div className="border-b border-[var(--stroke)] pb-4">
        <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[var(--gray-text)]">
          AI Assistant
        </p>
        <h2 className="mt-3 font-display text-2xl font-semibold text-[var(--navy-dark)]">
          Plan changes in plain language.
        </h2>
        <p className="mt-3 text-sm leading-6 text-[var(--gray-text)]">
          Ask the assistant to create, edit, move, or reorganize cards. This
          panel shows only the current login session.
        </p>
      </div>

      <div ref={messagesRef} className="mt-4 min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
        {messages.length === 0 ? (
          <div className="rounded-3xl border border-dashed border-[var(--stroke)] bg-[var(--surface)] px-4 py-5 text-sm leading-6 text-[var(--gray-text)]">
            Try “Move the analytics task to In Progress” or “Add a QA follow-up
            card to Review.”
          </div>
        ) : null}
        {messages.map((chatMessage) => (
          <article
            key={chatMessage.id}
            className={
              chatMessage.role === "user"
                ? "ml-8 rounded-[24px] bg-[var(--navy-dark)] px-4 py-3 text-sm leading-6 text-white"
                : "mr-8 rounded-[24px] border border-[var(--stroke)] bg-white px-4 py-3 text-sm leading-6 text-[var(--navy-dark)]"
            }
          >
            <p className="text-[10px] font-semibold uppercase tracking-[0.2em] opacity-70">
              {chatMessage.role === "user" ? "You" : "Assistant"}
            </p>
            <p className="mt-2 whitespace-pre-wrap">{chatMessage.content}</p>
          </article>
        ))}
        {isSubmitting ? (
          <div className="mr-8 rounded-[24px] border border-[var(--stroke)] bg-white px-4 py-3 text-sm font-medium text-[var(--primary-blue)]">
            Working on it...
          </div>
        ) : null}
      </div>

      <form
        ref={formRef}
        onSubmit={handleSubmit}
        className="mt-4 border-t border-[var(--stroke)] pt-4"
      >
        <label className="block">
          <span className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">
            Message
          </span>
          <textarea
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            onKeyDown={handleKeyDown}
            rows={4}
            placeholder="Ask the AI to update the board..."
            className="mt-2 w-full resize-none rounded-3xl border border-[var(--stroke)] bg-white px-4 py-3 text-sm leading-6 text-[var(--navy-dark)] outline-none transition focus:border-[var(--primary-blue)]"
            aria-label="Message"
          />
        </label>
        {errorMessage ? (
          <p className="mt-3 rounded-2xl border border-[var(--accent-yellow)] bg-[rgba(236,173,10,0.08)] px-4 py-3 text-sm text-[var(--navy-dark)]">
            {errorMessage}
          </p>
        ) : null}
        <div className="mt-3 flex items-center justify-between gap-3">
          <button
            type="submit"
            disabled={isSubmitting || !message.trim()}
            className="ml-auto rounded-full bg-[var(--secondary-purple)] px-5 py-3 text-xs font-semibold uppercase tracking-[0.2em] text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-80"
          >
            Send
          </button>
        </div>
      </form>
    </aside>
  );
};
