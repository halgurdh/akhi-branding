#!/usr/bin/env python3
"""Starts a built AkhiBrowser with a new profile and checks what the extension does, as a user would see it: an
ordinary site opens, an adult site and its subdomain go to the block page, a haram search is blocked and a Google
search gets SafeSearch. It drives the browser over WebDriver BiDi (smoke_bidi.mjs, needs node), after the extension has
started, and fails when a check fails. Screenshots only of the ordinary page.

    python smoke_test.py --binary <akhibrowser or AkhiBrowser.app/Contents/MacOS/akhibrowser> --out <folder>
"""

import argparse
import json
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

PAGES = [
    {"name": "1-ordinary-site", "url": "https://www.wikipedia.org/", "screenshot": True},
    {"name": "2-adult-site", "url": "https://www.pornhub.com/", "screenshot": False},
    {"name": "3-adult-subdomain", "url": "https://fr.pornhub.com/", "screenshot": False},
    {"name": "4-haram-search", "url": "https://www.google.com/search?q=buy+beer", "screenshot": False},
    {"name": "5-google-search", "url": "https://www.google.com/search?q=test", "screenshot": False},
]


def check(name, url):
    """Whether the tab ended where it should, and what it should have been."""
    blocked = url.startswith("moz-extension:") and "blocked" in url
    if name == "1-ordinary-site":
        return "wikipedia.org" in url, "Wikipedia"
    if name in ("2-adult-site", "3-adult-subdomain", "4-haram-search"):
        return blocked, "the block page"
    return "google." in url and "safe=active" in url, "Google with safe=active"


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)

    version = subprocess.run([str(args.binary), "--version"], capture_output=True, text=True, timeout=60)
    print(version.stdout.strip() or version.stderr.strip())
    if version.returncode != 0:
        sys.exit("The browser doesn't start")

    port = free_port()
    with tempfile.TemporaryDirectory() as profile:
        browser = subprocess.Popen(
            [
                str(args.binary), "--headless", "--no-remote", "--profile", profile,
                "--window-size", "1280,900", "--remote-debugging-port", str(port),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            driver = subprocess.run(
                ["node", str(Path(__file__).with_name("smoke_bidi.mjs")), str(port), str(out), json.dumps(PAGES)],
                capture_output=True,
                text=True,
                timeout=420,
            )
        finally:
            browser.terminate()
            try:
                browser.wait(timeout=30)
            except subprocess.TimeoutExpired:
                browser.kill()
    if driver.returncode != 0:
        sys.exit(f"Couldn't drive the browser: {driver.stderr.strip()[-500:]}")

    results = json.loads(driver.stdout.strip().splitlines()[-1])
    failed = []
    for result in results:
        ok, expected = check(result["name"], result["url"])
        # the URL of a blocked page only, never of an adult page that loaded
        shown = result["url"] if ok or not result["name"].startswith(("2-", "3-")) else "(the page itself)"
        print(f"{result['name']}: {'ok' if ok else 'FAILED'}, expected {expected}, got {shown}")
        if not ok:
            failed.append(result["name"])
    if failed:
        sys.exit(f"Failed: {', '.join(failed)}")


if __name__ == "__main__":
    main()
