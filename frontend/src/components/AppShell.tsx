"use client";

import { useEffect, useState, type FormEvent } from "react";
import { KanbanBoard } from "@/components/KanbanBoard";

const AUTHENTICATED_SESSION_KEY = "pm:isAuthenticated";
const AUTHENTICATED_USERNAME_SESSION_KEY = "pm:authenticatedUsername";
const AUTH_TOKEN_SESSION_KEY = "pm:authToken";

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
  const checks = {
    minLength: password.length >= 8,
    uppercase: /[A-Z]/.test(password),
    lowercase: /[a-z]/.test(password),
    number: /\d/.test(password),
    symbol: /[^A-Za-z0-9]/.test(password),
  };

  const score = Object.values(checks).filter(Boolean).length;
  const isStrong = score === 5;
  return { checks, score, isStrong };
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
      if (!/^[a-z0-9._-]{3,32}$/i.test(normalizedUsername)) {
        setErrorMessage(
          "Username must be 3-32 characters and can include letters, numbers, dots, hyphens, or underscores."
        );
        return;
      }

      if (!passwordStrength.isStrong) {
        setErrorMessage(
          "Use a stronger password that passes all checks below."
        );
        return;
      }

      if (password !== confirmPassword) {
        setErrorMessage("Password confirmation does not match.");
        return;
      }

      setIsStartingSession(true);
      try {
        const response = await fetch("/api/auth/signup", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username: normalizedUsername, password }),
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
      return;
    }

    setIsStartingSession(true);

    try {
      const loginResponse = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: normalizedUsername, password }),
      });

      if (!loginResponse.ok) {
        setErrorMessage("Invalid username or password.");
        return;
      }

      const { username: loggedInUsername, token } =
        (await loginResponse.json()) as AuthResponse;

      setIsAuthenticated(true);
      setAuthenticatedUsername(loggedInUsername);
      setAuthToken(token);
      window.sessionStorage.setItem(AUTHENTICATED_SESSION_KEY, "true");
      window.sessionStorage.setItem(
        AUTHENTICATED_USERNAME_SESSION_KEY,
        loggedInUsername
      );
      window.sessionStorage.setItem(AUTH_TOKEN_SESSION_KEY, token);
      setSessionKey((currentKey) => currentKey + 1);
      setPassword("");
      setConfirmPassword("");
    } catch {
      setErrorMessage("Unable to start your session right now.");
    } finally {
      setIsStartingSession(false);
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

    window.sessionStorage.removeItem(AUTHENTICATED_SESSION_KEY);
    window.sessionStorage.removeItem(AUTHENTICATED_USERNAME_SESSION_KEY);
    window.sessionStorage.removeItem(AUTH_TOKEN_SESSION_KEY);
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
          <div className="pointer-events-none absolute left-0 top-0 h-[420px] w-[420px] -translate-x-1/3 -translate-y-1/3 rounded-full bg-[radial-gradient(circle,_rgba(32,157,215,0.25)_0%,_rgba(32,157,215,0.05)_55%,_transparent_70%)]" />
          <div className="pointer-events-none absolute bottom-0 right-0 h-[520px] w-[520px] translate-x-1/4 translate-y-1/4 rounded-full bg-[radial-gradient(circle,_rgba(117,57,145,0.18)_0%,_rgba(117,57,145,0.05)_55%,_transparent_75%)]" />

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
                        <li>{passwordStrength.checks.minLength ? "[x]" : "[ ]"} At least 8 characters</li>
                        <li>{passwordStrength.checks.uppercase ? "[x]" : "[ ]"} One uppercase letter</li>
                        <li>{passwordStrength.checks.lowercase ? "[x]" : "[ ]"} One lowercase letter</li>
                        <li>{passwordStrength.checks.number ? "[x]" : "[ ]"} One number</li>
                        <li>{passwordStrength.checks.symbol ? "[x]" : "[ ]"} One symbol</li>
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
                {isStartingSession
                  ? "Opening board..."
                  : authMode === "signin"
                    ? "Sign in"
                    : "Create account"}
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
