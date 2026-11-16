// Copyright (c) 2026 the AkhiBrowser authors. All rights reserved.
// Uploads a Play bundle to a track with the Android Publisher API, as the service account of the JSON key file:
//   node upload_play.mjs --aab <file.aab> --key <service-account.json> [--track internal] [--notes "text"]
// On the internal track the release goes out to the testers at once; on any other track it stays a draft, to send
// out from the Play Console. The service account needs "Release to testing tracks" (and "Release to production" for
// production) in the Play Console's Users and permissions.
// --dry-run: the same up to the commit, then Play validates the edit and it's deleted, so nothing is published: a
// check that the bundle's signature and version are accepted and the service account may release.

import fs from "node:fs";
import { parseArgs } from "node:util";

const PACKAGE = "org.akhibrowser";
const API = `https://androidpublisher.googleapis.com/androidpublisher/v3/applications/${PACKAGE}`;
const UPLOAD = `https://androidpublisher.googleapis.com/upload/androidpublisher/v3/applications/${PACKAGE}`;

const { values } = parseArgs({
  options: {
    aab: { type: "string" },
    key: { type: "string" },
    track: { type: "string", default: "internal" },
    notes: { type: "string", default: "" },
    "dry-run": { type: "boolean", default: false },
  },
});
if (!values.aab || !values.key) {
  console.error("Usage: node upload_play.mjs --aab <file.aab> --key <service-account.json> [--track internal]");
  process.exit(2);
}

const base64url = data => Buffer.from(data).toString("base64url");

async function accessToken(account) {
  const now = Math.floor(Date.now() / 1000);
  const unsigned = `${base64url(JSON.stringify({ alg: "RS256", typ: "JWT" }))}.${base64url(
    JSON.stringify({
      iss: account.client_email,
      scope: "https://www.googleapis.com/auth/androidpublisher",
      aud: "https://oauth2.googleapis.com/token",
      iat: now,
      exp: now + 3600,
    })
  )}`;
  const der = Buffer.from(account.private_key.replace(/-----[^-]+-----/g, "").replace(/\s+/g, ""), "base64");
  const key = await crypto.subtle.importKey("pkcs8", der, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, [
    "sign",
  ]);
  const signature = await crypto.subtle.sign("RSASSA-PKCS1-v1_5", key, new TextEncoder().encode(unsigned));
  const response = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "urn:ietf:params:oauth:grant-type:jwt-bearer",
      assertion: `${unsigned}.${base64url(signature)}`,
    }),
  });
  if (!response.ok) {
    throw new Error(`Google token: ${response.status} ${await response.text()}`);
  }
  return (await response.json()).access_token;
}

const token = await accessToken(JSON.parse(fs.readFileSync(values.key, "utf8")));
async function call(url, init = {}) {
  const response = await fetch(url, {
    ...init,
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json", ...init.headers },
  });
  if (!response.ok) {
    throw new Error(`${init.method ?? "GET"} ${url}: ${response.status} ${await response.text()}`);
  }
  return response.status === 204 ? null : response.json();
}

const edit = await call(`${API}/edits`, { method: "POST", body: "{}" });
const bundle = await call(`${UPLOAD}/edits/${edit.id}/bundles?uploadType=media`, {
  method: "POST",
  headers: { "Content-Type": "application/octet-stream" },
  body: fs.readFileSync(values.aab),
});
const release = {
  versionCodes: [String(bundle.versionCode)],
  status: values.track === "internal" ? "completed" : "draft",
  ...(values.notes && { releaseNotes: [{ language: "en-US", text: values.notes.slice(0, 500) }] }),
};
await call(`${API}/edits/${edit.id}/tracks/${values.track}`, {
  method: "PUT",
  body: JSON.stringify({ track: values.track, releases: [release] }),
});
if (values["dry-run"]) {
  try {
    await call(`${API}/edits/${edit.id}:validate`, { method: "POST", body: "{}" });
    const { tracks = [] } = (await call(`${API}/edits/${edit.id}/tracks`)) ?? {};
    for (const track of tracks) {
      const codes = (track.releases ?? []).map(r => `${r.name ?? "?"} [${(r.versionCodes ?? []).join(",")}] ${r.status}`);
      console.log(`  ${track.track}: ${codes.join("; ") || "empty"}`);
    }
  } finally {
    await call(`${API}/edits/${edit.id}`, { method: "DELETE" });
  }
  console.log(
    `Play (dry run): version code ${bundle.versionCode} accepted and validated for the ${values.track} track; the edit was deleted, nothing published`
  );
} else {
  await call(`${API}/edits/${edit.id}:commit`, { method: "POST", body: "{}" });
  console.log(`Play: version code ${bundle.versionCode} on the ${values.track} track (${release.status})`);
}
