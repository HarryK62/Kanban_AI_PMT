"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  closestCorners,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { AiChatSidebar } from "@/components/AiChatSidebar";
import { KanbanColumn } from "@/components/KanbanColumn";
import { KanbanCardPreview } from "@/components/KanbanCardPreview";
import { createId, initialData, moveCard, type BoardData, type Card } from "@/lib/kanban";
import type { ChatMessage } from "@/lib/chat";

type KanbanBoardProps = {
  onLogout?: () => void;
  username: string;
  token: string;
};

type BoardSummary = {
  board_id: number;
  title: string;
  current_board_state_id: number;
  created_at: string;
  updated_at: string;
};

type BoardResponse = {
  username: string;
  board_id: number;
  current_board_state_id: number;
  board: BoardData;
};

type ChatReply = {
  assistant_message: {
    id: number;
    content: string;
    role: "assistant";
    sequence_number: number;
  };
  board: BoardData;
  chat_id: number;
  current_board_state_id: number;
};

const CHAT_REQUEST_TIMEOUT_MS = 20_000;
const CHAT_UI_FAILSAFE_TIMEOUT_MS = 25_000;
const RENAME_PERSIST_DEBOUNCE_MS = 400;

export const KanbanBoard = ({ onLogout, username, token }: KanbanBoardProps) => {
  const [boards, setBoards] = useState<BoardSummary[]>([]);
  const [activeBoardId, setActiveBoardId] = useState<number | null>(null);
  const [isLoadingBoards, setIsLoadingBoards] = useState(true);
  const [boardsErrorMessage, setBoardsErrorMessage] = useState("");
  const [isCreatingBoard, setIsCreatingBoard] = useState(false);

  const [board, setBoard] = useState<BoardData>(() => initialData);
  const [activeCardId, setActiveCardId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatErrorMessage, setChatErrorMessage] = useState("");
  const [isChatSubmitting, setIsChatSubmitting] = useState(false);
  const [isMobileChatOpen, setIsMobileChatOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  const authHeader = useMemo(
    () => ({ Authorization: `Bearer ${token}` }),
    [token]
  );

  const handleUnauthorizedResponse = useCallback(
    (response: Response) => {
      if (response.status === 401) {
        onLogout?.();
      }
    },
    [onLogout]
  );

  useEffect(() => {
    let isActive = true;

    const loadBoards = async () => {
      setIsLoadingBoards(true);
      setBoardsErrorMessage("");

      try {
        const response = await fetch(`/api/boards/${username}`, {
          headers: authHeader,
        });
        if (!response.ok) {
          handleUnauthorizedResponse(response);
          throw new Error("Unable to load boards.");
        }

        const data = (await response.json()) as BoardSummary[];
        if (!isActive) {
          return;
        }
        setBoards(data);
        setActiveBoardId((current) =>
          current !== null && data.some((summary) => summary.board_id === current)
            ? current
            : (data[0]?.board_id ?? null)
        );
      } catch {
        if (isActive) {
          setBoardsErrorMessage("Unable to load your boards right now.");
        }
      } finally {
        if (isActive) {
          setIsLoadingBoards(false);
        }
      }
    };

    void loadBoards();

    return () => {
      isActive = false;
    };
  }, [username, authHeader, handleUnauthorizedResponse]);

  useEffect(() => {
    if (activeBoardId === null) {
      setBoard(initialData);
      setChatMessages([]);
      setIsLoading(false);
      return;
    }

    let isActive = true;

    const loadActiveBoard = async () => {
      setIsLoading(true);
      setErrorMessage("");

      try {
        const [boardResponse, sessionResponse] = await Promise.all([
          fetch(`/api/boards/${username}/${activeBoardId}`, { headers: authHeader }),
          fetch(`/api/chat/${username}/${activeBoardId}/session`, {
            method: "POST",
            headers: authHeader,
          }),
        ]);

        if (!sessionResponse.ok) {
          handleUnauthorizedResponse(sessionResponse);
        }
        if (!boardResponse.ok) {
          handleUnauthorizedResponse(boardResponse);
          throw new Error("Unable to load board.");
        }

        const data = (await boardResponse.json()) as BoardResponse;
        if (isActive) {
          setBoard(data.board);
          setChatMessages([]);
        }
      } catch {
        if (isActive) {
          setErrorMessage("Unable to load the board right now.");
        }
      } finally {
        if (isActive) {
          setIsLoading(false);
        }
      }
    };

    void loadActiveBoard();

    return () => {
      isActive = false;
    };
  }, [username, activeBoardId, authHeader, handleUnauthorizedResponse]);

  useEffect(() => {
    if (!isChatSubmitting) {
      return;
    }

    const timeoutId = window.setTimeout(() => {
      setIsChatSubmitting(false);
      setChatErrorMessage("Unable to reach the AI now.");
    }, CHAT_UI_FAILSAFE_TIMEOUT_MS);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [isChatSubmitting]);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 6 },
    })
  );

  const cardsById = useMemo(() => board.cards, [board.cards]);
  const saveGenerationRef = useRef(0);
  const pendingSaveCountRef = useRef(0);
  const renamePersistTimeoutRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (renamePersistTimeoutRef.current !== null) {
        window.clearTimeout(renamePersistTimeoutRef.current);
      }
    };
  }, []);

  const persistBoard = async (nextBoard: BoardData) => {
    if (activeBoardId === null) {
      return;
    }

    setErrorMessage("");
    const generation = ++saveGenerationRef.current;
    pendingSaveCountRef.current += 1;
    setIsSaving(true);

    try {
      const response = await fetch(`/api/boards/${username}/${activeBoardId}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          ...authHeader,
        },
        body: JSON.stringify(nextBoard),
      });

      if (!response.ok) {
        handleUnauthorizedResponse(response);
        throw new Error("Unable to save board.");
      }

      const data = (await response.json()) as BoardResponse;
      if (generation === saveGenerationRef.current) {
        setBoard(data.board);
        setBoards((current) =>
          current.map((summary) =>
            summary.board_id === data.board_id
              ? {
                  ...summary,
                  title: data.board.title,
                  current_board_state_id: data.current_board_state_id,
                }
              : summary
          )
        );
      }
    } finally {
      pendingSaveCountRef.current -= 1;
      if (pendingSaveCountRef.current === 0) {
        setIsSaving(false);
      }
    }
  };

  const updateBoard = (updater: (currentBoard: BoardData) => BoardData) => {
    if (renamePersistTimeoutRef.current !== null) {
      window.clearTimeout(renamePersistTimeoutRef.current);
      renamePersistTimeoutRef.current = null;
    }

    const nextBoard = updater(board);
    setBoard(nextBoard);
    void persistBoard(nextBoard).catch(() => {
      setErrorMessage("Unable to save the latest board changes.");
    });
  };

  const handleDragStart = (event: DragStartEvent) => {
    setActiveCardId(event.active.id as string);
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveCardId(null);

    if (!over || active.id === over.id) {
      return;
    }

    updateBoard((prev) => ({
      ...prev,
      columns: moveCard(prev.columns, active.id as string, over.id as string),
    }));
  };

  const handleRenameColumn = (columnId: string, title: string) => {
    const nextBoard = {
      ...board,
      columns: board.columns.map((column) =>
        column.id === columnId ? { ...column, title } : column
      ),
    };
    setBoard(nextBoard);

    if (renamePersistTimeoutRef.current !== null) {
      window.clearTimeout(renamePersistTimeoutRef.current);
    }
    renamePersistTimeoutRef.current = window.setTimeout(() => {
      renamePersistTimeoutRef.current = null;
      void persistBoard(nextBoard).catch(() => {
        setErrorMessage("Unable to save the latest board changes.");
      });
    }, RENAME_PERSIST_DEBOUNCE_MS);
  };

  const handleAddCard = (columnId: string, title: string, details: string) => {
    const id = createId("card");
    updateBoard((prev) => ({
      ...prev,
      cards: {
        ...prev.cards,
        [id]: { id, title, details: details || "No details yet." },
      },
      columns: prev.columns.map((column) =>
        column.id === columnId
          ? { ...column, cardIds: [...column.cardIds, id] }
          : column
      ),
    }));
  };

  const handleDeleteCard = (columnId: string, cardId: string) => {
    updateBoard((prev) => ({
      ...prev,
      cards: Object.fromEntries(
        Object.entries(prev.cards).filter(([id]) => id !== cardId)
      ),
      columns: prev.columns.map((column) =>
        column.id === columnId
          ? {
              ...column,
              cardIds: column.cardIds.filter((id) => id !== cardId),
            }
          : column
      ),
    }));
  };

  const handleSelectBoard = (boardId: number) => {
    if (boardId === activeBoardId) {
      return;
    }
    setActiveBoardId(boardId);
  };

  const handleCreateBoard = async () => {
    if (isCreatingBoard) {
      return;
    }

    const title = window.prompt("Name your new board", "New board");
    if (title === null) {
      return;
    }

    setIsCreatingBoard(true);
    setBoardsErrorMessage("");

    try {
      const response = await fetch(`/api/boards/${username}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...authHeader,
        },
        body: JSON.stringify({ title: title.trim() || null }),
      });

      if (!response.ok) {
        handleUnauthorizedResponse(response);
        throw new Error("Unable to create board.");
      }

      const data = (await response.json()) as BoardResponse;
      setBoards((current) => [
        ...current,
        {
          board_id: data.board_id,
          title: data.board.title,
          current_board_state_id: data.current_board_state_id,
          created_at: "",
          updated_at: "",
        },
      ]);
      setActiveBoardId(data.board_id);
    } catch {
      setBoardsErrorMessage("Unable to create a new board right now.");
    } finally {
      setIsCreatingBoard(false);
    }
  };

  const handleDeleteBoard = async (boardId: number, boardTitle: string) => {
    if (!window.confirm(`Delete "${boardTitle}"? This cannot be undone.`)) {
      return;
    }

    setBoardsErrorMessage("");

    try {
      const response = await fetch(`/api/boards/${username}/${boardId}`, {
        method: "DELETE",
        headers: authHeader,
      });

      if (!response.ok) {
        handleUnauthorizedResponse(response);
        throw new Error("Unable to delete board.");
      }

      setBoards((current) => {
        const next = current.filter((summary) => summary.board_id !== boardId);
        if (activeBoardId === boardId) {
          setActiveBoardId(next[0]?.board_id ?? null);
        }
        return next;
      });
    } catch {
      setBoardsErrorMessage("Unable to delete that board right now.");
    }
  };

  const activeCard = activeCardId ? cardsById[activeCardId] : null;

  const handleChatSubmit = async (message: string): Promise<boolean> => {
    if (isChatSubmitting || activeBoardId === null) {
      return false;
    }

    const userMessage = {
      id: createId("chat"),
      role: "user" as const,
      content: message,
    };
    setChatMessages((currentMessages) => [...currentMessages, userMessage]);
    setChatErrorMessage("");
    setIsChatSubmitting(true);

    try {
      const controller = new AbortController();
      const timeoutId = window.setTimeout(() => {
        controller.abort();
      }, CHAT_REQUEST_TIMEOUT_MS);

      const response = await (async () => {
        try {
          return await fetch(`/api/chat/${username}/${activeBoardId}/messages`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              ...authHeader,
            },
            body: JSON.stringify({ message }),
            signal: controller.signal,
          });
        } finally {
          window.clearTimeout(timeoutId);
        }
      })();
      if (!response.ok) {
        handleUnauthorizedResponse(response);
        throw new Error("Unable to send chat message.");
      }

      const data = (await response.json()) as ChatReply;
      saveGenerationRef.current += 1;
      setBoard(data.board);
      setChatMessages((currentMessages) => [
        ...currentMessages,
        {
          id: `assistant-${data.assistant_message.id}`,
          role: "assistant",
          content: data.assistant_message.content,
        },
      ]);
      return true;
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        setChatErrorMessage("Unable to reach the AI now.");
      } else {
        setChatErrorMessage("Unable to reach the AI now.");
      }
      return false;
    } finally {
      setIsChatSubmitting(false);
    }
  };

  const mobileChatLabel = chatMessages.length > 0
    ? `AI chat (${chatMessages.length})`
    : "AI chat";

  const hasNoBoards = !isLoadingBoards && boards.length === 0;

  return (
    <div className="relative overflow-hidden">
      <div className="pointer-events-none absolute left-0 top-0 h-[420px] w-[420px] -translate-x-1/3 -translate-y-1/3 rounded-full bg-[radial-gradient(circle,_rgba(32,157,215,0.25)_0%,_rgba(32,157,215,0.05)_55%,_transparent_70%)]" />
      <div className="pointer-events-none absolute bottom-0 right-0 h-[520px] w-[520px] translate-x-1/4 translate-y-1/4 rounded-full bg-[radial-gradient(circle,_rgba(117,57,145,0.18)_0%,_rgba(117,57,145,0.05)_55%,_transparent_75%)]" />

      <main className="relative mx-auto flex min-h-screen max-w-[1400px] flex-col gap-8 px-5 pb-12 pt-10">
        <header className="flex flex-col gap-5 rounded-[32px] border border-[var(--stroke)] bg-white/80 p-7 shadow-[var(--shadow)] backdrop-blur">
          <div className="flex flex-wrap items-start justify-between gap-6">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.35em] text-[var(--gray-text)]">
                Boards
              </p>
              <h1 className="mt-3 font-display text-4xl font-semibold text-[var(--navy-dark)]">
                {board.title}
              </h1>
              <p className="mt-3 max-w-xl text-sm leading-6 text-[var(--gray-text)]">
                Keep momentum visible. Rename columns, drag cards between stages,
                and capture quick notes without getting buried in settings.
              </p>
              {isLoadingBoards || isLoading ? (
                <p className="mt-4 text-sm font-medium text-[var(--primary-blue)]">
                  {isLoadingBoards ? "Loading boards..." : "Loading board..."}
                </p>
              ) : null}
              {!isLoadingBoards && !isLoading && isSaving ? (
                <p
                  role="status"
                  className="mt-4 text-sm font-medium text-[var(--primary-blue)]"
                >
                  Saving...
                </p>
              ) : null}
              {errorMessage ? (
                <p className="mt-4 text-sm font-medium text-[var(--secondary-purple)]">
                  {errorMessage}
                </p>
              ) : null}
              {boardsErrorMessage ? (
                <p className="mt-4 text-sm font-medium text-[var(--secondary-purple)]">
                  {boardsErrorMessage}
                </p>
              ) : null}
            </div>
            <div className="rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] px-5 py-4">
              <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[var(--gray-text)]">
                Focus
              </p>
              <p className="mt-2 text-lg font-semibold text-[var(--primary-blue)]">
                Multiple boards. Five columns each.
              </p>
              {onLogout ? (
                <button
                  type="button"
                  onClick={onLogout}
                  className="mt-4 rounded-full border border-[var(--stroke)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--navy-dark)] transition hover:border-[var(--primary-blue)] hover:text-[var(--primary-blue)]"
                >
                  Log out
                </button>
              ) : null}
            </div>
          </div>

          <div
            className="flex flex-wrap items-center gap-2"
            role="tablist"
            aria-label="Boards"
          >
            {boards.map((summary) => (
              <div
                key={summary.board_id}
                className={`flex items-center gap-2 rounded-full border px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] transition ${
                  summary.board_id === activeBoardId
                    ? "border-[var(--primary-blue)] bg-[var(--primary-blue)] text-white"
                    : "border-[var(--stroke)] text-[var(--navy-dark)] hover:border-[var(--primary-blue)]"
                }`}
              >
                <button
                  type="button"
                  role="tab"
                  aria-selected={summary.board_id === activeBoardId}
                  onClick={() => handleSelectBoard(summary.board_id)}
                >
                  {summary.title}
                </button>
                <button
                  type="button"
                  aria-label={`Delete ${summary.title}`}
                  onClick={() => handleDeleteBoard(summary.board_id, summary.title)}
                  className="opacity-70 hover:opacity-100"
                >
                  ×
                </button>
              </div>
            ))}
            <button
              type="button"
              onClick={handleCreateBoard}
              disabled={isCreatingBoard}
              className="rounded-full border border-dashed border-[var(--stroke)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--navy-dark)] transition hover:border-[var(--primary-blue)] hover:text-[var(--primary-blue)] disabled:cursor-not-allowed disabled:opacity-60"
            >
              + New board
            </button>
          </div>

          {!hasNoBoards ? (
            <div className="flex flex-wrap items-center gap-4">
              {board.columns.map((column) => (
                <div
                  key={column.id}
                  className="flex items-center gap-2 rounded-full border border-[var(--stroke)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--navy-dark)]"
                >
                  <span className="h-2 w-2 rounded-full bg-[var(--accent-yellow)]" />
                  {column.title}
                </div>
              ))}
            </div>
          ) : null}
        </header>

        {hasNoBoards ? (
          <section className="rounded-[32px] border border-dashed border-[var(--stroke)] bg-white/60 p-10 text-center">
            <p className="font-display text-2xl font-semibold text-[var(--navy-dark)]">
              You don&apos;t have any boards yet.
            </p>
            <p className="mt-2 text-sm text-[var(--gray-text)]">
              Create your first board to start organizing work.
            </p>
            <button
              type="button"
              onClick={handleCreateBoard}
              disabled={isCreatingBoard}
              className="mt-6 rounded-full bg-[var(--secondary-purple)] px-5 py-3 text-xs font-semibold uppercase tracking-[0.2em] text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-70"
            >
              Create your first board
            </button>
          </section>
        ) : (
          <section className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_300px]">
            <div>
              <DndContext
                sensors={sensors}
                collisionDetection={closestCorners}
                onDragStart={handleDragStart}
                onDragEnd={handleDragEnd}
              >
                <div className="overflow-x-auto pb-2">
                  <section className="flex min-w-max gap-3" aria-busy={isLoading}>
                    {board.columns.map((column) => (
                      <div key={column.id} className="w-[208px] shrink-0">
                        <KanbanColumn
                          column={column}
                          cards={column.cardIds
                            .map((cardId) => board.cards[cardId])
                            .filter((card): card is Card => card !== undefined)}
                          onRename={handleRenameColumn}
                          onAddCard={handleAddCard}
                          onDeleteCard={handleDeleteCard}
                        />
                      </div>
                    ))}
                  </section>
                </div>
                <DragOverlay>
                  {activeCard ? (
                    <div className="w-[244px]">
                      <KanbanCardPreview card={activeCard} />
                    </div>
                  ) : null}
                </DragOverlay>
              </DndContext>
            </div>

            <div className="sticky top-8 hidden self-start lg:block">
              <AiChatSidebar
                errorMessage={chatErrorMessage}
                isSubmitting={isChatSubmitting}
                messages={chatMessages}
                onSubmit={handleChatSubmit}
              />
            </div>
          </section>
        )}

        {!hasNoBoards ? (
          <div className="lg:hidden">
            <button
              type="button"
              onClick={() => setIsMobileChatOpen(true)}
              className="fixed bottom-5 right-5 z-40 rounded-full bg-[var(--secondary-purple)] px-5 py-3 text-xs font-semibold uppercase tracking-[0.2em] text-white shadow-[var(--shadow)] transition hover:brightness-110"
            >
              {mobileChatLabel}
            </button>

            <div
              className={`fixed inset-0 z-50 transition ${
                isMobileChatOpen
                  ? "pointer-events-auto"
                  : "pointer-events-none"
              }`}
              aria-hidden={!isMobileChatOpen}
            >
              <button
                type="button"
                onClick={() => setIsMobileChatOpen(false)}
                className={`absolute inset-0 bg-[rgba(3,33,71,0.45)] transition ${
                  isMobileChatOpen ? "opacity-100" : "opacity-0"
                }`}
                aria-label="Close AI chat"
              />
              <div
                className={`absolute inset-x-0 bottom-0 h-[78vh] transform transition-transform duration-300 ${
                  isMobileChatOpen ? "translate-y-0" : "translate-y-full"
                }`}
              >
                {isMobileChatOpen ? (
                  <AiChatSidebar
                    className="h-full min-h-0 max-h-none rounded-b-none rounded-t-[28px] border-b-0"
                    errorMessage={chatErrorMessage}
                    isSubmitting={isChatSubmitting}
                    messages={chatMessages}
                    onSubmit={handleChatSubmit}
                  />
                ) : null}
              </div>
            </div>
          </div>
        ) : null}
      </main>
    </div>
  );
};
