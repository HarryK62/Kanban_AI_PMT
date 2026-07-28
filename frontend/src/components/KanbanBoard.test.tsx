import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { KanbanBoard } from "@/components/KanbanBoard";
import { initialData, type BoardData } from "@/lib/kanban";

const getFirstColumn = () => screen.getAllByTestId(/column-/i)[0];
const BOARD_ID = 1;

describe("KanbanBoard", () => {
  let currentBoard: BoardData;

  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();

    if (url.endsWith(`/api/chat/user/${BOARD_ID}/session`)) {
      return new Response(JSON.stringify({ chat_id: 1 }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith(`/api/chat/user/${BOARD_ID}/messages`)) {
      const parsedBody = init?.body ? JSON.parse(String(init.body)) : {};
      if (parsedBody.message === "trigger-chat-failure") {
        return new Response(null, { status: 500 });
      }

      currentBoard = {
        ...currentBoard,
        columns: currentBoard.columns.map((column) =>
          column.id === "col-backlog" ? { ...column, title: "Ideas" } : column
        ),
      };

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
          board: currentBoard,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    }

    if (url.endsWith("/api/boards/user")) {
      return new Response(
        JSON.stringify([
          {
            board_id: BOARD_ID,
            title: currentBoard.title,
            current_board_state_id: 1,
            created_at: "",
            updated_at: "",
          },
        ]),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    }

    if (url.endsWith(`/api/boards/user/${BOARD_ID}`)) {
      if (init?.method === "PUT" && init.body) {
        currentBoard = JSON.parse(String(init.body)) as BoardData;
        return new Response(
          JSON.stringify({
            username: "user",
            board_id: BOARD_ID,
            current_board_state_id: 2,
            board: currentBoard,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }

      return new Response(
        JSON.stringify({
          username: "user",
          board_id: BOARD_ID,
          current_board_state_id: 1,
          board: currentBoard,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    }

    throw new Error(`Unhandled fetch request: ${url}`);
  });

  beforeEach(() => {
    window.sessionStorage.clear();
    currentBoard = structuredClone(initialData);
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockClear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders five columns", async () => {
    render(<KanbanBoard username="user" token="test-token" />);
    await screen.findByText("Backlog");
    expect(screen.getAllByTestId(/column-/i)).toHaveLength(5);
  });

  it("sends the bearer token on the board list fetch", async () => {
    render(<KanbanBoard username="user" token="test-token" />);
    await screen.findByText("Backlog");

    const [, init] = fetchMock.mock.calls[0];
    expect((init as RequestInit).headers).toMatchObject({
      Authorization: "Bearer test-token",
    });
  });

  it("logs out automatically when the board list fetch is unauthorized", async () => {
    const originalImpl = fetchMock.getMockImplementation()!;
    fetchMock.mockImplementation(async (input, init) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/api/boards/user")) {
        return new Response(null, { status: 401 });
      }
      return originalImpl(input, init);
    });

    try {
      const onLogout = vi.fn();
      render(<KanbanBoard username="user" token="stale-token" onLogout={onLogout} />);

      await waitFor(() => expect(onLogout).toHaveBeenCalledTimes(1));
    } finally {
      fetchMock.mockImplementation(originalImpl);
    }
  });

  it("renames a column", async () => {
    render(<KanbanBoard username="user" token="test-token" />);
    await screen.findByText("Backlog");
    const column = getFirstColumn();
    const input = within(column).getByLabelText("Column title");
    // fireEvent.change delivers a single controlled-input update directly,
    // avoiding userEvent's focus/selection simulation which is unreliable
    // for this input immediately after the board's async load settles.
    fireEvent.change(input, { target: { value: "New Name" } });
    await waitFor(() => expect(input).toHaveValue("New Name"));

    // Renaming debounces persistence: wait past the debounce window for the
    // single resulting PUT rather than racing an intermediate fetch count.
    await waitFor(
      () => {
        const putCalls = fetchMock.mock.calls.filter(
          ([, init]) => (init as RequestInit | undefined)?.method === "PUT"
        );
        expect(putCalls).toHaveLength(1);
      },
      { timeout: 2000 }
    );
    const putCalls = fetchMock.mock.calls.filter(
      ([, init]) => (init as RequestInit | undefined)?.method === "PUT"
    );
    expect(JSON.parse(String(putCalls[0][1]?.body)).columns[0].title).toBe(
      "New Name"
    );
  });

  it("adds and removes a card", async () => {
    render(<KanbanBoard username="user" token="test-token" />);
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
    render(<KanbanBoard username="user" token="test-token" />);
    await screen.findByText("Backlog");

    await userEvent.type(screen.getByLabelText("Message"), "Rename Backlog to Ideas.");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() =>
      expect(screen.getByText("I renamed Backlog to Ideas.")).toBeInTheDocument()
    );
    expect(screen.getByText("Ideas")).toBeInTheDocument();
  });

  it("shows a chat error message when the request fails", async () => {
    render(<KanbanBoard username="user" token="test-token" />);
    await screen.findByText("Backlog");

    await userEvent.type(
      screen.getByLabelText("Message"),
      "trigger-chat-failure"
    );
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() =>
      expect(
        screen.getByText("Unable to reach the AI now.")
      ).toBeInTheDocument()
    );
  });

  it("keeps the optimistic update after a successful save", async () => {
    const originalImpl = fetchMock.getMockImplementation()!;
    let resolvePut!: (value: Response) => void;
    const putPromise = new Promise<Response>((resolve) => {
      resolvePut = resolve;
    });
    let capturedBody: string | undefined;

    fetchMock.mockImplementation(async (input, init) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith(`/api/boards/user/${BOARD_ID}`) && init?.method === "PUT") {
        capturedBody = init.body ? String(init.body) : undefined;
        return putPromise;
      }

      return originalImpl(input, init);
    });

    try {
      render(<KanbanBoard username="user" token="test-token" />);
      await screen.findByText("Backlog");

      const column = getFirstColumn();
      await userEvent.click(
        within(column).getByRole("button", { name: /add a card/i })
      );
      await userEvent.type(
        within(column).getByPlaceholderText(/card title/i),
        "Optimistic card"
      );
      await userEvent.click(
        within(column).getByRole("button", { name: /add card/i })
      );

      // The card appears immediately from the optimistic local update,
      // before the in-flight PUT request has resolved.
      expect(within(column).getByText("Optimistic card")).toBeInTheDocument();

      resolvePut(
        new Response(
          JSON.stringify({
            username: "user",
            board_id: BOARD_ID,
            current_board_state_id: 2,
            board: JSON.parse(capturedBody ?? "{}"),
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      );

      // The optimistic update must still be visible once the save succeeds.
      await waitFor(() =>
        expect(within(column).getByText("Optimistic card")).toBeInTheDocument()
      );
    } finally {
      fetchMock.mockImplementation(originalImpl);
    }
  });

  it("submits the chat form when enter is pressed", async () => {
    render(<KanbanBoard username="user" token="test-token" />);
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

    render(<KanbanBoard username="user" token="test-token" />);
    await screen.findByText("Backlog");

    expect(screen.queryByText("Rename Backlog to Ideas.")).not.toBeInTheDocument();
    expect(screen.queryByText("I renamed Backlog to Ideas.")).not.toBeInTheDocument();
    expect(
      screen.getByText(/ask the assistant to create, edit, move, or reorganize cards/i)
    ).toBeInTheDocument();
  });
});
