"use client";

import { useEffect, useState, type FormEvent } from "react";
import { BackgroundGlow } from "@/components/BackgroundGlow";
import { KanbanBoard } from "@/components/KanbanBoard";

const AUTHENTICATED_SESSION_KEY = "pm:isAuthenticated";
const AUTHENTICATED_USERNAME_SESSION_KEY = "pm:authenticatedUsername";
const AUTH_TOKEN_SESSION_KEY = "pm:authToken";

// Mirrors the backend's USERNAME_PATTERN so the form can fail fast; the
// backend remains the authority and re-validates every signup.
const USERNAME_PATTERN = /^[a-z0-9._-]{3,32}$/i;
const USERNAME_REQUIREMENTS_MESSAGE =
  "Username must be 3-32 characters and can include letters, numbers, dots, hyphens, or underscores.";

const PASSWORD_RULES = [
  { key: "minLength", label: "At least 8 characters" },
  { key: "uppercase", label: "One uppercase letter" },
  { key: "lowercase", label: "One lowercase letter" },
  { key: "number", label: "One number" },
  { key: "symbol", label: "One symbol" },
] as const;

const normalizeUsername = (value: string) => value.trim().toLowerCase();

type AuthResponse = {
  username: string;
  token: string;
};

const parseErrorDetail = async (response: Response): Promise<string> => {
  try {
    const data = (await response.json()) as { detail?: string };
    return typeof data.detail === "string" ? data.detail : "";
  } catch {
    return "";
  }
};

const getPasswordChecks = (password: string) => {
  const checks: Record<(typeof PASSWORD_RULES)[number]["key"], boolean> = {
    minLength: password.length >= 8,
    uppercase: /[A-Z]/.test(password),
    lowercase: /[a-z]/.test(password),
    number: /\d/.test(password),
    symbol: /[^A-Za-z0-9]/.test(password),
  };

  const score = Object.values(checks).filter(Boolean).length;
  return { checks, score, isStrong: score === PASSWORD_RULES.length };
};

const getPasswordStrengthLabel = (score: number) => {
  if (score <= 2) {
    return "Weak";
  }
  if (score <= 4) {
    return "Medium";
  }
  return "Strong";
};

const storeSession = (username: string, token: string) => {
  window.sessionStorage.setItem(AUTHENTICATED_SESSION_KEY, "true");
  window.sessionStorage.setItem(AUTHENTICATED_USERNAME_SESSION_KEY, username);
  window.sessionStorage.setItem(AUTH_TOKEN_SESSION_KEY, token);
};

const clearStoredSession = () => {
  window.sessionStorage.removeItem(AUTHENTICATED_SESSION_KEY);
  window.sessionStorage.removeItem(AUTHENTICATED_USERNAME_SESSION_KEY);
  window.sessionStorage.removeItem(AUTH_TOKEN_SESSION_KEY);
};

const postJson = (url: string, body: unknown) =>
  fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

export const AppShell = () => {
  const [authMode, setAuthMode] = useState<"signin" | "signup">("signin");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [authenticatedUsername, setAuthenticatedUsername] = useState("");
  const [authToken, setAuthToken] = useState("");
  const [sessionKey, setSessionKey] = useState(0);
  const [isStartingSession, setIsStartingSession] = useState(false);
  const [isRestoringSession, setIsRestoringSession] = useState(true);

  const passwordStrength = getPasswordChecks(password);

  useEffect(() => {
    const hasAuthenticatedSession =
      window.sessionStorage.getItem(AUTHENTICATED_SESSION_KEY) === "true";
    const storedUsername = window.sessionStorage.getItem(
      AUTHENTICATED_USERNAME_SESSION_KEY
    );
    const storedToken = window.sessionStorage.getItem(AUTH_TOKEN_SESSION_KEY);
    if (hasAuthenticatedSession && storedUsername) {
      setIsAuthenticated(true);
      setAuthenticatedUsername(storedUsername);
      setAuthToken(storedToken ?? "");
    }
    setIsRestoringSession(false);
  }, []);

  const handleSignup = async (normalizedUsername: string) => {
    if (!USERNAME_PATTERN.test(normalizedUsername)) {
      setErrorMessage(USERNAME_REQUIREMENTS_MESSAGE);
      return;
    }

    if (!passwordStrength.isStrong) {
      setErrorMessage("Use a stronger password that passes all checks below.");
      return;
    }

    if (password !== confirmPassword) {
      setErrorMessage("Password confirmation does not match.");
      return;
    }

    setIsStartingSession(true);
    try {
      const response = await postJson("/api/auth/signup", {
        username: normalizedUsername,
        password,
      });

      if (response.status === 409) {
        setErrorMessage("That username already exists. Please sign in.");
        return;
      }

      if (!response.ok) {
        const detail = await parseErrorDetail(response);
        setErrorMessage(detail || "Unable to create your account right now.");
        return;
      }

      setAuthMode("signin");
      setPassword("");
      setConfirmPassword("");
      setSuccessMessage("Account created. You can sign in now.");
    } catch {
      setErrorMessage("Unable to reach the server right now.");
    } finally {
      setIsStartingSession(false);
    }
  };

  const handleSignin = async (normalizedUsername: string) => {
    setIsStartingSession(true);
    try {
      const response = await postJson("/api/auth/login", {
        username: normalizedUsername,
        password,
      });

      if (!response.ok) {
        setErrorMessage("Invalid username or password.");
        return;
      }

      const { username: loggedInUsername, token } =
        (await response.json()) as AuthResponse;

      setIsAuthenticated(true);
      setAuthenticatedUsername(loggedInUsername);
      setAuthToken(token);
      storeSession(loggedInUsername, token);
      setSessionKey((currentKey) => currentKey + 1);
      setPassword("");
      setConfirmPassword("");
    } catch {
      setErrorMessage("Unable to start your session right now.");
    } finally {
      setIsStartingSession(false);
    }
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const normalizedUsername = normalizeUsername(username);

    if (!normalizedUsername) {
      setErrorMessage("Enter a username.");
      return;
    }

    setErrorMessage("");
    setSuccessMessage("");

    if (authMode === "signup") {
      await handleSignup(normalizedUsername);
    } else {
      await handleSignin(normalizedUsername);
    }
  };

  const handleLogout = () => {
    if (authToken) {
      void fetch("/api/auth/logout", {
        method: "POST",
        headers: { Authorization: `Bearer ${authToken}` },
      }).catch(() => {
        // Best-effort: the client-side session is cleared regardless.
      });
    }

    clearStoredSession();
    setIsAuthenticated(false);
    setAuthenticatedUsername("");
    setAuthToken("");
    setUsername("");
    setPassword("");
    setConfirmPassword("");
    setErrorMessage("");
    setSuccessMessage("");
    setAuthMode("signin");
  };

  if (isRestoringSession) {
    return null;
  }

  const primaryActionLabel =
    authMode === "signin" ? "Sign in" : "Create account";
  const submitLabel = isStartingSession ? "Opening board..." : primaryActionLabel;

  return (
    <div className="relative">
      {isAuthenticated ? (
        <KanbanBoard
          key={sessionKey}
          onLogout={handleLogout}
          username={authenticatedUsername}
          token={authToken}
        />
      ) : (
        <div className="relative overflow-hidden">
          <BackgroundGlow />

          <main className="relative mx-auto flex min-h-screen max-w-[560px] items-center px-6 py-12">
            <form
              onSubmit={handleSubmit}
              className="w-full rounded-[32px] border border-[var(--stroke)] bg-[var(--surface-strong)] p-8 shadow-[var(--shadow)]"
            >
              <p className="text-xs font-semibold uppercase tracking-[0.35em] text-[var(--gray-text)]">
                Project Management MVP
              </p>
              <h1 className="mt-4 font-display text-4xl font-semibold text-[var(--navy-dark)]">
                Sign in to open your board.
              </h1>
              <p className="mt-3 text-sm leading-7 text-[var(--gray-text)]">
                {authMode === "signin"
                  ? "Use your credentials to continue."
                  : "Create an account to start managing your board."}
              </p>
              <div className="mt-7 space-y-4">
                <label className="block">
                  <span className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">
                    Username
                  </span>
                  <input
                    value={username}
                    onChange={(event) => {
                      setUsername(event.target.value);
                      setErrorMessage("");
                      setSuccessMessage("");
                    }}
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
                    onChange={(event) => {
                      setPassword(event.target.value);
                      setErrorMessage("");
                    }}
                    className="mt-2 w-full rounded-2xl border border-[var(--stroke)] bg-white px-4 py-3 text-sm font-medium text-[var(--navy-dark)] outline-none transition focus:border-[var(--primary-blue)]"
                    autoComplete={
                      authMode === "signin"
                        ? "current-password"
                        : "new-password"
                    }
                    aria-label="Password"
                  />
                </label>
                {authMode === "signup" ? (
                  <>
                    <label className="block">
                      <span className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">
                        Confirm Password
                      </span>
                      <input
                        type="password"
                        value={confirmPassword}
                        onChange={(event) => {
                          setConfirmPassword(event.target.value);
                          setErrorMessage("");
                        }}
                        className="mt-2 w-full rounded-2xl border border-[var(--stroke)] bg-white px-4 py-3 text-sm font-medium text-[var(--navy-dark)] outline-none transition focus:border-[var(--primary-blue)]"
                        autoComplete="new-password"
                        aria-label="Confirm Password"
                      />
                    </label>

                    <div className="rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] px-4 py-3 text-sm">
                      <p className="font-semibold text-[var(--navy-dark)]">
                        Password strength: {getPasswordStrengthLabel(passwordStrength.score)}
                      </p>
                      <ul className="mt-2 space-y-1 text-[var(--gray-text)]">
                        {PASSWORD_RULES.map((rule) => (
                          <li key={rule.key}>
                            {passwordStrength.checks[rule.key] ? "[x]" : "[ ]"}{" "}
                            {rule.label}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </>
                ) : null}
              </div>
              {successMessage ? (
                <p
                  className="mt-4 rounded-2xl border border-[var(--primary-blue)] bg-[rgba(32,157,215,0.08)] px-4 py-3 text-sm text-[var(--navy-dark)]"
                  role="status"
                >
                  {successMessage}
                </p>
              ) : null}
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
                className="mt-6 w-full rounded-full bg-[var(--secondary-purple)] px-5 py-3 text-sm font-semibold uppercase tracking-[0.2em] text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-70"
              >
                {submitLabel}
              </button>
              <button
                type="button"
                onClick={() => {
                  setAuthMode((currentMode) =>
                    currentMode === "signin" ? "signup" : "signin"
                  );
                  setPassword("");
                  setConfirmPassword("");
                  setErrorMessage("");
                  setSuccessMessage("");
                }}
                className="mt-3 w-full rounded-full border border-[var(--stroke)] px-5 py-3 text-sm font-semibold uppercase tracking-[0.2em] text-[var(--navy-dark)] transition hover:border-[var(--primary-blue)] hover:text-[var(--primary-blue)]"
              >
                {authMode === "signin"
                  ? "New here? Sign up"
                  : "Have an account? Sign in"}
              </button>
            </form>
          </main>
        </div>
      )}
    </div>
  );
};
