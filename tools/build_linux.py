#!/usr/bin/env python3
"""Builds AkhiBrowser for Linux: the .tar.xz with the extension and Premium merged and minified.

    python browser/branding/akhi/tools/build_linux.py [--arch x64|arm64] [--keys <folder>]

Run on a Linux PC (or WSL2) with the same processor, after ./mach bootstrap. With --keys, also makes the signed update
(see make_update.py). Writes dist/release/AkhiBrowser-linux-<arch>.tar.xz in the objdir.
"""

import argparse
import sys

from desktop_build import ROOT, build_and_package, make_update, release_copy


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--arch", choices=["x64", "arm64"], default="x64")
    parser.add_argument("--keys", help="NSS database of the update signing key")
    args = parser.parse_args()
    if not sys.platform.startswith("linux"):
        sys.exit("Build for Linux on Linux (WSL2 works on Windows)")

    objdir = ROOT / f"obj-akhi-linux-{args.arch}"
    build_and_package(f"akhi-linux-{args.arch}", objdir)
    archives = sorted((objdir / "dist").glob("akhibrowser-*.tar.xz"), key=lambda p: p.stat().st_mtime)
    if not archives:
        sys.exit(f"No akhibrowser-*.tar.xz in {objdir / 'dist'}")
    print(release_copy(archives[-1], f"AkhiBrowser-linux-{args.arch}.tar.xz"))
    make_update(objdir, args.keys)


if __name__ == "__main__":
    main()
