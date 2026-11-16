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
  "content/yt_clean.js",
  "content/yt_clean.css",
  "content/hide_comments.js",
  "content/hide_comments.css",
  "content/profanity_mask.js",
  "content/strict_mode.js",
  "content/akhi_notice.js",
  "content/riba_warning.js",
  "content/halal_check.js",
  "content/quran_follow.js",
  "content/trusted_sources.js",
  "content/halal_places.js",
  "content/deen_time.js",
  "content/word_block.js",
  "lib/family_controls.js",
  "lib/parent_report.js",
  "lib/family.js",
  "lib/premium.js",
  "lib/prayer_pause.js",
  "pages/family_backup.js",
  "pages/family_pause.css",
  "pages/family_pause.html",
  "pages/family_pause.js",
  "pages/family_tools.js",
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
  "content/yt_clean.js",
  "content/hide_comments.js",
  "content/profanity_mask.js",
  "content/strict_mode.js",
  "content/akhi_notice.js",
  "content/riba_warning.js",
  "content/halal_check.js",
  "content/quran_follow.js",
  "content/trusted_sources.js",
  "content/halal_places.js",
  "content/deen_time.js",
  "content/word_block.js",
  "lib/family_controls.js",
  "lib/parent_report.js",
  "lib/family.js",
  "lib/premium.js",
  "lib/prayer_pause.js",
  "lib/home_card.js",
  "lib/image_classifier.js",
  "pages/family_backup.js",
  "pages/family_pause.js",
  "pages/family_tools.js",
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

// a file the manifest names but the build left out stops a whole group of content scripts from loading
const manifest = JSON.parse(readFileSync(join(target, "manifest.json"), "utf8"));
const named = [
  ...(manifest.background?.scripts ?? []),
  ...(manifest.content_scripts ?? []).flatMap(group => [...(group.js ?? []), ...(group.css ?? [])]),
];
const missing = named.filter(path => !existsSync(join(target, path)));
if (missing.length) {
  throw new Error(`Named in manifest.json but missing from the extension: ${missing.join(", ")}`);
}
