#!/usr/bin/env python3
"""Builds the Windows installer with the extension and Premium merged and minified, as the store builds have them.

The update MAR and signing stay with make_update.py. Run from anywhere: python build_windows.py
"""

from desktop_build import ROOT, build_and_package

OBJDIR = ROOT / "obj-akhi-desktop"


def main():
    build_and_package("akhi-desktop", OBJDIR, full=False)
    print(f"Installer: {OBJDIR / 'dist' / 'install' / 'sea'}")


if __name__ == "__main__":
    main()
