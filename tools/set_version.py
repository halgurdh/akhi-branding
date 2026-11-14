#!/usr/bin/env python3
# Copyright (c) 2026 the AkhiBrowser authors. All rights reserved.
"""Sets the AkhiBrowser version everywhere a release needs it, from the root of the tree:

    python browser/branding/akhi/tools/set_version.py 1.3.3
    python browser/branding/akhi/tools/set_version.py --check

browser/config/akhi_version.txt, CURRENT_VERSION in the extension's lib/updates.js and "version" in the root
package.json. The extension's own manifest version is separate and stays as it is.
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
VERSION_TXT = ROOT / "browser/config/akhi_version.txt"
UPDATES_JS = ROOT / "browser/extensions/akhi/lib/updates.js"
PACKAGE_JSON = ROOT / "package.json"
VERSION = re.compile(r"^\d+\.\d+\.\d+$")
UPDATES_PATTERN = re.compile(r'(CURRENT_VERSION = ")([^"]+)(")')
PACKAGE_PATTERN = re.compile(r'^(  "version": ")([^"]+)(")', re.MULTILINE)


def current():
    """{file: version} of the three places."""
    return {
        VERSION_TXT: VERSION_TXT.read_text().strip(),
        UPDATES_JS: UPDATES_PATTERN.search(UPDATES_JS.read_text()).group(2),
        PACKAGE_JSON: PACKAGE_PATTERN.search(PACKAGE_JSON.read_text()).group(2),
    }


def replace_in(path, pattern, version):
    text = path.read_text(newline="")
    new, count = pattern.subn(rf"\g<1>{version}\g<3>", text, count=1)
    if count != 1:
        sys.exit(f"No version found in {path}")
    path.write_text(new, newline="")


def set_version(version):
    if not VERSION.match(version):
        sys.exit(f"Not a version like 1.3.3: {version}")
    VERSION_TXT.write_text(f"{version}\n", newline="")
    replace_in(UPDATES_JS, UPDATES_PATTERN, version)
    replace_in(PACKAGE_JSON, PACKAGE_PATTERN, version)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("version", nargs="?")
    parser.add_argument("--check", action="store_true", help="Only check that the three places agree")
    args = parser.parse_args()
    if args.version and not args.check:
        set_version(args.version)
    found = current()
    for path, version in found.items():
        print(f"{version}  {path.relative_to(ROOT).as_posix()}")
    if len(set(found.values())) != 1:
        sys.exit("The versions differ")


if __name__ == "__main__":
    main()
