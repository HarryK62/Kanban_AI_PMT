# Frontend Agent Notes

This file describes the current frontend codebase in `frontend/` so future work starts from the actual implementation that exists today.

## Current state

- This is a standalone Next.js app using the App Router.
- It can be built as a static export for FastAPI to serve.
- It is still developed as a standalone frontend app locally.
- The root page renders a frontend-only login gate before the board.
- Board state is loaded from and saved to the backend board API.
- The UI already follows the project color palette and uses local font stacks.

## Tooling

- Framework: Next.js 16
- React: 19
- Styling: Tailwind CSS v4 plus CSS variables in `src/app/globals.css`
- Drag and drop: `@dnd-kit/core` and `@dnd-kit/sortable`
- Unit/component tests: Vitest + Testing Library
- End-to-end tests: Playwright
- Production build: static export via `next build --webpack`

## Important files

- `src/app/page.tsx`
  - Renders the `AppShell` component at `/`.
- `src/app/layout.tsx`
  - Defines page metadata.
- `src/app/globals.css`
  - Defines project color tokens and global styles.
- `src/components/AppShell.tsx`
  - Owns the frontend-only login flow.
  - Validates the hardcoded `user` / `password` credentials.
  - Stores login visibility in React state only.
  - Switches between the login UI and `KanbanBoard`.
- `src/components/KanbanBoard.tsx`
  - Main client component.
  - Loads the board from the backend on mount.
  - Persists board updates back to the backend API.
  - Handles drag start/end, column rename, add card, and delete card.
  - Accepts an optional logout action for the current phase.
- `src/components/KanbanColumn.tsx`
  - Renders a single column.
  - Supports inline column renaming.
  - Configures the droppable area and card list.
- `src/components/KanbanCard.tsx`
  - Renders a draggable card and delete action.
- `src/components/KanbanCardPreview.tsx`
  - Renders the drag overlay preview.
- `src/components/NewCardForm.tsx`
  - Handles add-card form open/close and submission.
- `src/lib/kanban.ts`
  - Defines `Card`, `Column`, and `BoardData`.
  - Contains the demo board seed data.
  - Contains card move logic and id generation.
- `src/components/KanbanBoard.test.tsx`
  - Covers rendering, renaming a column, and adding/removing a card.
- `src/components/AppShell.test.tsx`
  - Covers login gating, valid credentials, invalid credentials, and logout.
- `src/lib/kanban.test.ts`
  - Covers board utility logic.
- `tests/kanban.spec.ts`
  - Covers login gating, page load after login, add-card, drag-and-drop, and logout in Playwright.

## Current board model

The current frontend data shape is:

```ts
type Card = {
  id: string;
  title: string;
  details: string;
};

type Column = {
  id: string;
  title: string;
  cardIds: string[];
};

type BoardData = {
  version: number;
  title: string;
  columns: Column[];
  cards: Record<string, Card>;
};
```

This shape should be treated as the baseline for backend persistence unless there is a deliberate migration.

## Current behavior

- The user must sign in with `user` / `password` before seeing the board.
- Login state is stored only in memory, so a new window or refresh returns to the login screen.
- The user can log out and return to the login screen.
- Board changes persist through the backend API.
- A new window shows the same saved board after login.
- The board has five columns seeded from `initialData`.
- Column titles are editable inline.
- Cards can be dragged within a column or across columns.
- Cards can be added from the bottom of each column.
- Cards can be removed from a column.
- There is no AI chat UI yet.

## Constraints for future changes

- Keep the existing visual language unless the task explicitly changes it.
- Keep the board interactions simple; do not add extra product features outside the requested scope.
- Prefer extending the existing board model instead of replacing it.
- Preserve the current board behavior while using the backend as the source of truth.
- If the persisted board schema changes, update tests and docs in the same task.

## Run and test

From `frontend/`:

```bash
npm install
npm run dev
npm run test:unit
npm run test:e2e
npm run test:e2e:integration
```

## Notes for later phases

- Parts 7 to 10 should continue to use the current board shape unless an approved schema change is made.
