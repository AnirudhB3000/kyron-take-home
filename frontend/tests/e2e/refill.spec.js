import { expect, test } from "@playwright/test";

async function sendMessage(page, text) {
  await page.getByLabel("Tell us how we can help").fill(text);
  await page.getByRole("button", { name: "Send" }).click();
}

test("assistant handles refill requests without derailing intake", async ({ page }) => {
  await page.goto("/");

  await sendMessage(page, "I need a refill for my inhaler");

  const lastAssistantMessage = page.locator(".assistant-message p").last();
  await expect(lastAssistantMessage).toContainText(/cannot verify live refill status/i);
  await expect(lastAssistantMessage).toContainText(/what is your first name/i);
});
