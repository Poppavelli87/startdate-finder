import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";
import * as XLSX from "xlsx";

test("settings controls remain interactive", async ({ page }) => {
  await page.goto("/startdate-finder/");

  const thresholdSlider = page.locator('input[type="range"]');
  await expect(thresholdSlider).toBeVisible();
  const initialSliderValue = await thresholdSlider.inputValue();
  await thresholdSlider.focus();
  await page.keyboard.press("ArrowRight");
  await expect
    .poll(async () => thresholdSlider.inputValue())
    .not.toBe(initialSliderValue);
  const updatedSliderValue = Number(await thresholdSlider.inputValue()).toFixed(
    2,
  );
  await expect(
    page.getByText(`High confidence threshold: ${updatedSliderValue}`),
  ).toBeVisible();

  const earliestKnownDateCheckbox = page.getByLabel(
    "Prefer earliest known date",
  );
  await expect(earliestKnownDateCheckbox).not.toBeChecked();
  await earliestKnownDateCheckbox.check();
  await expect(earliestKnownDateCheckbox).toBeChecked();
  await earliestKnownDateCheckbox.uncheck();
  await expect(earliestKnownDateCheckbox).not.toBeChecked();
});

test("start uses current settings values", async ({ page }) => {
  const currentDir = path.dirname(fileURLToPath(import.meta.url));
  const fixturePath = path.resolve(
    currentDir,
    "../../../backend/tests/fixtures/businesses_fixture.xlsx",
  );

  await page.route("**/api/config", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        defaults: {
          high_confidence_threshold: 0.85,
          prefer_earliest_known_date: false,
          enable_rdap_lookup: true,
          enable_whois_fallback: false,
          enable_social_hints: false,
          min_plausible_date: "1900-01-01",
          denylist_domains: ["example.com"],
        },
        whois_key_present: true,
        feature_social_hints_env: true,
      }),
    });
  });

  let capturedSettings: Record<string, unknown> | null = null;
  await page.route("**/api/jobs", async (route) => {
    const request = route.request();
    if (request.method() !== "POST") {
      await route.fallback();
      return;
    }

    const postData = request.postData() ?? "";
    const settingsJsonMatch = postData.match(
      /name="settings_json"\r?\n\r?\n([\s\S]*?)\r?\n--/,
    );
    expect(settingsJsonMatch).toBeTruthy();
    const settingsJsonValue = settingsJsonMatch?.[1] ?? "{}";
    capturedSettings = JSON.parse(settingsJsonValue) as Record<string, unknown>;

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ job_id: "job-123" }),
    });
  });

  await page.route("**/api/jobs/job-123/status", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        job_id: "job-123",
        status: "running",
        progress_done: 0,
        progress_total: 1,
        progress_pct: 0,
        message: "running",
        counts: {
          total_rows: 0,
          auto_matched: 0,
          needs_review: 0,
          not_found: 0,
          filled_via_domain: 0,
          filled_via_social: 0,
        },
        can_download: false,
      }),
    });
  });

  await page.route("**/api/jobs/job-123/events", async (route) => {
    await route.fulfill({
      status: 200,
      headers: {
        "Content-Type": "text/event-stream",
      },
      body: "",
    });
  });

  await page.goto("/startdate-finder/");

  const thresholdSlider = page.locator('input[type="range"]');
  await thresholdSlider.fill("0.91");
  await page.getByLabel("Prefer earliest known date").check();
  await page.getByLabel("Minimum plausible date").fill("1950-12-31");
  await page
    .getByLabel("Domain denylist (one domain per line)")
    .fill("foo.com\n BAR.org \n");

  await page.setInputFiles('input[type="file"]', fixturePath);
  await page.getByRole("button", { name: "Start Processing" }).click();

  await expect.poll(() => capturedSettings).not.toBeNull();
  expect(capturedSettings).toMatchObject({
    high_confidence_threshold: 0.91,
    prefer_earliest_known_date: true,
    min_plausible_date: "1950-12-31",
    denylist_domains: ["foo.com", "bar.org"],
  });
});
test("uploads, processes, and downloads enriched spreadsheet", async ({
  page,
}) => {
  const currentDir = path.dirname(fileURLToPath(import.meta.url));
  const fixturePath = path.resolve(
    currentDir,
    "../../../backend/tests/fixtures/businesses_fixture.xlsx",
  );
  expect(fs.existsSync(fixturePath)).toBeTruthy();

  await page.goto("/startdate-finder/");
  await page.setInputFiles('input[type="file"]', fixturePath);
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
