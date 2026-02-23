import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";
import * as XLSX from "xlsx";

function fixturePath(): string {
  const currentDir = path.dirname(fileURLToPath(import.meta.url));
  return path.resolve(currentDir, "../../../backend/tests/fixtures/businesses_fixture.xlsx");
}

function extractSettingsJsonFromMultipart(body: string): Record<string, unknown> {
  const match = body.match(/name="settings_json"\r?\n\r?\n([\s\S]*?)\r?\n--/);
  if (!match) {
    throw new Error("settings_json field not found in multipart form body");
  }
  return JSON.parse(match[1].trim()) as Record<string, unknown>;
}

test("settings controls remain interactive", async ({ page }) => {
  await page.goto("/startdate-finder/");

  const thresholdSlider = page.locator('input[type="range"]');
  await expect(thresholdSlider).toBeVisible();
  const initialSliderValue = await thresholdSlider.inputValue();
  await thresholdSlider.click();
  await thresholdSlider.press("ArrowRight");
  await expect.poll(async () => thresholdSlider.inputValue()).not.toBe(initialSliderValue);
  const updatedSliderValue = Number(await thresholdSlider.inputValue()).toFixed(2);
  await expect(page.getByText(`High confidence threshold: ${updatedSliderValue}`)).toBeVisible();

  const earliestKnownDateCheckbox = page.getByLabel(
    "Prefer earliest known date",
  );
  await expect(earliestKnownDateCheckbox).not.toBeChecked();
  await earliestKnownDateCheckbox.check();
  await expect(earliestKnownDateCheckbox).toBeChecked();
  await earliestKnownDateCheckbox.uncheck();
  await expect(earliestKnownDateCheckbox).not.toBeChecked();
});

test("submits normalized settings_json payload from current UI state", async ({ page }) => {
  const xlsxFixture = fixturePath();
  expect(fs.existsSync(xlsxFixture)).toBeTruthy();

  let submittedSettings: Record<string, unknown> | null = null;

  await page.route("**/api/jobs", async (route, request) => {
    const multipartBody = request.postDataBuffer()?.toString("utf8") || "";
    submittedSettings = extractSettingsJsonFromMultipart(multipartBody);
    await route.fulfill({
      status: 400,
      contentType: "text/plain",
      body: "intentional test response"
    });
  });

  await page.goto("/startdate-finder/");

  const startButton = page.getByRole("button", { name: "Start Processing" });
  await expect(startButton).toBeDisabled();

  await page.setInputFiles('input[type="file"]', xlsxFixture);
  await expect(startButton).toBeEnabled();

  const thresholdSlider = page.locator('input[type="range"]');
  const initialSliderValue = await thresholdSlider.inputValue();
  await thresholdSlider.click();
  await thresholdSlider.press("ArrowRight");
  await expect.poll(async () => thresholdSlider.inputValue()).not.toBe(initialSliderValue);
  const updatedSliderValue = Number(await thresholdSlider.inputValue()).toFixed(2);
  await expect(page.getByText(`High confidence threshold: ${updatedSliderValue}`)).toBeVisible();

  const rdapCheckbox = page.getByLabel("Enable RDAP lookup");
  await expect(rdapCheckbox).toBeChecked();
  await rdapCheckbox.uncheck();
  await expect(rdapCheckbox).not.toBeChecked();

  await page.getByLabel("Prefer earliest known date").check();
  await page.getByLabel("Minimum plausible date").fill("2024-05-06");
  await page.getByLabel("Domain denylist (one domain per line)").fill("foo.com\n BAR.org \n");

  await startButton.click();

  await expect.poll(() => submittedSettings).not.toBeNull();
  expect(submittedSettings).not.toBeNull();

  const settings = submittedSettings as Record<string, unknown>;
  expect(settings.high_confidence_threshold).toBeCloseTo(Number(updatedSliderValue), 5);
  expect(settings.prefer_earliest_known_date).toBe(true);
  expect(settings.enable_rdap_lookup).toBe(false);
  expect(settings.min_plausible_date).toBe("2024-05-06");
  expect(settings.denylist_domains).toEqual(["foo.com", "bar.org"]);
});

test("uploads, processes, and downloads enriched spreadsheet", async ({ page }) => {
  const xlsxFixture = fixturePath();
  expect(fs.existsSync(xlsxFixture)).toBeTruthy();

  await page.goto("/startdate-finder/");
  await page.setInputFiles('input[type="file"]', xlsxFixture);
  await page.getByRole("button", { name: "Start Processing" }).click();

  await expect(
    page.getByRole("link", { name: "Download Enriched Excel" }),
  ).toBeVisible({
    timeout: 90000,
  });

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download Enriched Excel" }).click();
  const download = await downloadPromise;
  const outputPath = path.join(
    test.info().outputDir,
    download.suggestedFilename(),
  );
  await download.saveAs(outputPath);
  expect(fs.existsSync(outputPath)).toBeTruthy();

  const workbook = XLSX.read(fs.readFileSync(outputPath), { type: "buffer" });
  const sheet = workbook.Sheets[workbook.SheetNames[0]];
  const rows = XLSX.utils.sheet_to_json<Record<string, string>>(sheet, {
    defval: "",
  });
  const knownRow = rows.find((row) =>
    String(row["Business"]).toLowerCase().includes("acme"),
  );
  expect(knownRow).toBeTruthy();
  expect(
    String(knownRow?.["Date Established"] ?? "").trim().length,
  ).toBeGreaterThan(0);
});
