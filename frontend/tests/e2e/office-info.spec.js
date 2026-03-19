import { expect, test } from "@playwright/test";

async function sendMessage(page, text) {
  await page.getByLabel("Tell us how we can help").fill(text);
  await page.getByRole("button", { name: "Send" }).click();
}

test("assistant answers office info questions without derailing intake", async ({ page }) => {
  await page.goto("/");

  await sendMessage(page, "What are your office hours?");
  const lastAssistantMessage = page.locator(".assistant-message p").last();
  await expect(lastAssistantMessage).toContainText(/Monday to Thursday/i);
  await expect(lastAssistantMessage).toContainText(/what is your first name/i);

  await sendMessage(page, "What is your address?");
  const addressAssistantMessage = page.locator(".assistant-message p").last();
  await expect(addressAssistantMessage).toContainText(/1450 Market Street/i);
  await expect(addressAssistantMessage).toContainText(/what is your first name/i);
});
