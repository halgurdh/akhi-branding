#!/usr/bin/env python3
"""Builds the AkhiBrowser Windows x64 installer on Linux, cross-compiled, with the extension and Premium merged and
minified, as on Windows:

    python browser/branding/akhi/tools/build_windows_cross.py [--keys <folder>]

Needs ./mach bootstrap and the Rust target x86_64-pc-windows-msvc; configure downloads the rest. Writes
dist/release/AkhiBrowser-windows-x64-setup.exe in the objdir, and the update: signed with --keys (make_update.py),
else unsigned with update-info.json, for sign_mar.py.
The installer isn't Authenticode signed.
"""

import argparse
import shutil
import sys

from desktop_build import BRANDING, ROOT, build_and_package, make_update, release_copy, run

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
    if args.keys:
        make_update(OBJDIR, args.keys)
    else:
        run([sys.executable, str(BRANDING / "tools/make_update.py"), "--objdir", str(OBJDIR), "--unsigned"])
        release = OBJDIR / "dist/release"
        for path in (OBJDIR / "dist/update").iterdir():
            if path.is_file():
                shutil.copyfile(path, release / path.name)
                print(release / path.name)


if __name__ == "__main__":
    main()
