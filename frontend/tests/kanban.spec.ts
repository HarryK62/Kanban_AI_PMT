import { expect, test, type Page } from "@playwright/test";

const login = async (page: Page) => {
  await page.goto("/");
  await page.getByLabel("Username").fill("user");
  await page.getByLabel("Password").fill("password");
  await page.getByRole("button", { name: /sign in/i }).click();
};

test("requires login before showing the board", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: /sign in to open your board/i })
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Kanban Studio" })).not.toBeVisible();
});

test("loads the kanban board", async ({ page }) => {
  await login(page);
  await expect(page.getByRole("heading", { name: "Kanban Studio" })).toBeVisible();
  await expect(page.locator('[data-testid^="column-"]')).toHaveCount(5);
});

test("sends a chat request and reflects the returned board update", async ({ page }) => {
  await page.route("**/api/chat/user/messages", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        chat_id: 1,
        current_board_state_id: 2,
        assistant_message: {
          id: 2,
          sequence_number: 2,
          role: "assistant",
          content: "I renamed Backlog to Ideas.",
        },
        board: {
          version: 1,
          title: "Kanban Studio",
          columns: [
            { id: "col-backlog", title: "Ideas", cardIds: ["card-1", "card-2"] },
            { id: "col-discovery", title: "Discovery", cardIds: ["card-3"] },
            { id: "col-progress", title: "In Progress", cardIds: ["card-4", "card-5"] },
            { id: "col-review", title: "Review", cardIds: ["card-6"] },
            { id: "col-done", title: "Done", cardIds: ["card-7", "card-8"] },
          ],
          cards: {
            "card-1": {
              id: "card-1",
              title: "Align roadmap themes",
              details: "Draft quarterly themes with impact statements and metrics.",
            },
            "card-2": {
              id: "card-2",
              title: "Gather customer signals",
              details: "Review support tags, sales notes, and churn feedback.",
            },
            "card-3": {
              id: "card-3",
              title: "Prototype analytics view",
              details: "Sketch initial dashboard layout and key drill-downs.",
            },
            "card-4": {
              id: "card-4",
              title: "Refine status language",
              details: "Standardize column labels and tone across the board.",
            },
            "card-5": {
              id: "card-5",
              title: "Design card layout",
              details: "Add hierarchy and spacing for scanning dense lists.",
            },
            "card-6": {
              id: "card-6",
              title: "QA micro-interactions",
              details: "Verify hover, focus, and loading states.",
            },
            "card-7": {
              id: "card-7",
              title: "Ship marketing page",
              details: "Final copy approved and asset pack delivered.",
            },
            "card-8": {
              id: "card-8",
              title: "Close onboarding sprint",
              details: "Document release notes and share internally.",
            },
          },
        },
      }),
    });
  });

  await login(page);
  await page.getByLabel("Message").fill("Rename Backlog to Ideas.");
  await page.getByRole("button", { name: /send/i }).click();

  await expect(page.getByText("I renamed Backlog to Ideas.")).toBeVisible();
  await expect(page.getByText("Ideas")).toBeVisible();
});

test("adds a card to a column", async ({ page }) => {
  await login(page);
  const firstColumn = page.locator('[data-testid^="column-"]').first();
  await firstColumn.getByRole("button", { name: /add a card/i }).click();
  await firstColumn.getByPlaceholder("Card title").fill("Playwright card");
  await firstColumn.getByPlaceholder("Details").fill("Added via e2e.");
  await firstColumn.getByRole("button", { name: /add card/i }).click();
  await expect(firstColumn.getByText("Playwright card")).toBeVisible();
});

test("moves a card between columns", async ({ page }) => {
  await login(page);
  const card = page.getByTestId("card-card-1");
  const targetColumn = page.getByTestId("column-col-review");
  const cardBox = await card.boundingBox();
  const columnBox = await targetColumn.boundingBox();
  if (!cardBox || !columnBox) {
    throw new Error("Unable to resolve drag coordinates.");
  }

  await page.mouse.move(
    cardBox.x + cardBox.width / 2,
    cardBox.y + cardBox.height / 2
  );
  await page.mouse.down();
  await page.mouse.move(
    columnBox.x + columnBox.width / 2,
    columnBox.y + 120,
    { steps: 12 }
  );
  await page.mouse.up();
  await expect(targetColumn.getByTestId("card-card-1")).toBeVisible();
});

test("logs out back to the login screen", async ({ page }) => {
  await login(page);
  await page.locator('[data-testid^="column-"]').first().getByRole("button", {
    name: /add a card/i,
  }).click();
  await page.getByPlaceholder("Card title").fill("Session card");
  await page.getByPlaceholder("Details").fill("Persists in this tab.");
  await page.getByRole("button", { name: /add card/i }).click();
  await page.getByRole("button", { name: /log out/i }).click();

  await expect(
    page.getByRole("heading", { name: /sign in to open your board/i })
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Kanban Studio" })).not.toBeVisible();

  await page.getByLabel("Username").fill("user");
  await page.getByLabel("Password").fill("password");
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page.getByText("Session card")).toBeVisible();
});

test("loads the persisted board in a new window", async ({ browser, page }) => {
  await login(page);
  const firstColumn = page.locator('[data-testid^="column-"]').first();
  await firstColumn.getByRole("button", { name: /add a card/i }).click();
  await firstColumn.getByPlaceholder("Card title").fill("Tab-only card");
  await firstColumn.getByPlaceholder("Details").fill("Should not appear elsewhere.");
  await firstColumn.getByRole("button", { name: /add card/i }).click();
  await expect(page.getByText("Tab-only card")).toBeVisible();

  const secondPage = await browser.newPage();
  await secondPage.goto("/");
  await expect(
    secondPage.getByRole("heading", { name: /sign in to open your board/i })
  ).toBeVisible();
  await secondPage.getByLabel("Username").fill("user");
  await secondPage.getByLabel("Password").fill("password");
  await secondPage.getByRole("button", { name: /sign in/i }).click();
  await expect(secondPage.getByText("Tab-only card")).toBeVisible();
  await secondPage.close();
});
