// Drives a running AkhiBrowser over WebDriver BiDi (--remote-debugging-port) for smoke_test.py: waits for the
// built-in extension, opens each page and prints where the tab ended up, as JSON. Screenshots only of the pages
// marked safe, never of a page that should have been blocked.
//   node smoke_bidi.mjs <port> <out folder> <pages JSON: [{name, url, screenshot}]>

import fs from "node:fs";

const [port, outDir, pagesJson] = process.argv.slice(2);
const pages = JSON.parse(pagesJson);
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

let socket;
for (let attempt = 0; attempt < 60 && !socket; attempt++) {
  try {
    socket = await new Promise((resolve, reject) => {
      const ws = new WebSocket(`ws://127.0.0.1:${port}/session`);
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

let id = 0;
const pending = new Map();
socket.onmessage = event => {
  const message = JSON.parse(event.data);
  if (message.id && pending.has(message.id)) {
    pending.get(message.id)(message);
    pending.delete(message.id);
  }
};
const send = (method, params = {}) =>
  new Promise(resolve => {
    const messageId = ++id;
    pending.set(messageId, resolve);
    socket.send(JSON.stringify({ id: messageId, method, params }));
  });

await send("session.new", { capabilities: {} });
// the built-in extension starts after the first window
await sleep(10000);

const results = [];
for (const page of pages) {
  const tree = await send("browsingContext.getTree", {});
  const context = tree.result.contexts[0].context;
  send("browsingContext.navigate", { context, url: page.url, wait: "none" });
  let url = "";
  for (let waited = 0; waited < 20; waited++) {
    await sleep(1000);
    const now = await send("browsingContext.getTree", {});
    url = now.result?.contexts?.[0]?.url || url;
    if (url && url !== "about:blank" && (url.startsWith("moz-extension:") || waited >= 8)) {
      break;
    }
  }
  if (page.screenshot) {
    const top = (await send("browsingContext.getTree", {})).result.contexts[0].context;
    const shot = await send("browsingContext.captureScreenshot", { context: top });
    if (shot.result) {
      fs.writeFileSync(`${outDir}/${page.name}.png`, Buffer.from(shot.result.data, "base64"));
    }
  }
  results.push({ name: page.name, url });
}
console.log(JSON.stringify(results));
await send("session.end");
socket.close();
process.exit(0);
