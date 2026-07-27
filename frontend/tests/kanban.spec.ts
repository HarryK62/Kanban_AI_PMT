import { expect, test, type Page } from "@playwright/test";
import { defaultBoard } from "./helpers";

const login = async (page: Page) => {
  await page.goto("/");
  await page.getByLabel("Username").fill("harry");
  await page.getByLabel("Password").fill("kijanka");
  await page.getByRole("button", { name: /sign in/i }).click();
};

const signupAndLogin = async (
  page: Page,
  username: string,
  password: string
) => {
  await page.goto("/");
  await page.getByRole("button", { name: /new here\? sign up/i }).click();
  await page.getByLabel("Username").fill(username);
  await page.getByLabel(/^Password$/).fill(password);
  await page.getByLabel("Confirm Password").fill(password);
  await page.getByRole("button", { name: /create account/i }).click();
  await expect(page.getByRole("status")).toContainText("Account created");
  await page.getByLabel(/^Password$/).fill(password);
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

test("allows signup and sign in for a new user", async ({ page }) => {
  const username = `newuser${Date.now()}`;
  const password = "StrongPass1!";
  await signupAndLogin(page, username, password);

  await expect(page.getByRole("heading", { name: "Kanban Studio" })).toBeVisible();
  await expect(page.locator('[data-testid^="column-"]')).toHaveCount(5);
});

test("sends a chat request and reflects the returned board update", async ({ page }) => {
  const board = defaultBoard();
  board.columns[0] = { ...board.columns[0], title: "Ideas" };

  await page.route("**/api/chat/harry/messages", async (route) => {
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
        board,
      }),
    });
  });

  await login(page);
  await page.getByLabel("Message").fill("Rename Backlog to Ideas.");
  await page.getByRole("button", { name: /send/i }).click();

  await expect(page.getByText("I renamed Backlog to Ideas.")).toBeVisible();
  await expect(
    page.getByTestId("column-col-backlog").getByLabel("Column title")
  ).toHaveValue("Ideas");
});

test("adds a card to a column", async ({ page }) => {
  await login(page);
  const firstColumn = page.locator('[data-testid^="column-"]').first();
  await firstColumn.getByRole("button", { name: /add a card/i }).click();
  await firstColumn.getByPlaceholder("Card title").fill("Playwright card");
  await firstColumn.getByPlaceholder("Details").fill("Added via e2e.");
  await firstColumn.getByRole("button", { name: /add card/i }).click();
  await expect(
    firstColumn.getByRole("heading", { name: "Playwright card" }).first()
  ).toBeVisible();
});

test("moves a card between columns", async ({ page }) => {
  await login(page);
  const sourceColumn = page.locator('[data-testid^="column-"]').first();
  const card = sourceColumn.locator('[data-testid^="card-"]').first();
  const targetColumn = page.getByTestId("column-col-review");
  const cardTestId = await card.getAttribute("data-testid");
  if (!cardTestId) {
    throw new Error("Unable to resolve source card id.");
  }

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
  await expect(targetColumn.locator(`[data-testid="${cardTestId}"]`)).toBeVisible();
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

  await page.getByLabel("Username").fill("harry");
  await page.getByLabel("Password").fill("kijanka");
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page.getByRole("heading", { name: "Session card" }).first()).toBeVisible();
});

test("loads the persisted board in a new window", async ({ browser, page }) => {
  await login(page);
  const firstColumn = page.locator('[data-testid^="column-"]').first();
  await firstColumn.getByRole("button", { name: /add a card/i }).click();
  await firstColumn.getByPlaceholder("Card title").fill("Tab-only card");
  await firstColumn.getByPlaceholder("Details").fill("Should not appear elsewhere.");
  await firstColumn.getByRole("button", { name: /add card/i }).click();
  await expect(page.getByRole("heading", { name: "Tab-only card" }).first()).toBeVisible();

  const secondPage = await browser.newPage();
  await secondPage.goto("/");
  await expect(
    secondPage.getByRole("heading", { name: /sign in to open your board/i })
  ).toBeVisible();
  await secondPage.getByLabel("Username").fill("harry");
  await secondPage.getByLabel("Password").fill("kijanka");
  await secondPage.getByRole("button", { name: /sign in/i }).click();
  await expect(secondPage.getByRole("heading", { name: "Tab-only card" }).first()).toBeVisible();
  await secondPage.close();
});
