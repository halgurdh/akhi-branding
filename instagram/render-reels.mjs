// Renders pending reels to MP4 with ffmpeg and uploads them back to the worker.
// Runs in GitHub Actions (.github/workflows/render-reels.yml of akhi-branding: a public repo, so the Actions minutes
// are free; the worker itself lives in halgurdh/akhibrowser-premium). Needs ffmpeg and, to read the worker's render
// secret from D1, CLOUDFLARE_API_TOKEN + CLOUDFLARE_ACCOUNT_ID. No secret is in this file.
//
//   WORKER_URL=https://akhi-instagram.akhibrowser.workers.dev node instagram/render-reels.mjs
//   (RENDER_SECRET=... skips the D1 lookup)
import { execFileSync, spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const WORKER = (process.env.WORKER_URL || "").replace(/\/$/, "");
if (!WORKER) throw new Error("WORKER_URL is not set");
const FPS = 30;

// The secret that lets this job talk to the worker. Tried in order:
// 1. RENDER_SECRET from the environment;
// 2. the worker's secret stored in D1 (needs D1 access on the Cloudflare token);
// 3. a fresh random secret set as the Worker secret RENDER_SECRET with `wrangler secret put` (only needs the
//    Workers permission the deploy job already uses). Returns { secret, fresh }.
function renderSecret() {
  if (process.env.RENDER_SECRET) return { secret: process.env.RENDER_SECRET, fresh: false };
  try {
    const out = execFileSync(
      "npx",
      ["--yes", "wrangler@4", "d1", "execute", "akhi-instagram", "--remote", "--json", "--command", "SELECT v FROM meta WHERE k = 'render_secret'"],
      { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] }
    );
    const v = JSON.parse(out)?.[0]?.results?.[0]?.v;
    if (v) return { secret: v, fresh: false };
  } catch (e) {
    console.log("D1 not readable with this token, setting a fresh Worker secret instead");
  }
  const secret = crypto.randomUUID().replace(/-/g, "") + crypto.randomUUID().replace(/-/g, "");
  execFileSync("npx", ["--yes", "wrangler@4", "secret", "put", "RENDER_SECRET", "--name", "akhi-instagram"], { input: secret, encoding: "utf8", stdio: ["pipe", "inherit", "inherit"] });
  return { secret, fresh: true };
}

async function download(url, file) {
  const r = await fetch(url, { redirect: "follow" });
  if (!r.ok) throw new Error(`download ${r.status}: ${url}`);
  fs.writeFileSync(file, Buffer.from(await r.arrayBuffer()));
  return file;
}

function ffmpeg(args) {
  const r = spawnSync("ffmpeg", ["-hide_banner", "-loglevel", "error", "-y", ...args], { encoding: "utf8", maxBuffer: 1 << 26 });
  if (r.status !== 0) throw new Error(`ffmpeg failed: ${(r.stderr || "").slice(-600)}`);
}

function duration(file) {
  const r = spawnSync("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", file], { encoding: "utf8" });
  const d = parseFloat(r.stdout);
  if (!(d > 0)) throw new Error(`ffprobe: no duration for ${file}`);
  return d;
}

// Quran recitation: whole ayat joined into one track. The reel is made long enough for the full recitation:
// it starts at REC_START and the Quran card is stretched so nothing is ever cut off.
const REC_START = 0.6;
async function prepareRecitation(job, dir) {
  if (!job.recitation?.urls?.length) return null;
  const parts = [];
  for (let i = 0; i < job.recitation.urls.length; i++) parts.push(await download(job.recitation.urls[i], path.join(dir, `ayah${i}.mp3`)));
  const list = path.join(dir, "ayat.txt");
  fs.writeFileSync(list, parts.map((f) => `file '${f}'`).join("\n"));
  const file = path.join(dir, "recitation.m4a");
  ffmpeg(["-f", "concat", "-safe", "0", "-i", list, "-ac", "2", "-ar", "44100", "-c:a", "aac", "-b:a", "160k", file]);
  const dur = duration(file);
  const segs = job.segments;
  const total = segs.reduce((t, s) => t + s.dur, 0);
  const need = REC_START + dur + 1.2 - total;
  if (need > 0) {
    const card = segs.find((s) => s.type === "ayah") || segs[segs.length - 2] || segs[0];
    card.dur = Math.round((card.dur + need) * 10) / 10;
  }
  return file;
}

async function renderJob(job, base, dir) {
  const inputs = [];
  const filters = [];
  const recitation = await prepareRecitation(job, dir);
  const segs = job.segments;
  const total = segs.reduce((t, s) => t + s.dur, 0);
  let n = 0;
  for (let i = 0; i < segs.length; i++) {
    const s = segs[i];
    const frames = Math.round(s.dur * FPS);
    // background
    if (s.clip.kind === "video") {
      const f = await download(s.clip.url, path.join(dir, `clip${i}.mp4`));
      inputs.push("-stream_loop", "-1", "-t", String(s.dur + 0.5), "-i", f);
      filters.push(
        `[${n}:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=${FPS},setsar=1,trim=end_frame=${frames},setpts=PTS-STARTPTS,eq=brightness=-0.04:saturation=1.05[bg${i}]`
      );
    } else {
      const f = await download(`${base}/m/${s.clip.key}`, path.join(dir, `img${i}${path.extname(s.clip.key) || ".jpg"}`));
      inputs.push("-i", f);
      const zoomIn = i % 2 === 0;
      filters.push(
        `[${n}:v]scale=1440:2560:force_original_aspect_ratio=increase,crop=1440:2560,zoompan=z='${zoomIn ? `1+0.12*on/${frames}` : `1.12-0.12*on/${frames}`}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=${frames}:s=1080x1920:fps=${FPS},setsar=1,trim=end_frame=${frames},setpts=PTS-STARTPTS[bg${i}]`
      );
    }
    n++;
    // text overlay (fades in)
    const o = await download(`${base}/m/${s.overlay}`, path.join(dir, `ov${i}.png`));
    inputs.push("-loop", "1", "-framerate", String(FPS), "-t", String(s.dur), "-i", o);
    filters.push(`[${n}:v]format=rgba,fade=t=in:st=0:d=0.35:alpha=1[ov${i}]`);
    filters.push(`[bg${i}][ov${i}]overlay=0:0:shortest=1,format=yuv420p[s${i}]`);
    n++;
  }
  filters.push(`${segs.map((_, i) => `[s${i}]`).join("")}concat=n=${segs.length}:v=1:a=0[v]`);
  // audio: Quran recitation (never mixed with music), uploaded music (faded) or silence
  if (recitation) {
    inputs.push("-i", recitation);
    const ms = Math.round(REC_START * 1000);
    filters.push(`[${n}:a]adelay=${ms}|${ms},apad,atrim=0:${total},asetpts=PTS-STARTPTS[a]`);
  } else if (job.music) {
    const m = await download(`${base}/m/${job.music}`, path.join(dir, "music.mp3"));
    inputs.push("-i", m);
    filters.push(`[${n}:a]atrim=0:${total},asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.4,afade=t=out:st=${Math.max(0, total - 1.8)}:d=1.8,volume=0.85[a]`);
  } else {
    inputs.push("-f", "lavfi", "-t", String(total), "-i", "anullsrc=r=44100:cl=stereo");
    filters.push(`[${n}:a]anull[a]`);
  }
  const out = path.join(dir, "reel.mp4");
  ffmpeg([
    ...inputs,
    "-filter_complex", filters.join(";"),
    "-map", "[v]", "-map", "[a]",
    "-t", String(total),
    "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-profile:v", "high", "-pix_fmt", "yuv420p", "-r", String(FPS),
    "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
    "-movflags", "+faststart",
    out,
  ]);
  const cover = path.join(dir, "cover.jpg");
  ffmpeg(["-ss", "1.0", "-i", out, "-frames:v", "1", "-q:v", "3", cover]);
  return { out, cover };
}

const { secret, fresh } = renderSecret();
const headers = { Authorization: `Bearer ${secret}` };
// a freshly set Worker secret takes a few seconds to reach every Cloudflare location
let res;
for (let i = 0; i < (fresh ? 12 : 1); i++) {
  res = await fetch(`${WORKER}/api/render/jobs`, { headers });
  if (res.status !== 401) break;
  await new Promise((r) => setTimeout(r, 5000));
}
if (!res.ok) throw new Error(`jobs: ${res.status} ${await res.text()}`);
const { base, jobs } = await res.json();
console.log(`${jobs.length} reel(s) to render`);
let failed = 0;
for (const job of jobs) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "reel-"));
  const t0 = Date.now();
  try {
    const { out, cover } = await renderJob(job, base, dir);
    const form = new FormData();
    form.append("video", new Blob([fs.readFileSync(out)], { type: "video/mp4" }), "reel.mp4");
    form.append("cover", new Blob([fs.readFileSync(cover)], { type: "image/jpeg" }), "cover.jpg");
    // retry: a kept-alive connection can be closed while ffmpeg runs (EPIPE on the first write)
    let up;
    for (let attempt = 1; ; attempt++) {
      try {
        up = await fetch(`${WORKER}/api/render/${job.id}`, { method: "POST", headers, body: form });
        break;
      } catch (e) {
        if (attempt >= 3) throw e;
        await new Promise((r) => setTimeout(r, 2000 * attempt));
      }
    }
    if (!up.ok) throw new Error(`upload ${up.status}: ${await up.text()}`);
    console.log(`✓ ${job.brand} ${job.day}: ${(fs.statSync(out).size / 1048576).toFixed(1)} MB in ${((Date.now() - t0) / 1000).toFixed(0)}s`);
  } catch (e) {
    failed++;
    console.error(`✗ ${job.brand} ${job.day}: ${e.message}${e.cause ? ` (${e.cause.message || e.cause})` : ""}`);
    await fetch(`${WORKER}/api/render/${job.id}/fail`, { method: "POST", headers, body: e.message.slice(0, 400) }).catch(() => {});
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
}
if (failed) process.exitCode = 1;
