import { expect, test } from "@playwright/test";

async function sendMessage(page, text) {
  await page.getByLabel("Tell us how we can help").fill(text);
  await page.getByRole("button", { name: "Send" }).click();
}

test("patient can refine availability by weekday", async ({ page }) => {
  await page.goto("/");

  await sendMessage(page, "Taylor");
  await sendMessage(page, "Morgan");
  await sendMessage(page, "1990-06-15");
  await sendMessage(page, "555-123-4567");
  await sendMessage(page, "taylor@example.com");
  await sendMessage(page, "knee pain");

  await expect(page.locator(".assistant-message p").last()).toContainText(/matched you with dr\. olivia bennett/i);

  await sendMessage(page, "Do you have something on Tuesday?");
  await expect(page.locator(".assistant-message p").last()).toContainText(/available tuesday appointments/i);

  const slotTexts = await page.locator(".slot-card").allTextContents();
  expect(slotTexts.length).toBeGreaterThan(0);
  for (const text of slotTexts) {
    expect(text.toLowerCase()).toContain("tuesday");
  }
});
