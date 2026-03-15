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

test("opens a fresh board in a new window", async ({ browser, page }) => {
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
  await expect(secondPage.getByText("Tab-only card")).toHaveCount(0);
  await secondPage.close();
});
