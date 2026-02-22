import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";
import * as XLSX from "xlsx";

test("uploads, processes, and downloads enriched spreadsheet", async ({ page }) => {
  const currentDir = path.dirname(fileURLToPath(import.meta.url));
  const fixturePath = path.resolve(
    currentDir,
    "../../../backend/tests/fixtures/businesses_fixture.xlsx"
  );
  expect(fs.existsSync(fixturePath)).toBeTruthy();

  await page.goto("/startdate-finder/");
  await page.setInputFiles('input[type="file"]', fixturePath);
  await page.getByRole("button", { name: "Start Processing" }).click();

  await expect(page.getByRole("link", { name: "Download Enriched Excel" })).toBeVisible({
    timeout: 90000
  });

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download Enriched Excel" }).click();
  const download = await downloadPromise;
  const outputPath = path.join(test.info().outputDir, download.suggestedFilename());
  await download.saveAs(outputPath);
  expect(fs.existsSync(outputPath)).toBeTruthy();

  const workbook = XLSX.read(fs.readFileSync(outputPath), { type: "buffer" });
  const sheet = workbook.Sheets[workbook.SheetNames[0]];
  const rows = XLSX.utils.sheet_to_json<Record<string, string>>(sheet, { defval: "" });
  const knownRow = rows.find((row) => String(row["Business"]).toLowerCase().includes("acme"));
  expect(knownRow).toBeTruthy();
  expect(String(knownRow?.["Date Established"] ?? "").trim().length).toBeGreaterThan(0);
});
