# AkhiBrowser branding and build configurations

Private. Mounted in [akhiBrowser](https://github.com/halgurdh/akhiBrowser) at `browser/branding/akhi`.

- The desktop branding: names (`locales/`), installer, icons and about dialog, in TV Akhi's colors.
  `tools/make_icons.py` makes all the icons again from the logo, desktop and Android (needs Pillow).
- `mozconfigs/`: the build configurations, used from the top of akhiBrowser:

```sh
MOZCONFIG=browser/branding/akhi/mozconfigs/akhi-desktop ./mach build
```

## Owner notes: macOS and iOS

Owner only. This file is in the private `akhi-branding` repository; the README of `akhiBrowser` is public, so these
notes don't belong there. Neither platform has been built or tested yet: both need a Mac.

### macOS: possible, needs a Mac and an Apple Developer account

Ready: 64-bit build configs (`mozconfigs/akhi-macos-arm64`, `mozconfigs/akhi-macos-x64`), `firefox.icns`, `disk.icns`,
`document.icns` and `background.png` (all from `tools/make_icons.py`). The extension needs no change: it runs as on
Windows.

```sh
MOZCONFIG=browser/branding/akhi/mozconfigs/akhi-macos-arm64 ./mach build
MOZCONFIG=browser/branding/akhi/mozconfigs/akhi-macos-arm64 ./mach package
```

To do, on a Mac:

1. `Assets.car` is still byte-identical to `browser/branding/unofficial/`, so recent macOS can show the Nightly icon.
   Make it again from the logo with Xcode's Icon Composer and `actool`.
2. `dsstore` is also unofficial's and mentions "Nightly". Lay out a mounted disk image in Finder and copy its
   `.DS_Store` here, or the disk image window can look wrong.
3. Check the bundle id of the built app (`MOZ_MACBUNDLE_ID` in `configure.sh`). Decide it before the first release:
   changing it later makes macOS treat the app as a new one.
4. Sign and notarize. Without it Gatekeeper blocks the app on other Macs. It needs a paid Apple Developer account;
   `./mach macos-sign` signs, then `xcrun notarytool` and `xcrun stapler`.
5. Keep a separate download for each processor, or make a universal app, and check the blur on a real Mac.

### iOS: not with this engine for now

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
