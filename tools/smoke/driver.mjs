// S20 smoke test of the debug app (org.akhibrowser.debug) over WebDriver BiDi, forwarded with adb to 127.0.0.1:9222.
// Settings are written to the extension's storage.local from a privileged context, one feature at a time.
//   node driver.mjs <out folder> [only test name substring]
import fs from "node:fs";

const [outDir, only] = process.argv.slice(2);
const results = [];
const ID = "akhi@akhibrowser.org";
const LOCAL = "http://127.0.0.1:8765";
const sleep = ms => new Promise(r => setTimeout(r, ms));

let socket;
for (let i = 0; i < 90 && !socket; i++) {
  try {
    socket = await new Promise((resolve, reject) => {
      const ws = new WebSocket("ws://127.0.0.1:9222/session");
      ws.onopen = () => resolve(ws);
      ws.onerror = reject;
    });
  } catch {
    await sleep(1000);
  }
}
if (!socket) {
  console.error("No WebDriver BiDi connection");
  process.exit(2);
}
let nextId = 0;
const pending = new Map();
socket.onmessage = e => {
  const m = JSON.parse(e.data);
  if (m.id && pending.has(m.id)) {
    pending.get(m.id)(m);
    pending.delete(m.id);
  }
};
socket.onclose = () => {
  console.error("The connection closed: the app stopped or crashed");
  fs.writeFileSync(`${outDir}/results.json`, JSON.stringify(results, null, 2));
  process.exit(4);
};
const send = (method, params = {}) =>
  new Promise(resolve => {
    const id = ++nextId;
    pending.set(id, resolve);
    socket.send(JSON.stringify({ id, method, params }));
    setTimeout(() => {
      if (pending.delete(id)) {
        resolve({ error: "timeout", message: `${method} took over 60 s` });
      }
    }, 60000);
  });

const session = await send("session.new", { capabilities: {} });
if (session.error) {
  console.error("session.new:", JSON.stringify(session));
  process.exit(3);
}

async function chromeContext() {
  const tree = await send("browsingContext.getTree", { "moz:scope": "chrome" });
  if (tree.error) {
    throw new Error(`chrome scope: ${tree.error} ${tree.message}`);
  }
  return tree.result.contexts[0].context;
}

async function evalIn(context, expression) {
  const r = await send("script.evaluate", {
    expression,
    target: { context },
    awaitPromise: true,
    resultOwnership: "none",
  });
  if (r.error) {
    return { error: `${r.error}: ${r.message}` };
  }
  if (r.result.type === "exception") {
    return { error: r.result.exceptionDetails?.text };
  }
  return { value: r.result.result?.value };
}

// storage.local of the extension: set items (null removes), answer all of it
async function storage(items = {}) {
  const ctx = await chromeContext();
  const r = await evalIn(
    ctx,
    `(async () => {
      const { ExtensionStorageIDB } = ChromeUtils.importESModule("resource://gre/modules/ExtensionStorageIDB.sys.mjs");
      const policy = WebExtensionPolicy.getByID(${JSON.stringify(ID)});
      const db = await ExtensionStorageIDB.open(ExtensionStorageIDB.getStoragePrincipal(policy.extension));
      const items = ${JSON.stringify(items)};
      const removed = Object.keys(items).filter(k => items[k] === null);
      const kept = Object.fromEntries(Object.entries(items).filter(([, v]) => v !== null));
      let changes = {};
      if (Object.keys(kept).length) Object.assign(changes, (await db.set(kept)) ?? {});
      if (removed.length) Object.assign(changes, (await db.remove(removed)) ?? {});
      if (Object.keys(changes).length) ExtensionStorageIDB.notifyListeners(policy.id, changes);
      return JSON.stringify(await db.get(null));
    })()`
  );
  if (r.error) {
    throw new Error(`storage: ${r.error}`);
  }
  return JSON.parse(r.value);
}

async function tab() {
  const tree = await send("browsingContext.getTree", { maxDepth: 0 });
  return tree.result.contexts[0];
}

// open a URL, wait until it settles; answers the final URL
async function open(url, settle = 6000) {
  const { context } = await tab();
  send("browsingContext.navigate", { context, url, wait: "none" });
  let last = "";
  let stable = 0;
  for (let waited = 0; waited < 25000; waited += 1000) {
    await sleep(1000);
    const now = (await tab()).url;
    if (now.startsWith("moz-extension:")) {
      return now;
    }
    stable = now === last && now !== "about:blank" ? stable + 1000 : 0;
    last = now;
    if (stable >= settle && waited >= settle) {
      break;
    }
  }
  return (await tab()).url;
}

async function page(expression) {
  const { context, url } = await tab();
  if (url.startsWith("moz-extension:")) {
    return { error: "on an extension page" };
  }
  return evalIn(context, expression);
}

// Google and YouTube ask for consent from Europe: reject all, once
async function passConsent() {
  const { url } = await tab();
  if (!/consent\.(google|youtube)\./.test(url)) {
    return false;
  }
  await page(`(() => {
    const b = [...document.querySelectorAll("button, input[type=submit]")].find(x =>
      /reject all|alles afwijzen|alle ablehnen|tout refuser/i.test(x.innerText || x.value));
    b?.click(); return !!b;
  })()`);
  await sleep(5000);
  return true;
}

async function openPast(url, settle) {
  let now = await open(url, settle);
  if (await passConsent()) {
    now = await open(url, settle);
  }
  return now;
}

const isBlocked = url => url.startsWith("moz-extension:") && /blocked|family_pause/.test(url);
function record(name, ok, detail) {
  results.push({ name, ok, detail });
  console.log(`${ok === null ? "MANUAL" : ok ? "ok    " : "FAILED"}  ${name}: ${detail}`);
}

async function test(name, fn) {
  if (only && !new RegExp(only).test(name)) {
    return;
  }
  try {
    await fn();
  } catch (e) {
    record(name, false, `error: ${e.message}`);
  }
}

// a feature on for one test, off after
async function withSettings(items, fn) {
  await storage(items);
  await sleep(1500);
  try {
    await fn();
  } finally {
    const reset = Object.fromEntries(
      Object.keys(items).map(k => [k, typeof items[k] === "boolean" ? false : null])
    );
    await storage(reset);
    await sleep(1000);
  }
}

// the extension starts after the first window
await sleep(12000);

// a release build on a computer has no Premium for testing: Family in this throwaway profile's storage, for the test
if (process.env.SMOKE_FAMILY === "storage") {
  await storage({ premiumPlan: "family", premiumUntil: Date.now() + 3600 * 1000 });
}

await test("0 Family Premium for testing", async () => {
  const s = await storage();
  const minutes = Math.round(((s.premiumUntil ?? 0) - Date.now()) / 60000);
  const isTestFamily = s.premiumDebug === true || process.env.SMOKE_FAMILY === "storage";
  record("0 Family Premium for testing", s.premiumPlan === "family" && isTestFamily && minutes > 0,
    `plan ${s.premiumPlan}, premiumDebug ${s.premiumDebug}, ${minutes} minutes left`);
});

// ---------- free, on by default ----------
await test("1 ordinary site", async () => {
  const url = await open("https://www.wikipedia.org/");
  record("1 ordinary site", url.includes("wikipedia.org"), url);
  const { context } = await tab();
  const shot = await send("browsingContext.captureScreenshot", { context });
  if (shot.result) {
    fs.writeFileSync(`${outDir}/1-ordinary-site.png`, Buffer.from(shot.result.data, "base64"));
  }
});
await test("2 adult site blocked", async () => {
  const url = await open("https://www.pornhub.com/");
  record("2 adult site blocked", isBlocked(url), isBlocked(url) ? url : "(the page itself)");
});
await test("3 adult subdomain blocked", async () => {
  const url = await open("https://fr.pornhub.com/");
  record("3 adult subdomain blocked", isBlocked(url), isBlocked(url) ? url : "(the page itself)");
});
await test("4 haram search blocked", async () => {
  const url = await openPast("https://www.google.com/search?q=buy+beer");
  record("4 haram search blocked", isBlocked(url), url);
});
await test("5 Google SafeSearch", async () => {
  const url = await openPast("https://www.google.com/search?q=test");
  record("5 Google SafeSearch", decodeURIComponent(url).includes("safe=active"), url);
});
await test("6 ad blocking", async () => {
  await open("https://www.wikipedia.org/", 2000);
  const r = await page(`fetch("https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js", {mode: "no-cors"})
    .then(() => "loaded", e => "blocked: " + e.message)`);
  record("6 ad blocking", String(r.value).startsWith("blocked"), r.value ?? r.error);
});
await test("7 image scan (nudity blur, blur women)", async () => {
  await open("https://en.wikipedia.org/wiki/Miss_World", 8000);
  const r = await page(`JSON.stringify({
    scanned: document.querySelectorAll("[data-akhi-scan], [data-akhi-image]").length,
    images: document.images.length })`);
  const v = JSON.parse(r.value ?? "{}");
  record("7 image scan (nudity blur, blur women)", v.scanned > 0, `${v.scanned} of ${v.images} images marked by the scan; whether the right ones are blurred is a visual check`);
});
await test("8 YouTube Restricted Mode", async () => {
  await openPast("https://www.youtube.com/", 6000);
  const r = await page(`(document.cookie.match(/PREF=[^;]*/)||[""])[0] + " | " +
    ((window.ytcfg?.data_ ?? {}).RESTRICTED_MODE ?? (document.body.innerHTML.includes('"restrictedMode":true') ? "restrictedMode:true" : "?"))`);
  record("8 YouTube Restricted Mode", null, `header YouTube-Restrict: Strict is set by the background; page says: ${r.value ?? r.error}`);
});

// ---------- paid, each on for its test ----------
await test("9 activity summary records blocks", async () => {
  await withSettings({ activitySummary: true, blockList: true, familyBlocked: ["example.com"] }, async () => {
    await open("https://example.com/");
    await sleep(1500);
    const s = await storage();
    record("9 activity summary records blocks", !!s.familyActivity && JSON.stringify(s.familyActivity).includes("familyBlocked"),
      JSON.stringify(s.familyActivity));
  });
});
await test("10 block list", async () => {
  await withSettings({ blockList: true, familyBlocked: ["example.com"] }, async () => {
    const url = await open("https://example.com/");
    record("10 block list", isBlocked(url), url);
  });
});
await test("11 allow only", async () => {
  await withSettings({ allowOnly: true, familyAllowed: ["wikipedia.org"] }, async () => {
    const blocked = await open("https://example.com/");
    const allowed = await open("https://www.wikipedia.org/", 3000);
    record("11 allow only", isBlocked(blocked) && allowed.includes("wikipedia.org"), `example.com -> ${blocked}; wikipedia -> ${allowed}`);
  });
});
await test("12 time rules (bedtime now)", async () => {
  const now = new Date();
  const hhmm = d => `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  const start = hhmm(new Date(now - 30 * 60000));
  const end = hhmm(new Date(+now + 30 * 60000));
  await withSettings({ timeRules: true, familyTimes: { bedtime: { start, end } } }, async () => {
    const url = await open("https://example.com/");
    record("12 time rules (bedtime now)", isBlocked(url), `${start}-${end}: ${url}`);
  });
});
await test("13 loot box block", async () => {
  await withSettings({ lootboxBlock: true }, async () => {
    const url = await open("https://hellcase.com/");
    record("13 loot box block", isBlocked(url), url);
  });
});
await test("14 internet pause", async () => {
  await withSettings({ internetPause: true, internetPauseUntil: Date.now() + 10 * 60000 }, async () => {
    const url = await open("https://example.com/");
    record("14 internet pause", isBlocked(url), url);
  });
});
await test("15 strict mode", async () => {
  await withSettings({ strictMode: true, strictModeScope: "all" }, async () => {
    await open("https://www.wikipedia.org/", 3000);
    const r = await page(`document.documentElement.hasAttribute("data-akhi-strict")`);
    record("15 strict mode", r.value === true, `html[data-akhi-strict]: ${r.value ?? r.error}`);
  });
});
await test("16 profanity mask", async () => {
  await withSettings({ profanityMask: true }, async () => {
    await open(`${LOCAL}/profanity.html`, 3000);
    const r = await page(`document.getElementById("t").textContent`);
    record("16 profanity mask", !!r.value && !/fuck|shit|bastard/i.test(r.value), r.value ?? r.error);
  });
});
await test("17 halal check", async () => {
  await withSettings({ halalCheck: true }, async () => {
    await open(`${LOCAL}/halal.html`, 4000);
    const r = await page(`!!document.querySelector("akhi-notice")`);
    record("17 halal check", r.value === true, `notice shown: ${r.value ?? r.error}`);
  });
});
await test("18 riba warning", async () => {
  await withSettings({ ribaWarning: true }, async () => {
    await open(`${LOCAL}/hypotheek/`, 4000);
    const local = await page(`!!document.querySelector("akhi-notice")`);
    await open("https://www.klarna.com/", 5000);
    const real = await page(`!!document.querySelector("akhi-notice")`);
    record("18 riba warning", local.value === true || real.value === true, `/hypotheek page: ${local.value ?? local.error}; klarna.com: ${real.value ?? real.error}`);
  });
});
await test("19 trusted sources", async () => {
  await withSettings({ trustedSources: true }, async () => {
    // DuckDuckGo: Google answers a browser under automation with its robot check instead of results
    await openPast("https://duckduckgo.com/?q=is+mortgage+halal", 5000);
    const r = await page(`!!document.querySelector("akhi-trusted, [data-akhi-trusted], .akhi-trusted-mark")`);
    record("19 trusted sources", r.value === true, `box or marks: ${r.value ?? r.error}`);
  });
});
await test("20 halal places (Google Maps)", async () => {
  await withSettings({ halalPlaces: true }, async () => {
    await openPast("https://www.google.com/maps/@52.3676,4.9041,15z", 8000);
    const r = await page(`!!document.querySelector("akhi-halal-places")`);
    record("20 halal places (Google Maps)", r.value === true, `panel: ${r.value ?? r.error} (${(await tab()).url})`);
  });
});
await test("21 YouTube clean mode", async () => {
  await withSettings({ youtubeCleanMode: true }, async () => {
    await openPast("https://www.youtube.com/", 5000);
    const r = await page(`document.documentElement.hasAttribute("data-akhi-youtube-clean")`);
    record("21 YouTube clean mode", r.value === true, `html[data-akhi-youtube-clean]: ${r.value ?? r.error}`);
  });
});

// a recitation video, found by a search on YouTube
let recitation = null;
async function findRecitation() {
  if (recitation) {
    return recitation;
  }
  await openPast("https://www.youtube.com/results?search_query=surah+yasin+mishary+alafasy", 8000);
  const info = await page(`location.href + " | links: " + document.querySelectorAll('a[href*="/watch"]').length`);
  console.log("   search page:", info.value ?? info.error);
  const r = await page(`(() => {
    const links = [...document.querySelectorAll('a[href*="/watch?v="]')];
    const a = links.find(x => /yas|surah|recit/i.test(x.textContent + x.title + (x.getAttribute("aria-label")||""))) ?? links[0];
    return a ? new URL(a.getAttribute("href"), location.href).href : null; })()`);
  recitation = r.value;
  return recitation;
}

await test("22 hide comments", async () => {
  await withSettings({ hideComments: true }, async () => {
    // the mark is on every YouTube page, a video isn't needed for it
    await openPast("https://www.youtube.com/", 5000);
    const r = await page(`document.documentElement.hasAttribute("data-akhi-hide-comments")`);
    record("22 hide comments", r.value === true, `html[data-akhi-hide-comments]: ${r.value ?? r.error}`);
  });
});
await test("23 follow the recitation", async () => {
  await withSettings({ quranFollow: true }, async () => {
    const video = await findRecitation();
    if (!video) {
      return record("23 follow the recitation", false, "no video found");
    }
    await open(video, 8000);
    const r = await page(`!!document.querySelector("akhi-quran")`);
    record("23 follow the recitation", r.value === true, `panel: ${r.value ?? r.error} (${video})`);
  });
});
await test("24 feed limit (Shorts open as a video)", async () => {
  await withSettings({ feedLimit: true }, async () => {
    const video = await findRecitation();
    const id = video && new URL(video).searchParams.get("v");
    if (!id) {
      return record("24 feed limit (Shorts open as a video)", false, "no video id");
    }
    const url = await open(`https://www.youtube.com/shorts/${id}`, 5000);
    record("24 feed limit (Shorts open as a video)", !url.includes("/shorts/"), url);
  });
});
await test("25 Deen Time", async () => {
  await withSettings({ deenTime: true, deenTimeChannels: ["@oneminutemuslim"] }, async () => {
    await openPast("https://www.youtube.com/", 6000);
    const r = await page(`document.documentElement.hasAttribute("data-akhi-deen") || !!document.querySelector("akhi-deen-time")`);
    record("25 Deen Time", r.value === true, `home replaced by the chosen channels: ${r.value ?? r.error}`);
  });
});

await test("26 halal check badges on Jumbo", async () => {
  await withSettings({ halalCheck: true }, async () => {
    await open("https://www.jumbo.com/producten/?searchType=keyword&searchTerms=varkenshaas", 8000);
    const r = await page(`document.querySelectorAll(".akhi-halal-badge").length`);
    record("26 halal check badges on Jumbo", r.value > 0, `${r.value ?? r.error} badges`);
  });
});
await test("27 riba warning on car loans", async () => {
  await withSettings({ ribaWarning: true }, async () => {
    await open(`${LOCAL}/auto-lenen/`, 4000);
    const r = await page(`!!document.querySelector("akhi-notice")`);
    record("27 riba warning on car loans", r.value === true, `notice on /auto-lenen: ${r.value ?? r.error}`);
  });
});
await test("28 Mozilla's search code taken out", async () => {
  const url = await openPast("https://www.google.com/search?client=firefox-b-m&q=halal", 3000);
  record("28 Mozilla's search code taken out", !/client=firefox/.test(url), url);
});

for (const [name, why] of [
  ["26 no music", "audio: listen on a video with music"],
  ["27 blur men / recognize hijab / blur unclear", "image model: a visual check"],
  ["28 no private tabs", "private tab button in the app UI"],
  ["29 prayer pause", "only at prayer time"],
  ["30 family backup", "needs a backup round trip between devices"],
]) {
  if (!only) {
    record(name, null, why);
  }
}

fs.writeFileSync(`${outDir}/results.json`, JSON.stringify(results, null, 2));
await send("session.end");
socket.close();
process.exit(0);
