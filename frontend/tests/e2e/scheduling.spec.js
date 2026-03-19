import { expect, test } from "@playwright/test";

async function sendMessage(page, text) {
  await page.getByLabel("Tell us how we can help").fill(text);
  await page.getByRole("button", { name: "Send" }).click();
}

test("patient can complete scheduling and recover from invalid DOB input", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByText("AI concierge for modern patient access")).toBeVisible();
  await expect(page.locator(".assistant-message p").last()).toContainText(/what is your first name/i);

  await sendMessage(page, "Taylor");
  await expect(page.locator(".assistant-message p").last()).toContainText(/what is your last name/i);

  await sendMessage(page, "Morgan");
  await expect(page.locator(".assistant-message p").last()).toContainText(/what is your date of birth/i);

  await sendMessage(page, "not-a-date");
  await expect(page.locator(".assistant-message p").last()).toContainText(/date of birth is not valid/i);

  await sendMessage(page, "1990-06-15");
  await expect(page.locator(".assistant-message p").last()).toContainText(/phone number/i);

  await sendMessage(page, "555-123-4567");
  await expect(page.locator(".assistant-message p").last()).toContainText(/email address/i);

  await sendMessage(page, "taylor@example.com");
  await expect(page.locator(".assistant-message p").last()).toContainText(/body part or issue/i);

  await sendMessage(page, "knee pain");
  await expect(page.locator(".assistant-message p").last()).toContainText(/matched you with dr\. olivia bennett/i);
  await expect(page.getByRole("button", { name: /continue by phone/i })).toBeEnabled();

  const firstSlot = page.locator(".slot-card").first();
  await expect(firstSlot).toBeVisible();
  await firstSlot.click();

  await expect(page.locator(".assistant-message p").last()).toContainText(/reply yes to confirm/i);
  await sendMessage(page, "yes");

  await expect(page.locator(".assistant-message p").last()).toContainText(/appointment has been booked successfully/i);
});


test("assistant answers a clarification question during intake", async ({ page }) => {
  await page.goto("/");

  await sendMessage(page, "what is this site?");

  const lastAssistantMessage = page.locator(".assistant-message p").last();
  await expect(lastAssistantMessage).toContainText(/virtual scheduling assistant/i);
  await expect(lastAssistantMessage).toContainText(/what is your first name/i);
});
