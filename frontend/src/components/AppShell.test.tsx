import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AppShell } from "@/components/AppShell";

describe("AppShell", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("shows the login gate before the board", () => {
    render(<AppShell />);

    expect(screen.getByRole("heading", { name: /sign in to open your board/i })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Kanban Studio" })).not.toBeInTheDocument();
  });

  it("authenticates with the valid credentials", async () => {
    render(<AppShell />);

    await userEvent.type(screen.getByLabelText(/username/i), "user");
    await userEvent.type(screen.getByLabelText(/password/i), "password");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(screen.getByRole("heading", { name: "Kanban Studio" })).toBeInTheDocument();
    expect(window.localStorage.getItem("pm-authenticated")).toBe("true");
  });

  it("shows an error for invalid credentials", async () => {
    render(<AppShell />);

    await userEvent.type(screen.getByLabelText(/username/i), "wrong");
    await userEvent.type(screen.getByLabelText(/password/i), "credentials");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Use username 'user' and password 'password'."
    );
    expect(screen.queryByRole("heading", { name: "Kanban Studio" })).not.toBeInTheDocument();
  });

  it("logs out back to the login screen", async () => {
    render(<AppShell />);

    await userEvent.type(screen.getByLabelText(/username/i), "user");
    await userEvent.type(screen.getByLabelText(/password/i), "password");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    await userEvent.click(screen.getByRole("button", { name: /log out/i }));

    expect(screen.getByRole("heading", { name: /sign in to open your board/i })).toBeInTheDocument();
    expect(window.localStorage.getItem("pm-authenticated")).toBeNull();
  });
});
