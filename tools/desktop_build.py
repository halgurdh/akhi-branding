"""Shared steps of build_windows.py, build_linux.py and build_macos.py."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
BRANDING = ROOT / "browser/branding/akhi"


def run(command, env=None, shell=False, cwd=ROOT):
    subprocess.run(command, check=True, cwd=cwd, env=env, shell=shell)


def mozconfig_env(mozconfig):
    return {**os.environ, "MOZCONFIG": f"browser/branding/akhi/mozconfigs/{mozconfig}"}


def check_sources():
    for path, repository in (
        (BRANDING / "mozconfigs", "akhi-branding"),
        (ROOT / "browser/extensions/akhi/webext/package.json", "akhi-extension"),
        (ROOT / "browser/extensions/akhi-premium", "akhibrowser-premium"),
    ):
        if not path.exists():
            sys.exit(f"No {path}: run git submodule update --init --recursive ({repository})")


def build_and_package(mozconfig, objdir, full=True):
    """Builds with the extension and Premium merged and minified, then runs ./mach package.

    full: a complete ./mach build; False runs ./mach build faster, for when the C++ and Rust are already built.
    """
    check_sources()
    env = mozconfig_env(mozconfig)
    run([sys.executable, "mach", "build"] + ([] if full else ["faster"]), env=env)
    built_extension = objdir / "dist/bin/browser/chrome/browser/builtin-addons/akhi"
    with tempfile.TemporaryDirectory() as temp:
        minified = Path(temp) / "extension"
        run(
            ["node", str(BRANDING / "tools/merge_akhi_extension.mjs"), str(minified)],
            shell=sys.platform == "win32",
        )
        for source in minified.rglob("*"):
            if source.is_file():
                target = built_extension / source.relative_to(minified)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())
    run([sys.executable, "mach", "package"], env=env)


def make_update(objdir, keys):
    if keys:
        run([sys.executable, str(BRANDING / "tools/make_update.py"), "--objdir", str(objdir), "--keys", str(keys)])


def release_copy(source, name):
    out = source.parent / "release"
    out.mkdir(exist_ok=True)
    target = out / name
    shutil.copyfile(source, target)
    return target
