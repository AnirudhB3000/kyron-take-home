import { expect, test } from "@playwright/test";

async function sendMessage(page, text) {
  await page.getByLabel("Tell us how we can help").fill(text);
  await page.getByRole("button", { name: "Send" }).click();
}

test("patient can prepare a voice handoff after phone collection", async ({ page }) => {
  await page.goto("/");

  const phoneButton = page.getByRole("button", { name: /continue by phone/i });
  await expect(phoneButton).toBeDisabled();

  await sendMessage(page, "Taylor");
  await sendMessage(page, "Morgan");
  await sendMessage(page, "1990-06-15");
  await sendMessage(page, "555-123-4567");

  await expect(phoneButton).toBeEnabled();
  await phoneButton.click();

  await expect(page.getByText(/ready to continue by phone/i)).toBeVisible();
  await expect(page.getByText(/would call 555-123-4567/i)).toBeVisible();
});
