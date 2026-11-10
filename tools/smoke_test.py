#!/usr/bin/env python3
"""Starts a built AkhiBrowser and screenshots a few pages, each in a new profile: an ordinary site, an adult site, a
haram search and a Google search. Look at the screenshots: the second must show the block page, the third a question or
the block page, the fourth safe=active.

    python smoke_test.py --binary <akhibrowser or AkhiBrowser.app/Contents/MacOS/akhibrowser> --out <folder>

Fails when the browser doesn't start or writes no screenshot. On Linux without a display, run it under xvfb-run.
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

PAGES = {
    "1-ordinary-site": "https://www.wikipedia.org/",
    "2-adult-site": "https://www.pornhub.com/",
    "3-haram-search": "https://www.google.com/search?q=buy+beer",
    "4-google-search": "https://www.google.com/search?q=test",
}


def screenshot(binary, url, out):
    with tempfile.TemporaryDirectory() as profile:
        command = [
            str(binary), "--headless", "--no-remote", "--profile", profile,
            "--window-size", "1280,900", "--screenshot", str(out), url,
        ]
        try:
            subprocess.run(command, timeout=180, check=False, capture_output=True)
        except subprocess.TimeoutExpired:
            print(f"Timed out: {url}")
    return out.is_file() and out.stat().st_size > 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--url", action="append", help="Instead of the default pages (e.g. a file:// page offline)")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    version = subprocess.run([str(args.binary), "--version"], capture_output=True, text=True, timeout=60)
    print(version.stdout.strip() or version.stderr.strip())
    if version.returncode != 0:
        sys.exit("The browser doesn't start")

    pages = {f"page-{i}": url for i, url in enumerate(args.url, 1)} if args.url else PAGES
    failed = [name for name, url in pages.items() if not screenshot(args.binary, url, args.out / f"{name}.png")]
    for name in pages:
        print(f"{name}: {'missing' if name in failed else 'ok'}")
    if failed:
        sys.exit(f"No screenshot of {', '.join(failed)}")


if __name__ == "__main__":
    main()
