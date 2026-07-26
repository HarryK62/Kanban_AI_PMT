"use client";

import { useEffect, useState, type FormEvent } from "react";
import { KanbanBoard } from "@/components/KanbanBoard";

const VALID_USERNAME = "harry";
const VALID_PASSWORD = "kijanka";
const AUTHENTICATED_SESSION_KEY = "pm:isAuthenticated";
const CHAT_MESSAGES_SESSION_KEY = `pm:chatMessages:${VALID_USERNAME}`;

export const AppShell = () => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [sessionKey, setSessionKey] = useState(0);
  const [isStartingSession, setIsStartingSession] = useState(false);
  const [isRestoringSession, setIsRestoringSession] = useState(true);

  useEffect(() => {
    const hasAuthenticatedSession =
      window.sessionStorage.getItem(AUTHENTICATED_SESSION_KEY) === "true";
    if (hasAuthenticatedSession) {
      setIsAuthenticated(true);
    }
    setIsRestoringSession(false);
  }, []);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (username !== VALID_USERNAME || password !== VALID_PASSWORD) {
      setErrorMessage("Use username 'harry' and password 'kijanka'.");
      return;
    }

    setIsStartingSession(true);
    setErrorMessage("");

    try {
      const response = await fetch(`/api/chat/${VALID_USERNAME}/session`, {
        method: "POST",
      });
      if (!response.ok) {
        throw new Error("Unable to start AI chat session.");
      }

      setIsAuthenticated(true);
      window.sessionStorage.setItem(AUTHENTICATED_SESSION_KEY, "true");
      window.sessionStorage.removeItem(CHAT_MESSAGES_SESSION_KEY);
      setSessionKey((currentKey) => currentKey + 1);
      setPassword("");
    } catch {
      setErrorMessage("Unable to start your session right now.");
    } finally {
      setIsStartingSession(false);
    }
  };

  const handleLogout = () => {
    window.sessionStorage.removeItem(AUTHENTICATED_SESSION_KEY);
    window.sessionStorage.removeItem(CHAT_MESSAGES_SESSION_KEY);
    setIsAuthenticated(false);
    setUsername("");
    setPassword("");
    setErrorMessage("");
  };

  if (isRestoringSession) {
    return null;
  }

  return (
    <div className="relative">
      {isAuthenticated ? (
        <KanbanBoard
          key={sessionKey}
          onLogout={handleLogout}
          username={VALID_USERNAME}
        />
      ) : (
        <div className="relative overflow-hidden">
          <div className="pointer-events-none absolute left-0 top-0 h-[420px] w-[420px] -translate-x-1/3 -translate-y-1/3 rounded-full bg-[radial-gradient(circle,_rgba(32,157,215,0.25)_0%,_rgba(32,157,215,0.05)_55%,_transparent_70%)]" />
          <div className="pointer-events-none absolute bottom-0 right-0 h-[520px] w-[520px] translate-x-1/4 translate-y-1/4 rounded-full bg-[radial-gradient(circle,_rgba(117,57,145,0.18)_0%,_rgba(117,57,145,0.05)_55%,_transparent_75%)]" />

          <main className="relative mx-auto flex min-h-screen max-w-[1100px] items-center px-6 py-12">
            <section className="grid w-full gap-8 lg:grid-cols-[1.1fr_0.9fr]">
              <div className="rounded-[32px] border border-[var(--stroke)] bg-white/80 p-8 shadow-[var(--shadow)] backdrop-blur">
                <p className="text-xs font-semibold uppercase tracking-[0.35em] text-[var(--gray-text)]">
                  Project Management MVP
                </p>
                <h1 className="mt-4 font-display text-4xl font-semibold text-[var(--navy-dark)]">
                  Sign in to open your board.
                </h1>
                <p className="mt-4 max-w-xl text-sm leading-7 text-[var(--gray-text)]">
                  This phase uses a frontend-only sign in gate before backend-backed
                  identity exists. Use the MVP credentials to access the Kanban board.
                </p>
                <div className="mt-8 grid gap-4 sm:grid-cols-2">
                  <div className="rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] px-5 py-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[var(--gray-text)]">
                      Username
                    </p>
                    <p className="mt-2 text-lg font-semibold text-[var(--primary-blue)]">
                      {VALID_USERNAME}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] px-5 py-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[var(--gray-text)]">
                      Password
                    </p>
                    <p className="mt-2 text-lg font-semibold text-[var(--secondary-purple)]">
                      {VALID_PASSWORD}
                    </p>
                  </div>
                </div>
              </div>

              <form
                onSubmit={handleSubmit}
                className="rounded-[32px] border border-[var(--stroke)] bg-[var(--surface-strong)] p-8 shadow-[var(--shadow)]"
              >
                <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[var(--gray-text)]">
                  Sign In
                </p>
                <div className="mt-6 space-y-4">
                  <label className="block">
                    <span className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">
                      Username
                    </span>
                    <input
                      value={username}
                      onChange={(event) => setUsername(event.target.value)}
                      className="mt-2 w-full rounded-2xl border border-[var(--stroke)] bg-white px-4 py-3 text-sm font-medium text-[var(--navy-dark)] outline-none transition focus:border-[var(--primary-blue)]"
                      autoComplete="username"
                      aria-label="Username"
                    />
                  </label>
                  <label className="block">
                    <span className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">
                      Password
                    </span>
                    <input
                      type="password"
                      value={password}
                      onChange={(event) => setPassword(event.target.value)}
                      className="mt-2 w-full rounded-2xl border border-[var(--stroke)] bg-white px-4 py-3 text-sm font-medium text-[var(--navy-dark)] outline-none transition focus:border-[var(--primary-blue)]"
                      autoComplete="current-password"
                      aria-label="Password"
                    />
                  </label>
                </div>
                {errorMessage ? (
                  <p
                    className="mt-4 rounded-2xl border border-[var(--accent-yellow)] bg-[rgba(236,173,10,0.08)] px-4 py-3 text-sm text-[var(--navy-dark)]"
                    role="alert"
                  >
                    {errorMessage}
                  </p>
                ) : null}
                <button
                  type="submit"
                  disabled={isStartingSession}
                  className="mt-6 w-full rounded-full bg-[var(--secondary-purple)] px-5 py-3 text-sm font-semibold uppercase tracking-[0.2em] text-white transition hover:brightness-110"
                >
                  {isStartingSession ? "Opening board..." : "Sign in"}
                </button>
              </form>
            </section>
          </main>
        </div>
      )}
    </div>
  );
};
