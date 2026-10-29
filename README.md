# AkhiBrowser branding and build configurations

Private. Mounted in [akhiBrowser](https://github.com/halgurdh/akhiBrowser) at `browser/branding/akhi`.

- The desktop branding: names (`locales/`), installer, icons and about dialog, in TV Akhi's colors.
  `tools/make_icons.py` makes all the icons again from the logo, desktop and Android (needs Pillow).
- `mozconfigs/`: the build configurations, used from the top of akhiBrowser:

```sh
MOZCONFIG=browser/branding/akhi/mozconfigs/akhi-desktop ./mach build
```
