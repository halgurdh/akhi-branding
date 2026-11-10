# AkhiBrowser branding and build configurations

Private. Mounted in [akhiBrowser](https://github.com/halgurdh/akhiBrowser) at `browser/branding/akhi`.

- The desktop branding: names (`locales/`), installer, icons and about dialog, in TV Akhi's colors.
  `tools/make_icons.py` makes all the icons again from the logo, desktop and Android (needs Pillow).
- `mozconfigs/`: the build configurations, used from the top of akhiBrowser (or through the build scripts below):

```sh
MOZCONFIG=browser/branding/akhi/mozconfigs/akhi-desktop ./mach build
```

## Owner notes: macOS, Linux and iOS

Owner only. This file is in the private `akhi-branding` repository; the README of `akhiBrowser` is public, so these
notes don't belong there. None of the three has been built or tested yet: macOS and iOS need a Mac.

Every desktop build script does the same as `tools/build_windows.py`: build, merge and minify the extension and
Premium (`npm install` in `browser/extensions/akhi/webext` once), package, and with `--keys` the signed update. Run
`./mach bootstrap` once first. The release files go to `<objdir>/dist/release/`, named like the Windows installer.

| Platform | Command | Release file |
| --- | --- | --- |
| Windows x64 | `python browser/branding/akhi/tools/build_windows.py` | `AkhiBrowser-windows-x64-setup.exe` |
| Linux x64 | `python browser/branding/akhi/tools/build_linux.py` | `AkhiBrowser-linux-x64.tar.xz` |
| Linux ARM | `python browser/branding/akhi/tools/build_linux.py --arch arm64` | `AkhiBrowser-linux-arm64.tar.xz` |
| Mac, Apple silicon | `python browser/branding/akhi/tools/build_macos.py` | `AkhiBrowser-macos-arm64.dmg` |
| Mac, Intel | `python browser/branding/akhi/tools/build_macos.py --arch x64` | `AkhiBrowser-macos-x64.dmg` |

Updates: Linux and macOS have the updater on, like Windows, with the same channel and key. Upload the `.mar` and
`update-<target>.xml` from `<objdir>/dist/update/` to the release next to the download; the browser asks for
`update-Linux_x86_64-gcc3.xml`, `update-Linux_aarch64-gcc3.xml`, `update-Darwin_aarch64-gcc3.xml` or
`update-Darwin_x86_64-gcc3.xml`.

### Linux

Builds on any 64-bit Linux, or WSL2 (Ubuntu) on the Windows PC: 16 GB of memory and 60 GB of free space at least.
`build_linux.py` must run on the processor it builds for. The `.tar.xz` unpacks to `akhibrowser/`; start
`akhibrowser/akhibrowser`. Updates only work where the user can write to that folder. Not done yet: a `.deb`, Flatpak
or Snap, and a `.desktop` file for the menu (the icons `default16.png` to `default256.png` are ready for it).

### macOS: possible, needs a Mac and an Apple Developer account

Ready: 64-bit build configs (`mozconfigs/akhi-macos-arm64`, `mozconfigs/akhi-macos-x64`), `firefox.icns`, `disk.icns`,
`document.icns` and `background.png` (all from `tools/make_icons.py`). The extension needs no change: it runs as on
Windows. The bundle id is `org.akhibrowser.desktop` (`--with-distribution-id=org.akhibrowser` in the configs and
`MOZ_MACBUNDLE_ID` in `configure.sh`), and the configs make a `.dmg` (`MOZ_PKG_FORMAT=DMG`; without it a build that
isn't `--enable-release` packages a `.tar`).

```sh
python browser/branding/akhi/tools/build_macos.py
python browser/branding/akhi/tools/build_macos.py --sign-identity "Developer ID Application: <name> (<Team ID>)" \
    --notary-profile akhi --keys <folder>
```

The second signs with `./mach macos-sign`, notarizes and staples the `.dmg`, and makes the update from the signed app.
Save the notary profile once with `xcrun notarytool store-credentials akhi`.

To do, on a Mac:

1. `Assets.car` is still byte-identical to `browser/branding/unofficial/`, so recent macOS can show the Nightly icon.
   Make it again from the logo with Xcode's Icon Composer and `actool`.
2. `dsstore` is also unofficial's and mentions "Nightly". Lay out a mounted disk image in Finder and copy its
   `.DS_Store` here, or the disk image window can look wrong.
3. Check that the built app says `org.akhibrowser.desktop`
   (`defaults read AkhiBrowser.app/Contents/Info CFBundleIdentifier`). Changing it after the first release makes macOS
   treat the app as a new one.
4. Sign and notarize. Without it Gatekeeper blocks the app on other Macs. It needs a paid Apple Developer account and
   a Developer ID Application certificate: `build_macos.py --sign-identity ... --notary-profile ...`. Signed apps are
   changed by each update, so check that an update from the previous signed release still opens.
5. Keep a separate download for each processor, or make a universal app, and check the blur on a real Mac.

### iOS: not with this engine for now

The iOS app is now its own WebKit fork of firefox-ios, in the private
[akhibrowser-ios](https://github.com/halgurdh/akhibrowser-ios): see its `docs/akhibrowser-ios-macos-release.md` for
signing, `scripts/akhi-ios-build.sh` and Xcode Cloud. The notes below were written before it.

Gecko isn't a real option. `mobile/ios` is Mozilla's prototype, and engines other than WebKit are only allowed in some
regions (the EU, and Japan's rules since late 2025), with entitlements from Apple and extra security requirements. Check
Apple's current documentation first: the details found while writing this came from secondary sources and disagreed.

| Option | Protections | Verdict |
| --- | --- | --- |
| Own app on WebKit (fork of [firefox-ios](https://github.com/mozilla-mobile/firefox-ios)), the filters as `WKContentRuleList` and user scripts | Built in, can't be turned off outside the app, the parental PIN can stay | **Recommended** |
| Safari web extension in a small app | The user can turn it off in Settings, so the parental PIN means little; only Safari | Quickest to try |
| Gecko with BrowserEngineKit | Same as Android, in a few regions only | Not now |

What has to change from this extension, either way:

| Used today | On iOS |
| --- | --- |
| `experiment-apis/` (`browser.akhi`), called at the top of `background.js` | Doesn't exist: prefs go to the app, and those calls need a guard or the rest of the background stops |
| `webRequest` blocking (sites, ads, YouTube header) | Not available as here: rule lists instead. Convert `filters/*.bin`: they are hashes, so the rules must be built from the source lists in `tools/make_filter_lists.py`, and rule lists have size limits |
| SafeSearch redirects, search blocking | Rule list redirects, or a check in the app before a page loads |
| uBlock Origin (`keepAddonInstalled`, `setTrustedSite`) | Not available: only the built-in list and content rule lists |
| Long lived background with a worker (`classify`) | Background pages aren't persistent, and memory is tight: the models (about 13 MB) must be tested on a real iPhone, or moved to Core ML in an own app |
| Reading the pixels of images of other sites | Check it first: in an own app, download them natively |
| `openOrClosedShadowRoot` | Firefox only, already falls back to `shadowRoot`: closed shadow roots aren't seen |
| `tabs.update` with `loadReplace` | Firefox only |

`ios/AppIcon-1024.png` is the App Store icon (square, no transparency, also from `tools/make_icons.py`). Reusable as
they are: `lib/search_filter.js`, `lib/content_filter.js` (without the lists), `content/image_scan.*`,
`lib/image_classifier.js` and the models, if WebAssembly runs well enough.

### ARM devices

AkhiBrowser is 64-bit only: 64-bit ARM is supported where a config exists, 32-bit ARM (`armeabi-v7a`) is dropped.

| Device | Config | State |
| --- | --- | --- |
| Android phones and tablets (`arm64-v8a`) | `mozconfigs/akhi-android-arm64` | Released; the APK was installed and run on a Galaxy A54 |
| Windows on ARM (Snapdragon laptops) | `mozconfigs/akhi-windows-arm64` | Config only, made on an x64 Windows PC, never released or tested. Until then these laptops can run the x64 build through Windows' emulation, slower |
| Macs with Apple silicon | `mozconfigs/akhi-macos-arm64` | Config only, needs a Mac, see above |
| Linux on ARM | `mozconfigs/akhi-linux-arm64`, built on an ARM Linux machine | Config only, not tried |
| iPhone and iPad | None here: the WebKit app in akhibrowser-ios | Development build, see above |
| Old 32-bit ARM phones | Removed | Can stay on 0.2.1, which still has the APK, without updates |

The image check needs no change per processor: it runs on WebAssembly or WebGL, and the models and `filters/*.bin` are
the same files everywhere. The lists are read as little-endian, which all of these are.

TV Akhi is separate: it still ships `armeabi-v7a` as well as `arm64-v8a`. Keep both unless that changes on purpose, as
many Android TVs may run a 32-bit system.

To add a Windows ARM download: build and package with its config, test it on a real device (the blur and no music at
least), then add the installer to the release next to the x64 one.
