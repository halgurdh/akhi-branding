#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Makes the signed update of a release of the desktop browser, after ./mach package.

    python browser/branding/akhi/tools/make_update.py --objdir obj-akhi-desktop --keys <folder>

Writes to <objdir>/dist/update/ a .mar and the update-<BUILD_TARGET>.xml the browser asks for: upload both to the
GitHub release. <folder> has the NSS database of the signing key, and never goes in a repository.
"""

import argparse
import configparser
import hashlib
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
    # Windows adds the architecture it runs on to %BUILD_TARGET%: see the ABI getter of UpdateUtils.sys.mjs
    architecture = "aarch64" if abi.startswith("aarch64") else "x64"
    return f"{os_target}_{abi}-{architecture}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--objdir", required=True, type=Path)
    parser.add_argument("--keys", required=True, type=Path)
    parser.add_argument("--base-url", help="Where the .mar will be, instead of the GitHub release (for a test)")
    parser.add_argument("--display-version", help="Instead of browser/config/akhi_version.txt (for a test)")
    args = parser.parse_args()

    dist = args.objdir.resolve() / "dist"
    package = dist / "akhibrowser"
    if not package.is_dir():
        sys.exit(f"No {package}: run ./mach package first")
    version = args.display_version or release_version()

    ini = configparser.ConfigParser()
    ini.read(package / "application.ini", encoding="utf-8")
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

    (package / "precomplete").touch()
    environment = dict(
        os.environ,
        MAR=(dist / "host/bin/mar.exe").as_posix(),
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

    environment = dict(os.environ, PATH=f"{dist / 'bin'}{os.pathsep}{os.environ['PATH']}")
    signmar = str(dist / "bin/signmar.exe")
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
    base = args.base_url or f"{REPOSITORY}/releases/download/v{version}"
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n<updates>\n'
        f'  <update type="minor" displayVersion={quoteattr(version)} appVersion={quoteattr(app_version)}'
        f" platformVersion={quoteattr(platform_version)} buildID={quoteattr(build_id)}"
        f" detailsURL={quoteattr(f'{REPOSITORY}/releases/tag/v{version}')}>\n"
        f'    <patch type="complete" URL={quoteattr(f"{base}/{name}")} hashFunction="sha512"'
        f' hashValue="{hashlib.sha512(data).hexdigest()}" size="{len(data)}"/>\n'
        "  </update>\n</updates>\n"
    )
    (out / f"update-{target}.xml").write_text(xml, encoding="utf-8")
    print(f"{signed}\n{out / f'update-{target}.xml'}")


if __name__ == "__main__":
    main()
