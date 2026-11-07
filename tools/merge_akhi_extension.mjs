/* Copyright (c) 2026 the AkhiBrowser authors. All rights reserved.
 * See LICENSE in the root of this repository. */

import { cpSync, existsSync, readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { execFileSync } from "node:child_process";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../../../..");
const extension = join(root, "browser", "extensions", "akhi");
const premium = join(root, "browser", "extensions", "akhi-premium");
const target = resolve(process.argv[2] ?? "");
const require = createRequire(join(extension, "webext", "package.json"));
const { minify } = require("terser");

if (!process.argv[2]) {
  throw new Error("Usage: node merge_akhi_extension.mjs <target>");
}

execFileSync(process.execPath, [join(extension, "webext", "minify.mjs"), target], {
  cwd: root,
  stdio: "inherit",
});

for (const path of [
  "content/feeds.js",
  "lib/family.js",
  "lib/premium.js",
  "pages/settings_premium.js",
  "faces",
  "gender",
  "body",
]) {
  const source = join(premium, path);
  if (!existsSync(source)) {
    throw new Error(`Missing Premium source: ${path}`);
  }
  cpSync(source, join(target, path), { recursive: true, force: true });
}

const premiumClassifier = join(premium, "lib", "premium_image_classifier.js");
if (!existsSync(premiumClassifier)) {
  throw new Error("Missing Premium image classifier");
}
cpSync(premiumClassifier, join(target, "lib", "image_classifier.js"));

for (const path of [
  "content/feeds.js",
  "lib/family.js",
  "lib/premium.js",
  "lib/image_classifier.js",
  "pages/settings_premium.js",
]) {
  const destination = join(target, path);
  const result = await minify(readFileSync(destination, "utf8"), {
    compress: { passes: 2 },
    mangle: true,
    format: { comments: /Copyright/ },
  });
  if (!result.code) {
    throw new Error(`Couldn't minify Premium source: ${path}`);
  }
  writeFileSync(destination, result.code);
}
