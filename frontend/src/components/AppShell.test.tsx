import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AppShell } from "@/components/AppShell";
import { initialData, type BoardData } from "@/lib/kanban";

describe("AppShell", () => {
  let boardsByUser: Record<string, BoardData>;
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    if (typeof input === "string" && input.includes("/api/chat/") && input.endsWith("/session")) {
      return new Response(
        JSON.stringify({
          chat_id: 1,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    }

    if (typeof input === "string" && input.includes("/api/board/")) {
      const username = input.split("/").at(-1);
      if (!username) {
        throw new Error(`Invalid board request: ${input}`);
      }

      if (!boardsByUser[username]) {
        boardsByUser[username] = structuredClone(initialData);
      }

      if (init?.method === "PUT" && init.body) {
        boardsByUser[username] = JSON.parse(String(init.body)) as BoardData;
        return new Response(
          JSON.stringify({
            username,
            current_board_state_id: 2,
            board: boardsByUser[username],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }

      return new Response(
        JSON.stringify({
          username,
          current_board_state_id: 1,
          board: boardsByUser[username],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    }

    throw new Error(`Unhandled fetch request: ${String(input)}`);
  });

  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    boardsByUser = {
      harry: structuredClone(initialData),
    };
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockClear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows the login gate before the board", async () => {
    render(<AppShell />);

    expect(screen.getByRole("heading", { name: /sign in to open your board/i })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Kanban Studio" })).not.toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("authenticates with the valid credentials", async () => {
    render(<AppShell />);

    await userEvent.type(screen.getByLabelText(/username/i), "harry");
    await userEvent.type(screen.getByLabelText(/password/i), "kijanka");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByRole("heading", { name: "Kanban Studio" })).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/chat/harry/session", { method: "POST" });
  });

  it("shows an error for invalid credentials", async () => {
    render(<AppShell />);

    await userEvent.type(screen.getByLabelText(/username/i), "wrong");
    await userEvent.type(screen.getByLabelText(/password/i), "credentials");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(screen.getByRole("alert")).toHaveTextContent("Invalid username or password.");
    expect(screen.queryByRole("heading", { name: "Kanban Studio" })).not.toBeInTheDocument();
  });

  it("creates a new account and signs in with it", async () => {
    render(<AppShell />);

    await userEvent.click(screen.getByRole("button", { name: /new here\? sign up/i }));
    await userEvent.type(screen.getByLabelText(/username/i), "newuser");
    await userEvent.type(screen.getByLabelText(/^password$/i), "StrongPass1!");
    await userEvent.type(screen.getByLabelText(/confirm password/i), "StrongPass1!");
    await userEvent.click(screen.getByRole("button", { name: /create account/i }));

    expect(await screen.findByRole("status")).toHaveTextContent("Account created. You can sign in now.");

    await userEvent.type(screen.getByLabelText(/password/i), "StrongPass1!");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByRole("heading", { name: "Kanban Studio" })).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/chat/newuser/session", { method: "POST" });
  });

  it("blocks signup when password is weak", async () => {
    render(<AppShell />);

    await userEvent.click(screen.getByRole("button", { name: /new here\? sign up/i }));
    await userEvent.type(screen.getByLabelText(/username/i), "weakuser");
    await userEvent.type(screen.getByLabelText(/^password$/i), "weak");
    await userEvent.type(screen.getByLabelText(/confirm password/i), "weak");
    await userEvent.click(screen.getByRole("button", { name: /create account/i }));

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Use a stronger password that passes all checks below."
    );
    expect(screen.queryByRole("heading", { name: "Kanban Studio" })).not.toBeInTheDocument();
  });

  it("logs out back to the login screen", async () => {
    render(<AppShell />);

    await userEvent.type(screen.getByLabelText(/username/i), "harry");
    await userEvent.type(screen.getByLabelText(/password/i), "kijanka");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    await screen.findByText("Backlog");
    await userEvent.click(screen.getByRole("button", { name: /log out/i }));

    expect(screen.getByRole("heading", { name: /sign in to open your board/i })).toBeInTheDocument();
  });

  it("restores the current tab session after reload", async () => {
    window.sessionStorage.setItem("pm:isAuthenticated", "true");
    window.sessionStorage.setItem("pm:authenticatedUsername", "harry");

    render(<AppShell />);

    expect(await screen.findByRole("heading", { name: "Kanban Studio" })).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalledWith("/api/chat/harry/session", { method: "POST" });
  });

  it("keeps the same board after logout and login in the same tab", async () => {
    render(<AppShell />);

    await userEvent.type(screen.getByLabelText(/username/i), "harry");
    await userEvent.type(screen.getByLabelText(/password/i), "kijanka");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    await screen.findByText("Backlog");

    const firstColumn = screen.getAllByTestId(/column-/i)[0];
    await userEvent.click(
      within(firstColumn).getByRole("button", { name: /add a card/i })
    );
    await userEvent.type(
      within(firstColumn).getByPlaceholderText(/card title/i),
      "Session card"
    );
    await userEvent.type(
      within(firstColumn).getByPlaceholderText(/details/i),
      "Stays in this tab."
    );
    await userEvent.click(
      within(firstColumn).getByRole("button", { name: /add card/i })
    );
    await userEvent.click(screen.getByRole("button", { name: /log out/i }));

    await userEvent.type(screen.getByLabelText(/username/i), "harry");
    await userEvent.type(screen.getByLabelText(/password/i), "kijanka");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => expect(screen.getByText("Session card")).toBeInTheDocument());
  });
});
