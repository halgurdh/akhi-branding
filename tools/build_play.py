#!/usr/bin/env python3
# Copyright (c) 2026 the AkhiBrowser authors. All rights reserved.
"""Builds the Google Play release and checks it for what Play would refuse.

From the root of the tree, after `./mach build` with the akhi-android-arm64 config:

    python browser/branding/akhi/tools/build_play.py --signing <signing.properties>

Writes to artifacts/play-<version>/:
    AkhiBrowser-<version>-play.aab            what to upload to the Play Console
    AkhiBrowser-<version>-play-universal.apk  the same build, to install and test locally: never upload it

--check-only checks the files of an earlier build again.
"""

import argparse
import configparser
import hashlib
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
MOZCONFIG = "browser/branding/akhi/mozconfigs/akhi-android-arm64"
OBJDIR = ROOT / "obj-akhi-android-arm64"
EXTENSION = ROOT / "browser/extensions/akhi"
BUNDLE = OBJDIR / "gradle/build/mobile/android/fenix/app/outputs/bundle/release/fenix-release.aab"
PACKAGE = "org.akhibrowser"
BUNDLETOOL_VERSION = "1.18.3"
BUNDLETOOL_URL = (
    f"https://github.com/google/bundletool/releases/download/{BUNDLETOOL_VERSION}/bundletool-all-{BUNDLETOOL_VERSION}.jar"
)
BUNDLETOOL_SHA256 = "a099cfa1543f55593bc2ed16a70a7c67fe54b1747bb7301f37fdfd6d91028e29"

FORBIDDEN_PERMISSIONS = {
    "com.google.android.gms.permission.AD_ID",
    "com.adjust.preinstall.READ_PERMISSION",
    "android.permission.REQUEST_INSTALL_PACKAGES",
}
# forms in the Play Console that these permissions need: see browser/branding/akhi/play/CONSOLE.md
DECLARED_PERMISSIONS = {
    "android.permission.QUERY_ALL_PACKAGES",
    "android.permission.FOREGROUND_SERVICE_DATA_SYNC",
    "android.permission.FOREGROUND_SERVICE_MEDIA_PLAYBACK",
    "android.permission.FOREGROUND_SERVICE_SPECIAL_USE",
    "android.permission.ACCESS_FINE_LOCATION",
    "android.permission.ACCESS_COARSE_LOCATION",
    "android.permission.CAMERA",
    "android.permission.RECORD_AUDIO",
}
MIN_TARGET_SDK = 36
PAGE_SIZE = 16384
MAX_DOWNLOAD_BYTES = 200 * 1000 * 1000

failures = []


def check(is_ok, text):
    print(("ok    " if is_ok else "FAIL  ") + text)
    if not is_ok:
        failures.append(text)


def sdk_tool(relative):
    state = Path(os.environ.get("MOZBUILD_STATE_PATH", Path.home() / ".mozbuild"))
    names = ("android-sdk-windows", "android-sdk-linux", "android-sdk-macosx")
    found = [state / name for name in names if (state / name / "build-tools").is_dir()]
    sdk = found[0] if found else Path(os.environ["ANDROID_HOME"])
    tools = sorted((sdk / "build-tools").iterdir(), key=lambda p: [int(n) for n in p.name.split(".")])
    return tools[-1] / relative


def java_home():
    if os.environ.get("JAVA_HOME"):
        return Path(os.environ["JAVA_HOME"])
    return sorted((Path.home() / ".mozbuild/jdk").glob("jdk-*"))[-1]


def java():
    return str(java_home() / "bin/java")


def bundletool():
    jar = Path.home() / f".mozbuild/bundletool/bundletool-all-{BUNDLETOOL_VERSION}.jar"
    if not jar.exists():
        jar.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(BUNDLETOOL_URL) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != BUNDLETOOL_SHA256:
            sys.exit("The bundletool download doesn't have the expected hash")
        jar.write_bytes(data)
    return str(jar)


def read_signing(path):
    parser = configparser.RawConfigParser()
    parser.optionxform = str
    parser.read_string("[s]\n" + Path(path).read_text(encoding="utf8"))
    return dict(parser["s"])


def run(command, **kwargs):
    return subprocess.run(command, check=True, cwd=ROOT, **kwargs)


def output(command):
    return subprocess.run(command, check=True, capture_output=True, text=True, cwd=ROOT).stdout


def build(signing_path, work):
    minified = work / "extension"
    run(
        ["node", str(ROOT / "browser/branding/akhi/tools/merge_akhi_extension.mjs"), str(minified)],
        shell=sys.platform == "win32",
    )
    env = {
        **os.environ,
        "MOZCONFIG": MOZCONFIG,
        "AKHI_PLAY_STORE": "1",
        "AKHI_SIGNING_PROPERTIES": str(Path(signing_path).resolve()),
        "AKHI_EXTENSION_DIR": str(minified),
    }
    run([sys.executable, "mach", "gradle", ":fenix:bundleRelease"], env=env)


def signing_args(signing, work):
    # in files of the temporary folder, so they aren't on a command line other programs can read, or in a traceback
    store_password = work / "store-password"
    key_password = work / "key-password"
    store_password.write_text(signing["storePassword"], encoding="utf8")
    key_password.write_text(signing["keyPassword"], encoding="utf8")
    return [
        f"--ks={signing['storeFile']}",
        f"--ks-pass=file:{store_password}",
        f"--ks-key-alias={signing['keyAlias']}",
        f"--key-pass=file:{key_password}",
    ]


def make_apks(aab, signing, work):
    """The universal APK and the size of the download of each device, both from the bundle itself."""
    tool = [java(), "-jar", bundletool()]
    per_device = work / "device.apks"
    run(tool + ["build-apks", f"--bundle={aab}", f"--output={per_device}", "--overwrite"] + signing_args(signing, work))
    universal = work / "universal.apks"
    run(
        tool
        + ["build-apks", f"--bundle={aab}", f"--output={universal}", "--mode=universal", "--overwrite"]
        + signing_args(signing, work)
    )
    size = output(tool + ["get-size", "total", f"--apks={per_device}"]).splitlines()[-1]
    with zipfile.ZipFile(universal) as apks:
        apks.extract("universal.apk", work)
    return work / "universal.apk", int(size.split(",")[1])


def page_alignments(data):
    """The alignments of the loaded segments of a 64-bit ELF file."""
    phoff = struct.unpack_from("<Q", data, 32)[0]
    phentsize, phnum = struct.unpack_from("<HH", data, 54)
    aligns = set()
    for index in range(phnum):
        at = phoff + index * phentsize
        if struct.unpack_from("<I", data, at)[0] == 1:
            aligns.add(struct.unpack_from("<Q", data, at + 48)[0])
    return aligns


def check_bundle(aab):
    with zipfile.ZipFile(aab) as bundle:
        names = bundle.namelist()
    abis = {n.split("/")[2] for n in names if n.startswith("base/lib/")}
    check(abis == {"arm64-v8a"}, f"only the ABI Gecko is built for: {sorted(abis)}")
    check(any(n.endswith("arm64-v8a/libxul.so") for n in names), "Gecko is in the bundle")
    check("BUNDLE-METADATA/com.android.tools.build.obfuscation/proguard.map" in names, "R8 mapping is in the bundle")


def check_apk(apk):
    with zipfile.ZipFile(apk) as package:
        libs = [n for n in package.namelist() if n.endswith(".so")]
        wrong = []
        for name in libs:
            with package.open(name) as lib:
                bad = [a for a in page_alignments(lib.read()) if a < PAGE_SIZE]
            if bad:
                wrong.append(name)
        code = b"".join(package.read(n) for n in package.namelist() if n.endswith(".dex"))
    check(not wrong, f"{len(libs)} native libraries support 16 KB pages {wrong or ''}")
    check(b"releases/latest" not in code, "no reference to GitHub releases left in the app's code")

    aapt = sdk_tool("aapt2.exe" if sys.platform == "win32" else "aapt2")
    badging = output([str(aapt), "dump", "badging", str(apk)])
    package_line = re.search(r"package: name='([^']+)' versionCode='(\d+)' versionName='([^']*)'", badging)
    check(package_line and package_line[1] == PACKAGE, f"package {package_line[1]}")
    version = (ROOT / "browser/config/akhi_version.txt").read_text().strip()
    check(package_line[3] == version, f"version name {package_line[3]}")
    print(f"      version code {package_line[2]}: must be higher than the last one uploaded")
    target = int(re.search(r"targetSdkVersion:'(\d+)'", badging)[1])
    check(target >= MIN_TARGET_SDK, f"target SDK {target}")
    check("application-debuggable" not in badging, "not debuggable")
    check("testOnly" not in badging, "not test-only")
    label = re.search(r"application-label:'([^']*)'", badging)[1]
    check(label == "AkhiBrowser", f"app name {label}")

    permissions = set(re.findall(r"name='([^']+)'", output([str(aapt), "dump", "permissions", str(apk)])))
    found = permissions & FORBIDDEN_PERMISSIONS
    check(not found, f"none of the permissions removed for Play {sorted(found) or ''}")
    print("      to declare in the Play Console:", ", ".join(sorted(permissions & DECLARED_PERMISSIONS)))

    signer = "apksigner.bat" if sys.platform == "win32" else "apksigner"
    certs = output(
        ["cmd", "/c", str(sdk_tool(signer)), "verify", "--print-certs", str(apk)]
        if sys.platform == "win32"
        else [str(sdk_tool(signer)), "verify", "--print-certs", str(apk)]
    )
    subject = re.search(r"certificate DN: (.*)", certs)[1]
    check("Android Debug" not in subject, f"not signed with a debug key: {subject}")
    print("      upload certificate SHA-256:", re.search(r"certificate SHA-256 digest: (\w+)", certs)[1])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--signing", required=True, help="properties file: storeFile, storePassword, keyAlias, keyPassword")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    os.environ["JAVA_HOME"] = str(java_home())

    version = (ROOT / "browser/config/akhi_version.txt").read_text().strip()
    out = ROOT / "artifacts" / f"play-{version}"
    aab = out / f"AkhiBrowser-{version}-play.aab"
    apk = out / f"AkhiBrowser-{version}-play-universal.apk"
    signing = read_signing(args.signing)

    with tempfile.TemporaryDirectory() as temp:
        work = Path(temp)
        if not args.check_only:
            build(args.signing, work)
            out.mkdir(parents=True, exist_ok=True)
            shutil.copy2(BUNDLE, aab)
        universal, download = make_apks(aab, signing, work)
        shutil.copy2(universal, apk)
        check_bundle(aab)
        check_apk(universal)
        check(download <= MAX_DOWNLOAD_BYTES, f"largest download {download / 1e6:.1f} MB (limit 200 MB)")

    print(f"\n{aab}\n{apk}")
    if failures:
        sys.exit(f"\n{len(failures)} check(s) failed: Play would refuse this build")
    print("\nAll checks passed. See browser/branding/akhi/play/CONSOLE.md for what the Play Console asks for.")


if __name__ == "__main__":
    main()
