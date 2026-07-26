"use client";

import { useEffect, useMemo, useState } from "react";
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
import { createId, initialData, moveCard, type BoardData } from "@/lib/kanban";

type KanbanBoardProps = {
  onLogout?: () => void;
  username: string;
};

type BoardResponse = {
  username: string;
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

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

const CHAT_REQUEST_TIMEOUT_MS = 20_000;
const CHAT_UI_FAILSAFE_TIMEOUT_MS = 25_000;

export const KanbanBoard = ({ onLogout, username }: KanbanBoardProps) => {
  const [board, setBoard] = useState<BoardData>(() => initialData);
  const [activeCardId, setActiveCardId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatErrorMessage, setChatErrorMessage] = useState("");
  const [isChatSubmitting, setIsChatSubmitting] = useState(false);
  const [isMobileChatOpen, setIsMobileChatOpen] = useState(false);

  useEffect(() => {
    let isActive = true;

    const loadBoard = async () => {
      setIsLoading(true);
      setErrorMessage("");

      try {
        const response = await fetch(`/api/board/${username}`);
        if (!response.ok) {
          throw new Error("Unable to load board.");
        }

        const data = (await response.json()) as BoardResponse;
        if (isActive) {
          setBoard(data.board);
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

    void loadBoard();

    return () => {
      isActive = false;
    };
  }, [username]);

  useEffect(() => {
    setChatMessages([]);
  }, [username]);

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

  const persistBoard = async (nextBoard: BoardData) => {
    setErrorMessage("");

    const response = await fetch(`/api/board/${username}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(nextBoard),
    });

    if (!response.ok) {
      throw new Error("Unable to save board.");
    }

    const data = (await response.json()) as BoardResponse;
    setBoard(data.board);
  };

  const updateBoard = (updater: (currentBoard: BoardData) => BoardData) => {
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
    updateBoard((prev) => ({
      ...prev,
      columns: prev.columns.map((column) =>
        column.id === columnId ? { ...column, title } : column
      ),
    }));
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

  const activeCard = activeCardId ? cardsById[activeCardId] : null;

  const handleChatSubmit = async (message: string): Promise<boolean> => {
    if (isChatSubmitting) {
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
          return await fetch(`/api/chat/${username}/messages`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({ message }),
            signal: controller.signal,
          });
        } finally {
          window.clearTimeout(timeoutId);
        }
      })();
      if (!response.ok) {
        throw new Error("Unable to send chat message.");
      }

      const data = (await response.json()) as ChatReply;
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

  return (
    <div className="relative overflow-hidden">
      <div className="pointer-events-none absolute left-0 top-0 h-[420px] w-[420px] -translate-x-1/3 -translate-y-1/3 rounded-full bg-[radial-gradient(circle,_rgba(32,157,215,0.25)_0%,_rgba(32,157,215,0.05)_55%,_transparent_70%)]" />
      <div className="pointer-events-none absolute bottom-0 right-0 h-[520px] w-[520px] translate-x-1/4 translate-y-1/4 rounded-full bg-[radial-gradient(circle,_rgba(117,57,145,0.18)_0%,_rgba(117,57,145,0.05)_55%,_transparent_75%)]" />

      <main className="relative mx-auto flex min-h-screen max-w-[1400px] flex-col gap-8 px-5 pb-12 pt-10">
        <header className="flex flex-col gap-5 rounded-[32px] border border-[var(--stroke)] bg-white/80 p-7 shadow-[var(--shadow)] backdrop-blur">
          <div className="flex flex-wrap items-start justify-between gap-6">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.35em] text-[var(--gray-text)]">
                Single Board Kanban
              </p>
              <h1 className="mt-3 font-display text-4xl font-semibold text-[var(--navy-dark)]">
                {board.title}
              </h1>
              <p className="mt-3 max-w-xl text-sm leading-6 text-[var(--gray-text)]">
                Keep momentum visible. Rename columns, drag cards between stages,
                and capture quick notes without getting buried in settings.
              </p>
              {isLoading ? (
                <p className="mt-4 text-sm font-medium text-[var(--primary-blue)]">
                  Loading board...
                </p>
              ) : null}
              {errorMessage ? (
                <p className="mt-4 text-sm font-medium text-[var(--secondary-purple)]">
                  {errorMessage}
                </p>
              ) : null}
            </div>
            <div className="rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] px-5 py-4">
              <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[var(--gray-text)]">
                Focus
              </p>
              <p className="mt-2 text-lg font-semibold text-[var(--primary-blue)]">
                One board. Five columns. Zero clutter.
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
        </header>

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
                        cards={column.cardIds.map((cardId) => board.cards[cardId])}
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
      </main>
    </div>
  );
};
