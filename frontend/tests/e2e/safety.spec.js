import { expect, test } from "@playwright/test";

async function sendMessage(page, text) {
  await page.getByLabel("Tell us how we can help").fill(text);
  await page.getByRole("button", { name: "Send" }).click();
}

test("assistant blocks medical advice requests without advancing intake", async ({ page }) => {
  await page.goto("/");

  await sendMessage(page, "what medication should I take?");

  const lastAssistantMessage = page.locator(".assistant-message p").last();
  await expect(lastAssistantMessage).toContainText(/cannot provide medical advice/i);
  await expect(lastAssistantMessage).not.toContainText(/what is your last name/i);
  await expect(page.getByText(/what is your first name/i)).toBeVisible();
});

test("assistant blocks emergency language with urgent guidance", async ({ page }) => {
  await page.goto("/");

  await sendMessage(page, "i think i am having a heart attack");

  const lastAssistantMessage = page.locator(".assistant-message p").last();
  await expect(lastAssistantMessage).toContainText(/call emergency services/i);
  await expect(page.getByText(/what is your first name/i)).toBeVisible();
});
