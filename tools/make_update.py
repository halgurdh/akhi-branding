#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Makes the signed update of a release of the desktop browser, after ./mach package.

    python browser/branding/akhi/tools/make_update.py --objdir obj-akhi-desktop --keys <folder>

Writes to <objdir>/dist/update/ a .mar and the update-<BUILD_TARGET>.xml the browser asks for: upload both to the
GitHub release. <folder> has the NSS database of the signing key, and never goes in a repository.
With --unsigned instead of --keys (a build on GitHub), it writes the .mar unsigned and update-info.json, for
sign_mar.py to sign and to write the .xml.
"""

import argparse
import configparser
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from xml.sax.saxutils import quoteattr

ROOT = Path(__file__).resolve().parents[4]
REPOSITORY = "https://github.com/halgurdh/akhiBrowser"
MAR_CHANNEL_ID = "akhibrowser-release"
KEY_NICKNAME = "akhi-update-primary"
PLATFORMS = {
    "WINNT_x86_64-msvc-x64": "windows-x64",
    "WINNT_aarch64-msvc-aarch64": "windows-arm64",
    "Darwin_aarch64-gcc3": "macos-arm64",
    "Darwin_x86_64-gcc3": "macos-x64",
    "Linux_x86_64-gcc3": "linux-x64",
    "Linux_aarch64-gcc3": "linux-arm64",
}


def release_version():
    version = (ROOT / "browser/config/akhi_version.txt").read_text().strip()
    extension = (ROOT / "browser/extensions/akhi/lib/updates.js").read_text(encoding="utf-8")
    found = re.search(r'CURRENT_VERSION = "([^"]+)"', extension)
    if not found or found.group(1) != version:
        sys.exit(
            f"browser/config/akhi_version.txt says {version}, CURRENT_VERSION in lib/updates.js says "
            f"{found and found.group(1)}: they must be the same"
        )
    return version


def build_target(dist):
    substs = (dist.parent / "config/autoconf.mk").read_text(encoding="utf-8", errors="replace")
    os_target = re.search(r"^OS_TARGET\s*=\s*(\S+)", substs, re.M).group(1)
    abi = re.search(r"^TARGET_XPCOM_ABI\s*=\s*(\S+)", substs, re.M).group(1)
    if os_target != "WINNT":
        return f"{os_target}_{abi}"
    # Windows adds the architecture it runs on to %BUILD_TARGET%: see the ABI getter of UpdateUtils.sys.mjs
    architecture = "aarch64" if abi.startswith("aarch64") else "x64"
    return f"{os_target}_{abi}-{architecture}"


def tool(directory, name):
    path = directory / (f"{name}.exe" if sys.platform == "win32" else name)
    if not path.is_file():
        sys.exit(f"No {path}: build with --enable-updater")
    return path


def update_xml(version, app_version, platform_version, build_id, name, data, base_url=None):
    base = base_url or f"{REPOSITORY}/releases/download/v{version}"
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n<updates>\n'
        f'  <update type="minor" displayVersion={quoteattr(version)} appVersion={quoteattr(app_version)}'
        f" platformVersion={quoteattr(platform_version)} buildID={quoteattr(build_id)}"
        f" detailsURL={quoteattr(f'{REPOSITORY}/releases/tag/v{version}')}>\n"
        f'    <patch type="complete" URL={quoteattr(f"{base}/{name}")} hashFunction="sha512"'
        f' hashValue="{hashlib.sha512(data).hexdigest()}" size="{len(data)}"/>\n'
        "  </update>\n</updates>\n"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--objdir", required=True, type=Path)
    keys = parser.add_mutually_exclusive_group(required=True)
    keys.add_argument("--keys", type=Path)
    keys.add_argument("--unsigned", action="store_true", help="Leave the .mar to sign_mar.py")
    parser.add_argument("--base-url", help="Where the .mar will be, instead of the GitHub release (for a test)")
    parser.add_argument("--display-version", help="Instead of browser/config/akhi_version.txt (for a test)")
    parser.add_argument(
        "--package",
        type=Path,
        help="The app to update to, instead of the one ./mach package made (on macOS: the signed AkhiBrowser.app)",
    )
    args = parser.parse_args()

    dist = args.objdir.resolve() / "dist"
    package = dist / "akhibrowser"
    if sys.platform == "darwin":
        package = package / "AkhiBrowser.app"
    package = args.package.resolve() if args.package else package
    if not package.is_dir():
        sys.exit(f"No {package}: run ./mach package first")
    resources = package / "Contents/Resources" if package.suffix == ".app" else package
    version = args.display_version or release_version()

    ini = configparser.ConfigParser()
    ini.read(resources / "application.ini", encoding="utf-8")
    app_version = ini["App"]["Version"]
    build_id = ini["App"]["BuildID"]
    platform_version = ini["Gecko"]["MaxVersion"] if "Gecko" in ini else app_version
    target = build_target(dist)
    platform = PLATFORMS.get(target, target)

    out = dist / "update"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    name = f"AkhiBrowser-{version}-{platform}.complete.mar"
    unsigned = out / f"{name}.unsigned"
    signed = out / name

    (resources / "precomplete").touch()
    environment = dict(
        os.environ,
        MAR=tool(dist / "host/bin", "mar").as_posix(),
        MOZ_PRODUCT_VERSION=app_version,
        MAR_CHANNEL_ID=MAR_CHANNEL_ID,
        MOZ_FULL_PRODUCT_VERSION=app_version,
    )
    bash = shutil.which("bash") or "bash"
    subprocess.run(
        [
            bash,
            "tools/update-packaging/make_full_update.sh",
            unsigned.as_posix(),
            package.as_posix(),
            "akhibrowser",
        ],
        cwd=ROOT,
        env=environment,
        check=True,
    )

    if args.unsigned:
        info = {
            "name": name,
            "version": version,
            "app_version": app_version,
            "platform_version": platform_version,
            "build_id": build_id,
            "target": target,
        }
        (out / "update-info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
        print(f"{unsigned}\n{out / 'update-info.json'}")
        return

    libraries = str(dist / "bin")
    environment = dict(
        os.environ,
        PATH=f"{libraries}{os.pathsep}{os.environ['PATH']}",
        LD_LIBRARY_PATH=libraries,
        DYLD_LIBRARY_PATH=libraries,
    )
    signmar = str(tool(dist / "bin", "signmar"))
    subprocess.run(
        [signmar, "-d", str(args.keys), "-n", KEY_NICKNAME, "-s", str(unsigned), str(signed)],
        env=environment,
        check=True,
    )
    subprocess.run(
        [signmar, "-D", str(ROOT / "browser/branding/akhi/update/primary.der"), "-v", str(signed)],
        env=environment,
        check=True,
    )
    unsigned.unlink()

    data = signed.read_bytes()
    xml = update_xml(version, app_version, platform_version, build_id, name, data, args.base_url)
    (out / f"update-{target}.xml").write_text(xml, encoding="utf-8")
    print(f"{signed}\n{out / f'update-{target}.xml'}")


if __name__ == "__main__":
    main()
