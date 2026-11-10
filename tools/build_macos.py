#!/usr/bin/env python3
"""Builds AkhiBrowser for macOS: the .dmg with the extension and Premium merged and minified.

    python browser/branding/akhi/tools/build_macos.py [--arch arm64|x64] [--sign-identity <identity>]
        [--notary-profile <profile>] [--keys <folder>]

Run on a Mac with Xcode, after ./mach bootstrap. Without --sign-identity the app is only ad-hoc signed: it runs on the
Mac that built it, and Gatekeeper blocks it on others. --sign-identity is a "Developer ID Application: ..." certificate
in the keychain (security find-identity -v -p codesigning). --notary-profile is a profile saved once with
xcrun notarytool store-credentials; the .dmg is then notarized and stapled. With --keys, also makes the signed update
(see make_update.py), from the signed app when there is one. Writes dist/release/AkhiBrowser-macos-<arch>.dmg in the
objdir.
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

from desktop_build import BRANDING, ROOT, build_and_package, release_copy, run


def sign(dmg, identity, notary_profile, out, work):
    mount = work / "mount"
    stage = work / "stage"
    mount.mkdir()
    run(["hdiutil", "attach", "-nobrowse", "-readonly", "-mountpoint", str(mount), str(dmg)])
    try:
        run(["ditto", str(mount), str(stage)])
    finally:
        run(["hdiutil", "detach", str(mount)])
    app = stage / "AkhiBrowser.app"
    run(
        [
            sys.executable, "mach", "macos-sign", "-a", str(app), "-s", identity,
            "-e", "production-without-restricted", "-c", "release",
        ]
    )
    run(["codesign", "--verify", "--deep", "--strict", str(app)])
    out.parent.mkdir(exist_ok=True)
    run(["hdiutil", "create", "-volname", "AkhiBrowser", "-srcfolder", str(stage), "-ov", "-format", "UDZO", str(out)])
    run(["codesign", "--sign", identity, "--timestamp", str(out)])
    if notary_profile:
        run(["xcrun", "notarytool", "submit", str(out), "--keychain-profile", notary_profile, "--wait"])
        run(["xcrun", "stapler", "staple", str(out)])
        run(["spctl", "--assess", "--type", "open", "--context", "context:primary-signature", "-v", str(out)])
    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--arch", choices=["arm64", "x64"], default="arm64")
    parser.add_argument("--sign-identity")
    parser.add_argument("--notary-profile")
    parser.add_argument("--keys", help="NSS database of the update signing key")
    args = parser.parse_args()
    if sys.platform != "darwin":
        sys.exit("Build for macOS on a Mac with Xcode")
    if args.notary_profile and not args.sign_identity:
        sys.exit("--notary-profile needs --sign-identity: Apple only notarizes signed apps")

    objdir = ROOT / f"obj-akhi-macos-{args.arch}"
    build_and_package(f"akhi-macos-{args.arch}", objdir)
    dmgs = sorted((objdir / "dist").glob("akhibrowser-*.dmg"), key=lambda p: p.stat().st_mtime)
    if not dmgs:
        sys.exit(f"No akhibrowser-*.dmg in {objdir / 'dist'}")
    name = f"AkhiBrowser-macos-{args.arch}.dmg"

    with tempfile.TemporaryDirectory() as temp:
        package = None
        if args.sign_identity:
            out = objdir / "dist/release" / name
            package = sign(dmgs[-1], args.sign_identity, args.notary_profile, out, Path(temp))
            print(out)
        else:
            print(release_copy(dmgs[-1], name))
        if args.keys:
            command = [
                sys.executable, str(BRANDING / "tools/make_update.py"),
                "--objdir", str(objdir), "--keys", args.keys,
            ]
            if package:
                command += ["--package", str(package)]
            subprocess.run(command, check=True, cwd=ROOT)


if __name__ == "__main__":
    main()
