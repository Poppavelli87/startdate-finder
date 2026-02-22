import { mkdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

const distDir = resolve(process.cwd(), "dist");
const markerPath = resolve(distDir, ".nojekyll");

mkdirSync(distDir, { recursive: true });
writeFileSync(markerPath, "", { encoding: "utf8" });
console.log(`Created ${markerPath}`);
