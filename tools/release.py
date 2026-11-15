#!/usr/bin/env python3
# Copyright (c) 2026 the AkhiBrowser authors. All rights reserved.
"""Builds a whole AkhiBrowser release, from the root of the tree, and mails how it went:

    python browser/branding/akhi/tools/release.py 1.3.3 [--push] [--upload play,msstore,github]

1. pull: fast-forwards main of the tree and of the three submodules (stops when one has changes or has diverged)
2. version: browser/config/akhi_version.txt, lib/updates.js and package.json, committed in the extension and the tree
3. desktop: mach build, the Windows installer, the signed update (.mar + xml) and the Microsoft Store package
4. smoke: the installer's browser against tools/smoke (Family Premium included); a critical failure stops the release
5. android: mach build, the direct APK and the Play bundle, with a higher version code than the last release and every
   file of the merged extension in the APK
6. sums and Drive: SHA256SUMS.txt, the files to G:/My Drive/AkhiRelease and the previous version's to a subfolder
7. uploads, only those asked: Play (internal track, or a draft on another), the Microsoft Store (a draft unless
   --msstore-commit) and a GitHub release with the files of github-release-contents
8. --push: pushes main of the submodules and the tree, then makes the GitHub release (so its tag is the new main),
   and with --linux-macos starts the Linux and macOS builds on GitHub, which attach themselves to it

The mail goes through the license server's /ops/notify, with AKHI_OPS_TOKEN from the environment or KEYS/ops-token.txt.
The GitHub workflow "Release" of akhi-branding runs this on the self-hosted runner of this PC.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
TOOLS = ROOT / "browser/branding/akhi/tools"
SUBMODULES = ["browser/extensions/akhi", "browser/extensions/akhi-premium", "browser/branding/akhi"]
KEYS = Path(os.environ.get("AKHI_KEYS", "C:/Users/halgu/AkhiBrowser-keys"))
SIGNING = KEYS / "signing.properties"
UPDATE_KEYS = Path(os.environ.get("AKHI_UPDATE_KEYS", "C:/Users/halgu/.akhibrowser-update-keys/primary"))
PLAY_KEY = KEYS / "play-service-account.json"
DRIVE = Path(os.environ.get("AKHI_DRIVE", "G:/My Drive/AkhiRelease"))
SEVEN_ZIP = Path("C:/Program Files/7-Zip/7z.exe")
NOTIFY_URL = "https://akhi-license.akhibrowser.workers.dev/ops/notify"
DESKTOP_CONFIG = "browser/branding/akhi/mozconfigs/akhi-desktop"
ANDROID_CONFIG = "browser/branding/akhi/mozconfigs/akhi-android-arm64"
DESKTOP_OBJ = ROOT / "obj-akhi-desktop"
ANDROID_OBJ = ROOT / "obj-akhi-android-arm64"
STATE = ROOT / "artifacts/release-state.json"
# the highest version code of 1.3.2 (its Play bundle), for the first run without a state file
FIRST_VERSION_CODE = 2016196287
MSSTORE_ID = "9N8KMF22Z6K4"
MSSTORE_IDENTITY = [
    "--identity-name", "RezgariTech.AkhiBrowser",
    "--publisher", "CN=F0209D67-61A9-4F82-9C24-608F78CBF40B",
    "--publisher-display-name", "Rezgari Tech",
]
CRITICAL_SMOKE = [
    "0 Family", "1 ordinary", "2 adult site", "3 adult subdomain", "4 haram search", "5 Google SafeSearch",
    "10 block list", "11 allow only", "14 internet pause",
]
TARGETS = ["windows", "android", "play", "msstore"]
STEPS = ["pull", "version", "desktop", "smoke", "android", "sums", "drive", "upload", "push"]

STARTED = time.time()
notes = []
tasks = []


def log(text):
    print(f"== {datetime.now():%H:%M:%S} {text}", flush=True)


def run(*args, cwd=ROOT, env=None, capture=False):
    printable = " ".join(str(arg) for arg in args)
    print(f"$ {printable}", flush=True)
    result = subprocess.run(
        [str(arg) for arg in args],
        cwd=cwd,
        env={**os.environ, **(env or {})},
        text=True,
        capture_output=capture,
    )
    if result.returncode:
        detail = f"\n{result.stdout}\n{result.stderr}" if capture else ""
        raise RuntimeError(f"Failed ({result.returncode}): {printable}{detail}")
    return result.stdout.strip() if capture else None


def git(*args, cwd=ROOT):
    return run("git", *args, cwd=cwd, capture=True)


def mach(*args, config, env=None):
    run(sys.executable, "mach", *args, env={"MOZCONFIG": config, **(env or {})})


def notify(subject, text):
    token = os.environ.get("AKHI_OPS_TOKEN")
    if not token and (KEYS / "ops-token.txt").exists():
        token = (KEYS / "ops-token.txt").read_text().strip()
    if not token:
        print("No AKHI_OPS_TOKEN: no mail", flush=True)
        return
    request = urllib.request.Request(
        NOTIFY_URL,
        data=json.dumps({"subject": subject, "text": text}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(request, timeout=30).read()
    except Exception as e:
        print(f"The mail failed: {e}", flush=True)


def repos():
    return [ROOT, *(ROOT / path for path in SUBMODULES)]


def pull():
    for repo in repos():
        name = repo.relative_to(ROOT).as_posix() or "the tree"
        if git("status", "--porcelain", "--untracked-files=no", cwd=repo):
            raise RuntimeError(f"{name} has uncommitted changes: commit or stash them first")
    git("fetch", "-q", "origin", "main")
    if git("rev-parse", "--abbrev-ref", "HEAD") != "main":
        raise RuntimeError("The tree isn't on main")
    git("merge", "-q", "--ff-only", "origin/main")
    for path in SUBMODULES:
        repo = ROOT / path
        git("fetch", "-q", "origin", "main", cwd=repo)
        git("checkout", "-q", "main", cwd=repo)
        try:
            git("merge", "-q", "--ff-only", "origin/main", cwd=repo)
        except RuntimeError:
            raise RuntimeError(f"{path}: local main and origin/main have diverged, merge them first")
        notes.append(f"{path} at {git('log', '-1', '--format=%h %s', cwd=repo)}")


def set_version(version):
    run(sys.executable, TOOLS / "set_version.py", version)
    extension = ROOT / SUBMODULES[0]
    if git("status", "--porcelain", "--untracked-files=no", cwd=extension):
        git("commit", "-q", "-am", f"Version {version}", cwd=extension)
    git("add", "browser/config/akhi_version.txt", "package.json", *SUBMODULES)
    if git("diff", "--cached", "--name-only"):
        git("commit", "-q", "-m", f"AkhiBrowser {version}")


def touch_clobber(objdir, config, clobber):
    """A checkout makes CLOBBER newer than the objdir's: a real clobber when asked, else the objdir counts as clobbered."""
    if clobber:
        mach("clobber", "objdir", "--full", config=config)
    elif objdir.exists():
        (objdir / "CLOBBER").touch()


def desktop(version, final, targets):
    mach("build", config=DESKTOP_CONFIG)
    run(sys.executable, TOOLS / "build_windows.py", env={"MOZCONFIG": DESKTOP_CONFIG})
    installer = max((DESKTOP_OBJ / "dist").glob("akhibrowser-*.win64.installer.exe"), key=os.path.getmtime)
    shutil.copy2(installer, final / f"AkhiBrowser-{version}-windows-x64-setup.exe")
    if "windows" in targets:
        run(sys.executable, TOOLS / "make_update.py", "--objdir", DESKTOP_OBJ, "--keys", UPDATE_KEYS)
        update = DESKTOP_OBJ / "dist/update"
        shutil.copy2(update / f"AkhiBrowser-{version}-windows-x64.complete.mar", final)
        shutil.copy2(update / "update-WINNT_x86_64-msvc-x64.xml", final)
    if "msstore" in targets:
        run(sys.executable, TOOLS / "build_msstore.py", "--package-only", *MSSTORE_IDENTITY)


def smoke(version, final):
    out = ROOT / f"artifacts/smoke-desktop-{version}"
    work = ROOT / f"artifacts/smoke-app-{version}"
    shutil.rmtree(work, ignore_errors=True)
    shutil.rmtree(out, ignore_errors=True)
    (work / "profile").mkdir(parents=True)
    out.mkdir(parents=True)
    run(SEVEN_ZIP, "x", "-y", f"-o{work / 'app'}", final / f"AkhiBrowser-{version}-windows-x64-setup.exe", capture=True)
    browser = work / "app/core/akhibrowser.exe"
    pages = subprocess.Popen(
        [sys.executable, "-m", "http.server", "8765", "--bind", "127.0.0.1"],
        cwd=TOOLS / "smoke/pages",
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    with open(out / "browser.log", "w") as browser_log:
        app = subprocess.Popen(
            [browser, "--headless", "--no-remote", "--profile", work / "profile", "--remote-debugging-port", "9222"],
            env={**os.environ, "MOZ_REMOTE_ALLOW_SYSTEM_ACCESS": "1"},
            stdout=browser_log,
            stderr=subprocess.STDOUT,
        )
    try:
        with open(out / "run.log", "w") as run_log:
            subprocess.run(
                ["node", TOOLS / "smoke/driver.mjs", out.as_posix()],
                cwd=TOOLS / "smoke",
                env={**os.environ, "SMOKE_FAMILY": "storage"},
                stdout=run_log,
                stderr=subprocess.STDOUT,
                timeout=900,
            )
    except subprocess.TimeoutExpired:
        pass
    finally:
        app.kill()
        pages.kill()
        subprocess.run(["taskkill", "/F", "/T", "/IM", "akhibrowser.exe"], capture_output=True)
    results = (out / "run.log").read_text(errors="replace")
    print(results, flush=True)
    passed = len(re.findall(r"^ok ", results, re.MULTILINE))
    failed = [line for line in results.splitlines() if line and not line.startswith("ok ") and re.match(r"^\w+ +\d+ ", line)]
    notes.append(f"Smoke test: {passed} ok" + ("".join(f"\n  {line}" for line in failed)))
    missing = [test for test in CRITICAL_SMOKE if not re.search(rf"^ok +{re.escape(test)}", results, re.MULTILINE)]
    if missing:
        raise RuntimeError(f"Critical smoke tests failed: {', '.join(missing)} (artifacts/smoke-desktop-{version})")


def aapt():
    tools = sorted((Path.home() / ".mozbuild/android-sdk-windows/build-tools").glob("*/aapt.exe"))
    if not tools:
        raise RuntimeError("No aapt in ~/.mozbuild/android-sdk-windows/build-tools")
    return tools[-1]


def version_code(apk):
    badging = run(aapt(), "dump", "badging", apk, capture=True).splitlines()[0]
    return int(re.search(r"versionCode='(\d+)'", badging).group(1))


def android(version, final, targets):
    env = {"MOZ_BUILD_DATE": datetime.now().strftime("%Y%m%d%H%M%S")}
    mach("build", config=ANDROID_CONFIG, env=env)
    extension = ROOT / "artifacts/release-extension"
    shutil.rmtree(extension, ignore_errors=True)
    run("node", TOOLS / "merge_akhi_extension.mjs", extension)
    apks = []
    if "android" in targets:
        mach(
            "gradle",
            ":fenix:assembleRelease",
            config=ANDROID_CONFIG,
            env={**env, "AKHI_EXTENSION_DIR": extension.as_posix(), "AKHI_SIGNING_PROPERTIES": SIGNING.as_posix()},
        )
        apk = final / f"AkhiBrowser-{version}-android-arm64-v8a.apk"
        shutil.copy2(
            ANDROID_OBJ / "gradle/build/mobile/android/fenix/app/outputs/apk/release/fenix-arm64-v8a-release.apk", apk
        )
        apks.append(apk)
    if "play" in targets:
        run(sys.executable, TOOLS / "build_play.py", "--signing", SIGNING, env={"MOZCONFIG": ANDROID_CONFIG, **env})
        apks.append(ROOT / f"artifacts/play-{version}/AkhiBrowser-{version}-play-universal.apk")
    state = json.loads(STATE.read_text()) if STATE.exists() else {"versionCode": FIRST_VERSION_CODE}
    codes = {path.name: version_code(path) for path in apks}
    apk = apks[0]
    for name, code in codes.items():
        if code <= state["versionCode"]:
            raise RuntimeError(f"{name} has version code {code}, not higher than the last release's {state['versionCode']}")
    in_apk = set(zipfile.ZipFile(apk).namelist())
    missing = [
        path.relative_to(extension).as_posix()
        for path in extension.rglob("*")
        if path.is_file()
        and not path.name.startswith(".")
        and path.relative_to(extension).parts[0] != "ios"
        and f"assets/extensions/akhi/{path.relative_to(extension).as_posix()}" not in in_apk
    ]
    if missing:
        raise RuntimeError(f"Files of the extension missing in the APK: {', '.join(missing[:20])}")
    notes.append(f"Version codes: {codes}")
    return max(codes.values())


def sums(version, final):
    names = [
        f"AkhiBrowser-{version}-android-arm64-v8a.apk",
        f"AkhiBrowser-{version}-windows-x64-setup.exe",
        f"AkhiBrowser-{version}-windows-x64.complete.mar",
    ]
    lines = [f"{hashlib.sha256((final / name).read_bytes()).hexdigest()} *{name}" for name in names if (final / name).exists()]
    if not lines:
        return
    (final / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", newline="\n")


def release_files(version, final, targets=TARGETS):
    files = {
        "android": [final / f"AkhiBrowser-{version}-android-arm64-v8a.apk"],
        "windows": [
            final / f"AkhiBrowser-{version}-windows-x64-setup.exe",
            final / f"AkhiBrowser-{version}-windows-x64.complete.mar",
            final / "update-WINNT_x86_64-msvc-x64.xml",
        ],
        "play": [ROOT / f"artifacts/play-{version}/AkhiBrowser-{version}-play.aab"],
        "msstore": [ROOT / f"artifacts/msstore-{version}/AkhiBrowser-{version}-x64.msix"],
    }
    chosen = [path for target in TARGETS if target in targets for path in files[target]]
    if {"android", "windows"} & set(targets):
        chosen.append(final / "SHA256SUMS.txt")
    if "play" in targets and "android" in targets:
        chosen.append(ROOT / f"artifacts/play-{version}/AkhiBrowser-{version}-play-universal.apk")
    return chosen


def drive(version, final, targets):
    if not DRIVE.exists():
        raise RuntimeError(f"{DRIVE} isn't there: is Google Drive for desktop running?")
    old_versions = {
        match.group(1)
        for path in DRIVE.glob("AkhiBrowser-*")
        if (match := re.match(r"AkhiBrowser-(\d+\.\d+\.\d+)-", path.name)) and match.group(1) != version
    }
    if old_versions:
        previous = max(old_versions, key=lambda v: tuple(map(int, v.split("."))))
        old = DRIVE / f"akhibrowser-{previous}"
        old.mkdir(exist_ok=True)
        for path in [*DRIVE.glob("AkhiBrowser-*"), DRIVE / "SHA256SUMS.txt", DRIVE / "update-WINNT_x86_64-msvc-x64.xml"]:
            if path.is_file() and f"-{version}-" not in path.name:
                shutil.move(str(path), str(old / path.name))
    copied = [path for path in release_files(version, final, targets) if path.exists() and path.stat().st_mtime >= STARTED]
    for path in copied:
        shutil.copy2(path, DRIVE)
    notes.append(f"On Drive: {', '.join(path.name for path in copied)}")


def upload_play(version, track, release_notes):
    if not PLAY_KEY.exists():
        tasks.append(f"Upload artifacts/play-{version}/AkhiBrowser-{version}-play.aab to Google Play by hand "
                     f"(or put the service account's JSON key at {PLAY_KEY} for automatic uploads)")
        return
    aab = ROOT / f"artifacts/play-{version}/AkhiBrowser-{version}-play.aab"
    output = run("node", TOOLS / "upload_play.mjs", "--aab", aab, "--key", PLAY_KEY, "--track", track,
                 "--notes", release_notes, capture=True)
    notes.append(output)
    if track != "internal":
        tasks.append(f"Google Play: send out the draft on the {track} track in the Play Console")


def upload_msstore(version, commit):
    if not shutil.which("msstore"):
        tasks.append(f"Upload artifacts/msstore-{version}/AkhiBrowser-{version}-x64.msix to Partner Center by hand "
                     "(or install and configure the Microsoft Store Developer CLI for automatic uploads)")
        return
    msix = ROOT / f"artifacts/msstore-{version}/AkhiBrowser-{version}-x64.msix"
    run("msstore", "publish", msix, "-id", MSSTORE_ID, *([] if commit else ["--noCommit"]))
    notes.append("Microsoft Store: submission " + ("sent to certification" if commit else "made as a draft"))
    if not commit:
        tasks.append("Microsoft Store: submit the draft in Partner Center")


def upload_github(version, final, release_notes):
    files = [
        final / f"AkhiBrowser-{version}-android-arm64-v8a.apk",
        final / f"AkhiBrowser-{version}-windows-x64-setup.exe",
        final / f"AkhiBrowser-{version}-windows-x64.complete.mar",
        final / "update-WINNT_x86_64-msvc-x64.xml",
        final / "SHA256SUMS.txt",
    ]
    latest = ROOT / f"artifacts/github-{version}"
    latest.mkdir(exist_ok=True)
    for name, source in (
        ("AkhiBrowser-windows-x64-setup.exe", files[1]),
        ("AkhiBrowser-android-arm64-v8a.apk", files[0]),
    ):
        shutil.copy2(source, latest / name)
        files.append(latest / name)
    run("gh", "release", "create", f"v{version}", "--repo", "halgurdh/akhiBrowser", "--target", "main", "--latest",
        "--title", f"AkhiBrowser {version}", "--notes", release_notes or f"AkhiBrowser {version}", *files)
    notes.append(f"GitHub release v{version} published")


def linux_macos(version):
    for workflow in ("akhi-linux.yml", "akhi-macos.yml"):
        run("gh", "workflow", "run", workflow, "--repo", "halgurdh/akhiBrowser", "--ref", "main",
            "-f", f"ref=v{version}", "-f", f"release_tag=v{version}")
    notes.append("Linux and macOS are building on GitHub (a few hours): they attach themselves to the release")


def push():
    for path in SUBMODULES:
        git("push", "-q", "origin", "main", cwd=ROOT / path)
    git("push", "-q", "origin", "main")
    notes.append("Pushed main of the tree and the submodules")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("version")
    parser.add_argument("--skip", default="", help=f"Steps to leave out, separated by commas: {','.join(STEPS)}")
    parser.add_argument("--only", default="", help="Only these steps, separated by commas")
    parser.add_argument("--targets", default=",".join(TARGETS), help=f"What to build: {','.join(TARGETS)}")
    parser.add_argument("--upload", default="", help="play, msstore and/or github, separated by commas")
    parser.add_argument("--play-track", default="internal")
    parser.add_argument("--msstore-commit", action="store_true", help="Send the submission to certification")
    parser.add_argument("--notes", default="", help="Release notes for the stores and GitHub")
    parser.add_argument("--push", action="store_true")
    parser.add_argument("--linux-macos", action="store_true",
                        help="After the GitHub release, build Linux and macOS on GitHub and attach them to it")
    parser.add_argument("--clobber", action="store_true", help="Build from scratch, when CLOBBER asks for it")
    parser.add_argument("--shutdown", action="store_true", help="Shut the PC down 15 minutes after a good release")
    args = parser.parse_args()

    steps = [step for step in (args.only.split(",") if args.only else STEPS) if step not in args.skip.split(",")]
    if not args.push and "push" in steps:
        steps.remove("push")
    targets = [item for item in args.targets.split(",") if item]
    if not {"windows", "msstore"} & set(targets):
        steps = [step for step in steps if step not in ("desktop", "smoke")]
    if not {"android", "play"} & set(targets):
        steps = [step for step in steps if step != "android"]
    uploads = [item for item in args.upload.split(",") if item]
    version = args.version
    final = ROOT / f"artifacts/final-{version}"
    final.mkdir(parents=True, exist_ok=True)
    started = time.time()
    current = None
    try:
        for current in steps:
            log(current)
            if current == "pull":
                pull()
            elif current == "version":
                set_version(version)
            elif current == "desktop":
                touch_clobber(DESKTOP_OBJ, DESKTOP_CONFIG, args.clobber)
                desktop(version, final, targets)
            elif current == "smoke":
                smoke(version, final)
            elif current == "android":
                touch_clobber(ANDROID_OBJ, ANDROID_CONFIG, args.clobber)
                code = android(version, final, targets)
            elif current == "sums":
                sums(version, final)
            elif current == "drive":
                drive(version, final, targets)
            elif current == "upload":
                if "play" in uploads:
                    upload_play(version, args.play_track, args.notes)
                if "msstore" in uploads:
                    upload_msstore(version, args.msstore_commit)
                if "github" in uploads and "push" not in steps:
                    upload_github(version, final, args.notes)
            elif current == "push":
                push()
                if "github" in uploads:
                    upload_github(version, final, args.notes)
                    if args.linux_macos:
                        linux_macos(version)
        if "android" in steps:
            STATE.write_text(json.dumps({"version": version, "versionCode": code}))
    except Exception as e:
        traceback.print_exc()
        notify(
            f"AkhiBrowser {version}: the release stopped at {current}",
            f"{e}\n\nDone before it:\n" + "\n".join(notes) + "\n\nThe whole log is in the Release run on GitHub.",
        )
        sys.exit(1)
    minutes = round((time.time() - started) / 60)
    if "upload" in steps and "play" not in uploads:
        tasks.append(f"Google Play: upload artifacts/play-{version}/AkhiBrowser-{version}-play.aab (or run with play)")
    if "upload" in steps and "msstore" not in uploads:
        tasks.append(f"Microsoft Store: upload artifacts/msstore-{version}/AkhiBrowser-{version}-x64.msix")
    text = f"AkhiBrowser {version} is ready, in {minutes} minutes.\n\n" + "\n".join(notes)
    if tasks:
        text += "\n\nFor you to do:\n" + "\n".join(f"- {task}" for task in tasks)
    notify(f"AkhiBrowser {version} is ready" + (" (tasks for you)" if tasks else ""), text)
    print(text, flush=True)
    if args.shutdown:
        subprocess.run(["shutdown", "/s", "/t", "900", "/c", f"AkhiBrowser {version} is done. Cancel: shutdown /a"])


if __name__ == "__main__":
    main()
