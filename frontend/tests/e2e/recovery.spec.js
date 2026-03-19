import { expect, test } from "@playwright/test";

async function sendMessage(page, text) {
  await page.getByLabel("Tell us how we can help").fill(text);
  await page.getByRole("button", { name: "Send" }).click();
}

test("patient can recover from an unsupported concern to a successful booking path", async ({ page }) => {
  await page.goto("/");

  await sendMessage(page, "Taylor");
  await sendMessage(page, "Morgan");
  await sendMessage(page, "1990-06-15");
  await sendMessage(page, "555-123-4567");
  await sendMessage(page, "taylor@example.com");

  await sendMessage(page, "stomach pain");
  await expect(page.getByText(/could not match that concern/i)).toBeVisible();
  await expect(page.getByText(/describe the body part or issue in different words/i)).toBeVisible();

  await sendMessage(page, "knee pain");
  await expect(page.getByText(/matched you with dr\. olivia bennett/i)).toBeVisible();
  await expect(page.locator(".slot-card")).toHaveCount(6);
});
