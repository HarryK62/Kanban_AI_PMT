# Code Review

Reviewed: 2026-03-24
Scope: full repository — `backend/`, `frontend/`, `docs/`

---

## Summary

The codebase is well-structured for an MVP. The domain model is clear, the persistence design is sound, and the test coverage is solid. The findings below are ranked by impact. Items 1–4 are bugs or correctness issues that should be addressed before continued feature work.

---

## High priority

### 1. `repository.initialize()` is called on every repository method

**File:** `backend/app/repository.py`

Every public method on `BoardRepository` (`get_or_create_board`, `replace_board`, `list_chat_history`, `append_chat_message`, `reset_chat_session`, etc.) calls `self.initialize()`, which re-runs all five `CREATE TABLE IF NOT EXISTS` statements plus two `CREATE UNIQUE INDEX` statements on every API request.

This is wasteful and makes every request pay the DDL overhead. It also means the initialization logic is interleaved with data access methods rather than being a clear startup step.

**Action:** Call `repository.initialize()` once in `create_app` immediately after constructing `BoardRepository`, and remove it from all individual methods.

---

### 2. User message is persisted before the AI call succeeds

**Files:** `backend/app/main.py:181–203`, `backend/tests/test_main.py:373–383`

In `create_chat_message`, the user message is inserted into `chat_messages` before `client.complete_messages` is called. If the AI returns malformed JSON or an invalid board, the route returns 502 — but the user message stays in the database as an unanswered turn. The test at line 373 explicitly confirms this:

```python
assert chat_messages == [(1, "user", "Do something.", 1)]
```

On the user's next message, `list_chat_history` returns this unanswered user turn to the AI as context, which is misleading and may degrade model behavior.

**Action:** Either move user message persistence to after a successful AI response (only persist both messages together), or delete the user message row in the error path before returning 502. The simplest fix is to insert both the user message and the assistant message in a single transaction only after the AI call succeeds.

---

### 3. Column rename fires a PUT request per keystroke

**File:** `frontend/src/components/KanbanBoard.tsx:172–179`

`handleRenameColumn` is called on every `onChange` event of the column title input, which calls `updateBoard`, which immediately calls `persistBoard`. Typing "New Name" (8 characters) after clearing fires 9 consecutive PUT requests. The integration test documents this directly:

```ts
await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(10));
```

This creates a burst of concurrent PUT requests, and because `persistBoard` fires with `void` (no sequencing), an earlier response can overwrite a later one in `setBoard(data.board)`, producing stale board state in the UI.

**Action:** Debounce `persistBoard` calls (e.g., 300 ms) or save on blur. Update the test assertion to check call behavior rather than an exact count, which is brittle.

---

### 4. Concurrent board saves can silently overwrite each other

**File:** `frontend/src/components/KanbanBoard.tsx:146–152`

`updateBoard` fires `persistBoard(nextBoard)` with `void` and catches only the error. There is no locking, cancellation, or sequencing. Two rapid edits will fire two concurrent PUT requests; whichever response arrives last will call `setBoard(data.board)`, potentially reverting the first change visually (even though the second PUT correctly persists it).

The more dangerous case: after the AI chat route responds with a board update and `setBoard(data.board)` is called at line 239, a prior `persistBoard` for a user action that was still in-flight may resolve afterwards and overwrite the AI board in state.

**Action:** Track a generation counter (or abort pending fetch with `AbortController`) so that stale save responses are discarded. This resolves both the rename-per-keystroke problem and the AI-update-overwrite problem together.

---

## Medium priority

### 5. `OpenRouterClient` raises `HTTPException` from a non-HTTP module

**File:** `backend/app/ai.py:31–35, 61–66, 71–73`

`OpenRouterClient` raises `fastapi.HTTPException` directly. This couples infrastructure code (the HTTP client for OpenRouter) to the FastAPI request model. Consequences:

- `test_ai.py` has to import and assert against `HTTPException`, coupling the unit test to FastAPI internals.
- The client cannot be used or tested outside of a FastAPI request context without pulling in the framework.

**Action:** Raise plain Python exceptions (`ValueError` for missing config, `RuntimeError` or a custom exception for upstream failures) and translate them to `HTTPException` at the route level in `main.py`.

---

### 6. `except Exception` is too broad in the chat message route

**File:** `backend/app/main.py:198–203`

```python
try:
    structured_reply = AiStructuredReply.model_validate_json(raw_reply)
except Exception:
    raise HTTPException(status_code=502, detail="AI response was malformed.") from None
```

`except Exception` swallows all exceptions, including programming errors in the validation logic itself. A `TypeError` or `AttributeError` from a code bug would silently produce a 502 with a misleading error message.

**Action:** Catch `pydantic.ValidationError` and `json.JSONDecodeError` specifically.

---

### 7. `anyio` is not declared as a dev dependency

**File:** `backend/pyproject.toml`

`backend/tests/test_ai.py` uses `@pytest.mark.anyio` (lines 15, 39, 50), which requires `anyio` and its pytest plugin. Currently `anyio` is available only because it is a transitive dependency of `httpx`/`starlette`. Transitive deps can disappear when direct dependencies are upgraded.

**Action:** Add `anyio[trio]` or `pytest-anyio` to the `[dependency-groups] dev` section in `pyproject.toml`. Also add `asyncio_mode = "auto"` (or equivalent `anyio` configuration) to `[tool.pytest.ini_options]` so the mode is explicit.

---

### 8. `get_or_create_chat` and `_get_or_create_chat_id` are near-duplicates

**File:** `backend/app/repository.py:302–331, 420–446`

Both methods find-or-create a chat for a user with nearly identical logic. `get_or_create_chat` is a public method but is never called from `main.py`; all internal callers use `_get_or_create_chat_id`. The duplication means a bug in one is unlikely to be fixed in the other.

**Action:** Remove `get_or_create_chat` (it is dead code) and rename `_get_or_create_chat_id` if it needs to be called from outside. Or keep one and delegate the other to it.

---

### 9. Local imports inside frequently called methods

**Files:** `backend/app/repository.py:299`, `backend/app/ai.py:107`

`_deserialize_board` has `import json` inside the method body. `json_dumps` has `import json` inside its body. Both are called on every board operation or AI message build. Python caches module imports after the first call, so there is no real runtime penalty, but it is inconsistent with the rest of the codebase and obscures dependencies.

**Action:** Move `import json` to the module level in both files.

---

## Low priority

### 10. `DATABASE.md` schema diverges from the implementation

**File:** `docs/DATABASE.md:43`

The design doc shows:

```sql
current_board_state_id INTEGER NOT NULL UNIQUE
```

The actual DDL in `repository.py:106` declares it nullable:

```sql
current_board_state_id INTEGER UNIQUE,
```

The implementation is correct (NULL is needed during the two-step board bootstrap), but the doc is misleading to anyone reading the design.

**Action:** Update `DATABASE.md` to show `current_board_state_id INTEGER UNIQUE` and note that it is set to NULL on initial insert, then updated immediately after the first board state is written.

---

### 11. `ChatMessage` type is defined twice

**Files:** `frontend/src/components/KanbanBoard.tsx:42–46`, `frontend/src/components/AiChatSidebar.tsx:11–15`

Identical type definition:

```ts
type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
};
```

**Action:** Extract to `frontend/src/lib/types.ts` (or co-locate with `kanban.ts`) and import in both components.

---

### 12. `UNIQUE INDEX idx_boards_current_board_state_id` is redundant

**File:** `backend/app/repository.py:150–156`

The partial unique index (`WHERE current_board_state_id IS NOT NULL`) is created in addition to the `UNIQUE` column constraint declared in the `CREATE TABLE` statement. SQLite already permits multiple NULLs in a UNIQUE column constraint; the partial index adds nothing.

**Action:** Remove the `CREATE UNIQUE INDEX` for `idx_boards_current_board_state_id`. The column-level `UNIQUE` constraint is sufficient.

---

### 13. No visual feedback during board save operations

**File:** `frontend/src/components/KanbanBoard.tsx`

Board loads show "Loading board..." (`isLoading`), but card adds, deletes, renames, and drag-drops show no in-progress indicator. Errors are shown only on failure. For the MVP this is acceptable, but users have no confirmation that their change was actually saved.

**Action:** Track a `isSaving` state and show a brief save indicator in the header, or at minimum ensure the error message is prominent enough. This is a UX concern, not a bug.

---

### 14. `board.cards[cardId]` can return `undefined` in the render path

**File:** `frontend/src/components/KanbanBoard.tsx:330`

```ts
cards={column.cardIds.map((cardId) => board.cards[cardId])}
```

If `column.cardIds` contains an ID not present in `board.cards`, this produces an `undefined` entry in the `cards` array passed to `KanbanColumn`, which would crash rendering. The backend validates board consistency before persisting, so this is unlikely in practice. But if a locally constructed board (e.g., from a failed AI update path) ever reaches this render, there is no guard.

**Action:** Either add a filter (`board.cards[cardId]` !== undefined) or rely on TypeScript strict mode to surface the type mismatch — currently `KanbanColumn` expects `Card[]`, not `(Card | undefined)[]`.

---

### 15. Playwright test inlines a full board JSON payload

**File:** `frontend/tests/kanban.spec.ts:28–93`

The test for "sends a chat request" inlines all eight cards verbatim (~65 lines) to construct the mock response. A helper that returns the default board with a targeted override would be shorter and easier to maintain.

**Action:** Extract a `defaultBoard(overrides?)` helper in a `tests/helpers.ts` file and use it in the mock. This keeps individual test cases focused on what they are actually testing.

---

## Test coverage gaps

The following scenarios are not currently covered by automated tests:

- **Backend:** What happens when `append_chat_message` is called and the `chat_id` does not exist in the `chats` table (defensive path in `_get_or_create_chat_id`).
- **Backend:** `replace_board` when called for a user who has no board yet (the `existing_board is None` branch at `repository.py:180`).
- **Frontend:** Chat error state (`chatErrorMessage`) renders in the sidebar.
- **Frontend:** Optimistic board update is preserved on `persistBoard` success (currently only failure is observed via error message).

These are low-priority for an MVP but worth noting as the feature set grows.
