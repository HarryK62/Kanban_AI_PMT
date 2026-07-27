import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { KanbanBoard } from "@/components/KanbanBoard";
import { initialData } from "@/lib/kanban";

const getFirstColumn = () => screen.getAllByTestId(/column-/i)[0];

describe("KanbanBoard", () => {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    if (typeof input === "string" && input.endsWith("/api/chat/user/messages")) {
      return new Response(
        JSON.stringify({
          chat_id: 1,
          current_board_state_id: 2,
          assistant_message: {
            id: 2,
            sequence_number: 2,
            role: "assistant",
            content: "I renamed Backlog to Ideas.",
          },
          board: {
            ...initialData,
            columns: initialData.columns.map((column) =>
              column.id === "col-backlog" ? { ...column, title: "Ideas" } : column
            ),
          },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    }

    if (typeof input === "string" && input.endsWith("/api/board/user")) {
      if (init?.method === "PUT" && init.body) {
        return new Response(
          JSON.stringify({
            username: "user",
            board: JSON.parse(String(init.body)),
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }

      return new Response(
        JSON.stringify({
          username: "user",
          board: initialData,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    }

    throw new Error(`Unhandled fetch request: ${String(input)}`);
  });

  beforeEach(() => {
    window.sessionStorage.clear();
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockClear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders five columns", async () => {
    render(<KanbanBoard username="user" />);
    await screen.findByText("Backlog");
    expect(screen.getAllByTestId(/column-/i)).toHaveLength(5);
  });

  it("renames a column", async () => {
    render(<KanbanBoard username="user" />);
    await screen.findByText("Backlog");
    const column = getFirstColumn();
    const input = within(column).getByLabelText("Column title");
    const fetchCallsBeforeRename = fetchMock.mock.calls.length;
    await userEvent.clear(input);
    await userEvent.type(input, "New Name");
    await waitFor(() => expect(input).toHaveValue("New Name"));

    // Renaming debounces persistence, so keystrokes should not each fire a PUT.
    await waitFor(() =>
      expect(fetchMock.mock.calls.length).toBeGreaterThan(fetchCallsBeforeRename)
    );
    const putCalls = fetchMock.mock.calls.filter(
      ([, init]) => (init as RequestInit | undefined)?.method === "PUT"
    );
    expect(putCalls).toHaveLength(1);
    expect(JSON.parse(String(putCalls[0][1]?.body)).columns[0].title).toBe(
      "New Name"
    );
  });

  it("adds and removes a card", async () => {
    render(<KanbanBoard username="user" />);
    await screen.findByText("Backlog");
    const column = getFirstColumn();
    const addButton = within(column).getByRole("button", {
      name: /add a card/i,
    });
    await userEvent.click(addButton);

    const titleInput = within(column).getByPlaceholderText(/card title/i);
    await userEvent.type(titleInput, "New card");
    const detailsInput = within(column).getByPlaceholderText(/details/i);
    await userEvent.type(detailsInput, "Notes");

    await userEvent.click(within(column).getByRole("button", { name: /add card/i }));

    await waitFor(() => expect(within(column).getByText("New card")).toBeInTheDocument());

    const deleteButton = within(column).getByRole("button", {
      name: /delete new card/i,
    });
    await userEvent.click(deleteButton);

    await waitFor(() =>
      expect(within(column).queryByText("New card")).not.toBeInTheDocument()
    );
  });

  it("sends a chat message and applies the returned board update", async () => {
    render(<KanbanBoard username="user" />);
    await screen.findByText("Backlog");

    await userEvent.type(screen.getByLabelText("Message"), "Rename Backlog to Ideas.");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() =>
      expect(screen.getByText("I renamed Backlog to Ideas.")).toBeInTheDocument()
    );
    expect(screen.getByText("Ideas")).toBeInTheDocument();
  });

  it("submits the chat form when enter is pressed", async () => {
    render(<KanbanBoard username="user" />);
    await screen.findByText("Backlog");

    await userEvent.type(screen.getByLabelText("Message"), "Rename Backlog to Ideas.{enter}");

    await waitFor(() =>
      expect(screen.getByText("I renamed Backlog to Ideas.")).toBeInTheDocument()
    );
  });

  it("starts with an empty chat view after reload", async () => {
    window.sessionStorage.setItem(
      "pm:chatMessages:user",
      JSON.stringify([
        {
          id: "user-1",
          role: "user",
          content: "Rename Backlog to Ideas.",
        },
        {
          id: "assistant-2",
          role: "assistant",
          content: "I renamed Backlog to Ideas.",
        },
      ])
    );

    render(<KanbanBoard username="user" />);
    await screen.findByText("Backlog");

    expect(screen.queryByText("Rename Backlog to Ideas.")).not.toBeInTheDocument();
    expect(screen.queryByText("I renamed Backlog to Ideas.")).not.toBeInTheDocument();
    expect(
      screen.getByText(/ask the assistant to create, edit, move, or reorganize cards/i)
    ).toBeInTheDocument();
  });
});
