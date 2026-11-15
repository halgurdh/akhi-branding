#!/usr/bin/env python3
"""Builds the AkhiBrowser Windows x64 installer on Linux, cross-compiled, with the extension and Premium merged and
minified, as on Windows:

    python browser/branding/akhi/tools/build_windows_cross.py [--keys <folder>]

Needs ./mach bootstrap and the Rust target x86_64-pc-windows-msvc; configure downloads the rest. Writes
dist/release/AkhiBrowser-windows-x64-setup.exe in the objdir. With --keys, also the signed update (make_update.py).
The installer isn't Authenticode signed.
"""

import argparse
import sys

from desktop_build import ROOT, build_and_package, make_update, release_copy

OBJDIR = ROOT / "obj-akhi-windows-x64"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--keys", help="NSS database of the update signing key")
    args = parser.parse_args()
    if not sys.platform.startswith("linux"):
        sys.exit("This cross-compiles on Linux; on Windows, use build_windows.py")

    build_and_package("akhi-windows-x64-cross", OBJDIR)
    installers = sorted(
        [*(OBJDIR / "dist").glob("*.installer.exe"), *(OBJDIR / "dist/install/sea").glob("*.exe")],
        key=lambda p: p.stat().st_mtime,
    )
    if not installers:
        sys.exit(f"No installer in {OBJDIR / 'dist'}")
    print(release_copy(installers[-1], "AkhiBrowser-windows-x64-setup.exe"))
    zips = sorted((OBJDIR / "dist").glob("akhibrowser-*.zip"), key=lambda p: p.stat().st_mtime)
    if zips:
        print(release_copy(zips[-1], "AkhiBrowser-windows-x64.zip"))
    make_update(OBJDIR, args.keys)


if __name__ == "__main__":
    main()
