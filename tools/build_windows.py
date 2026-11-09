#!/usr/bin/env python3
"""Builds the Windows installer with the extension and Premium merged and minified, as the store builds have them.

The update MAR and signing stay with make_update.py. Run from anywhere: python build_windows.py
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OBJDIR = ROOT / "obj-akhi-desktop"
BUILT_EXTENSION = OBJDIR / "dist/bin/browser/chrome/browser/builtin-addons/akhi"


def run(command, env=None, shell=False):
    subprocess.run(command, check=True, cwd=ROOT, env=env, shell=shell)


def main():
    env = {**os.environ, "MOZCONFIG": "browser/branding/akhi/mozconfigs/akhi-desktop"}
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
                target.write_bytes(source.read_bytes())
    run([sys.executable, "mach", "package"], env=env)
    print(f"Installer: {OBJDIR / 'dist' / 'install' / 'sea'}")


if __name__ == "__main__":
    main()
