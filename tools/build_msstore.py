#!/usr/bin/env python3
# Copyright (c) 2026 the AkhiBrowser authors. All rights reserved.
"""Builds the Microsoft Store package (MSIX) and checks it.

From the root of the tree, with the values of Partner Center's Product identity page:

    python browser/branding/akhi/tools/build_msstore.py --identity-name <Package/Identity/Name> \
        --publisher "CN=..." --publisher-display-name "..."

Writes artifacts/msstore-<version>/AkhiBrowser-<version>-x64.msix. Microsoft signs it when it's submitted. Without the
three values, placeholders make a package to look at, which Partner Center refuses.

--package-only packs the current build again, without building it.
"""

import argparse
import configparser
import io
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[4]
MOZCONFIG = "browser/branding/akhi/mozconfigs/akhi-desktop"
OBJDIR = ROOT / "obj-akhi-desktop"
EXTENSION = ROOT / "browser/extensions/akhi"
BUILT_EXTENSION = OBJDIR / "dist/bin/browser/chrome/browser/builtin-addons/akhi"
PLACEHOLDER_IDENTITY = "AkhiBrowser.AkhiBrowser"
PLACEHOLDER_PUBLISHER = "CN=AkhiBrowser"
PLACEHOLDER_DISPLAY_NAME = "AkhiBrowser"

failures = []


def check(is_ok, text):
    print(("ok    " if is_ok else "FAIL  ") + text)
    if not is_ok:
        failures.append(text)


def run(command, env=None, shell=False):
    subprocess.run(command, check=True, cwd=ROOT, env=env, shell=shell)


def build(env):
    run([sys.executable, "mach", "build", "faster"], env=env)
    with tempfile.TemporaryDirectory() as temp:
        minified = Path(temp) / "extension"
        run(
            ["node", str(ROOT / "browser/branding/akhi/tools/merge_akhi_extension.mjs"), str(minified)],
            shell=sys.platform == "win32",
        )
        for source in minified.rglob("*"):
            if source.is_file():
                target = BUILT_EXTENSION / source.relative_to(minified)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.unlink(missing_ok=True)
                target.write_bytes(source.read_bytes())
    run([sys.executable, "mach", "package"], env=env)


def check_package(msix, version, identity, publisher):
    with zipfile.ZipFile(msix) as package:
        names = package.namelist()
        manifest = package.read("AppxManifest.xml").decode("utf8")
        distribution = next(n for n in names if n.endswith("distribution/distribution.ini"))
        ini = configparser.RawConfigParser()
        ini.optionxform = str
        ini.read_string(package.read(distribution).decode("utf8"))
        omni = next(n for n in names if n.endswith("browser/omni.ja"))
        with zipfile.ZipFile(io.BytesIO(package.read(omni))) as chrome:
            updates = next(n for n in chrome.namelist() if n.endswith("builtin-addons/akhi/lib/updates.js"))
            updates_js = chrome.read(updates).decode("utf8")

    tag = re.search(r"<Identity ([^>]*)/>", manifest)[1]
    check(f'Name="{identity}"' in tag, f"identity {identity}")
    check(f'Publisher="{publisher}"' in tag, f"publisher {publisher}")
    check(f'Version="{version}"' in tag, f"version {version}: the Store needs the last number to be 0")
    check('ProcessorArchitecture="x64"' in tag, "x64")
    # Mozilla.MsixComServer is the name of a class in the browser's own code, which no one sees
    visible = re.sub(r"<!--.*?-->|Mozilla\.MsixComServer", "", manifest, flags=re.S)
    check("Mozilla" not in visible, "no Mozilla in the manifest")
    check('Name="runFullTrust"' in manifest, "runFullTrust is declared: justify it at submission")

    executables = set(re.findall(r'Executable="([^"]+\.exe)"', manifest))
    lowered = {unquote(n).lower() for n in names}
    test_programs = [n for n in lowered if re.search(r"/(test[a-z]|.*server\.exe|smokedmd)[^/]*\.exe$", n)]
    check(not test_programs, f"no test programs in the package {test_programs[:3] or ''}")
    missing = [e for e in executables if e.replace("\\", "/").lower() not in lowered]
    check(not missing, f"the manifest's programs are in the package {missing or ''}")
    check(ini["Preferences"].get("extensions.akhi.storeBuild") == "true", "the GitHub update notice is off")
    check("storeBuild" in updates_js, "the built-in extension is the current one")
    check(any(n.startswith("Assets/") for n in names), "logos are in the package")
    print(f"      size {msix.stat().st_size / 1e6:.1f} MB")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--identity-name", default=PLACEHOLDER_IDENTITY)
    parser.add_argument("--publisher", default=PLACEHOLDER_PUBLISHER)
    parser.add_argument("--publisher-display-name", default=PLACEHOLDER_DISPLAY_NAME)
    parser.add_argument("--package-only", action="store_true")
    parser.add_argument("--objdir", type=Path, help="Instead of obj-akhi-desktop, like the cross build's on GitHub")
    parser.add_argument("--mozconfig", help="The mozconfig of that objdir")
    args = parser.parse_args()
    global OBJDIR, MOZCONFIG
    if args.objdir:
        OBJDIR = args.objdir.resolve()
    if args.mozconfig:
        MOZCONFIG = args.mozconfig

    if "." not in args.identity_name:
        sys.exit("--identity-name looks like Vendor.Name, as Partner Center shows it")
    vendor, name = args.identity_name.split(".", 1)

    version = (ROOT / "browser/config/akhi_version.txt").read_text().strip()
    out = ROOT / "artifacts" / f"msstore-{version}"
    out.mkdir(parents=True, exist_ok=True)
    msix = out / f"AkhiBrowser-{version}-x64.msix"
    store_version = f"{version}.0"
    env = {**os.environ, "MOZCONFIG": MOZCONFIG}

    if not args.package_only:
        build(env)
    run(
        [
            sys.executable,
            "mach",
            "repackage",
            "msix",
            "--input",
            str(next((OBJDIR / "dist").glob("akhibrowser-*.win64.zip"))),
            "--channel",
            "official",
            "--arch",
            "x86_64",
            "--version",
            store_version,
            "--vendor",
            vendor,
            "--identity-name",
            name,
            "--publisher",
            args.publisher,
            "--publisher-display-name",
            args.publisher_display_name,
            "--output",
            str(msix),
        ],
        env=env,
    )

    check_package(msix, store_version, args.identity_name, args.publisher)
    is_placeholder = args.identity_name == PLACEHOLDER_IDENTITY
    print(f"\n{msix}")
    if failures:
        sys.exit(f"\n{len(failures)} check(s) failed")
    if is_placeholder:
        print("\nBuilt with placeholders: build again with the values from Partner Center before submitting.")


if __name__ == "__main__":
    main()
