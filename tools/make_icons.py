#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
"""Draws the AkhiBrowser logo, in the colors of TV Akhi (https://github.com/halgurdh/tv-akhi): a gold shield on a
teal gradient, with a white crescent and star where TV Akhi has its play button. Writes every icon made from it:
the desktop branding (browser/branding/akhi/), the Android launcher icons (mobile/android/fenix/app/src/*/res/)
and the icon of the built-in extension (browser/extensions/akhi/icons/).

Needs Pillow. From the top source directory:

    python browser/branding/akhi/tools/make_icons.py
"""

import math
import os

from PIL import Image, ImageDraw, ImageFont

TEAL_TOP = "#074D49"
TEAL_BOTTOM = "#03282E"
PRIVATE_TOP = "#4A2E83"
PRIVATE_BOTTOM = "#21123A"
GOLD = "#F4BE34"
INSIDE = "#03282E"
WHITE = "#FFFFFF"

BRANDING = "browser/branding/akhi"
EXTENSION = "browser/extensions/akhi"
FENIX = "mobile/android/fenix/app/src"

# The logo, in the 108x108 viewport of an Android adaptive icon (safe zone: a 33 radius circle around 54,54)
SHIELD_CENTER = (54.0, 54.5)
SHIELD_INSET = 0.8
CRESCENT_OUTER = ((53.0, 53.0), 10.0)
CRESCENT_INNER = ((58.0, 49.5), 8.6)
STAR = ((63.5, 44.5), 2.8)

# The desktop icon: the logo, larger, on a rounded square
DESKTOP_SCALE = 1.4
DESKTOP_RADIUS = 24.0


def shield_points():
    return [(34, 34), (54, 28), (74, 34), (74, 57), (54, 81), (34, 57)]


def inner_shield_points():
    cx, cy = SHIELD_CENTER
    return [(cx + (x - cx) * SHIELD_INSET, cy + (y - cy) * SHIELD_INSET) for x, y in shield_points()]


def crescent_points(steps=64):
    """The outer circle minus the inner one: the far arc of the outer circle, back along the near arc of the inner"""
    (c1, r1), (c2, r2) = CRESCENT_OUTER, CRESCENT_INNER
    dx, dy = c2[0] - c1[0], c2[1] - c1[1]
    d = math.hypot(dx, dy)
    phi = math.atan2(dy, dx)
    alpha = math.acos((r1 * r1 + d * d - r2 * r2) / (2 * r1 * d))
    beta = math.acos((r2 * r2 + d * d - r1 * r1) / (2 * r2 * d))
    points = []
    for i in range(steps + 1):
        a = phi + alpha + (2 * math.pi - 2 * alpha) * i / steps
        points.append((c1[0] + r1 * math.cos(a), c1[1] + r1 * math.sin(a)))
    back = phi + math.pi
    for i in range(steps + 1):
        a = back + beta - 2 * beta * i / steps
        points.append((c2[0] + r2 * math.cos(a), c2[1] + r2 * math.sin(a)))
    return points


def star_points():
    (cx, cy), r = STAR
    points = []
    for i in range(10):
        radius = r if i % 2 == 0 else r * 0.42
        a = -math.pi / 2 + i * math.pi / 5
        points.append((cx + radius * math.cos(a), cy + radius * math.sin(a)))
    return points


# (color, points) from back to front
def logo():
    return [
        (GOLD, shield_points()),
        (INSIDE, inner_shield_points()),
        (WHITE, crescent_points()),
        (WHITE, star_points()),
    ]


def path_of(points):
    return "M" + " L".join(f"{x:.2f},{y:.2f}" for x, y in points) + " Z"


def transform(points, scale):
    return [(54 + (x - 54) * scale, 54 + (y - 54) * scale) for x, y in points]


def gradient(size, top, bottom):
    top_rgb = Image.new("RGB", (1, 1), top).getpixel((0, 0))
    bottom_rgb = Image.new("RGB", (1, 1), bottom).getpixel((0, 0))
    column = Image.new("RGB", (1, 256))
    for y in range(256):
        t = y / 255
        column.putpixel((0, y), tuple(round(a + (b - a) * t) for a, b in zip(top_rgb, bottom_rgb)))
    return column.resize(size, Image.BILINEAR).convert("RGBA")


def render(size, private=False, desktop=True):
    """The logo as an RGBA image, drawn large and scaled down"""
    big = max(size * 8, 1024)
    k = big / 108
    top, bottom = (PRIVATE_TOP, PRIVATE_BOTTOM) if private else (TEAL_TOP, TEAL_BOTTOM)
    background = gradient((big, big), top, bottom)
    mask = Image.new("L", (big, big), 0)
    if desktop:
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, big - 1, big - 1), radius=DESKTOP_RADIUS * k, fill=255)
    else:
        mask.paste(255, (0, 0, big, big))
    image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    image.paste(background, (0, 0), mask)
    draw = ImageDraw.Draw(image)
    scale = DESKTOP_SCALE if desktop else 1.0
    for color, points in logo():
        draw.polygon([(x * k, y * k) for x, y in transform(points, scale)], fill=color)
    return image.resize((size, size), Image.LANCZOS)


def font(size):
    for name in ("segoeuib.ttf", "DejaVuSans-Bold.ttf", "Arial Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def draw_name(image, center, size):
    """AkhiBrowser in the colors of TV Akhi's name: Akhi in gold, Browser in white"""
    draw = ImageDraw.Draw(image)
    f = font(size)
    akhi = draw.textlength("Akhi", font=f)
    total = akhi + draw.textlength("Browser", font=f)
    left = center[0] - total / 2
    draw.text((left, center[1]), "Akhi", fill=GOLD, font=f, anchor="lm")
    draw.text((left + akhi, center[1]), "Browser", fill=WHITE, font=f, anchor="lm")


def save(image, path, **kwargs):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    image.save(path, **kwargs)
    print(path)


def tile(size, private=False):
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    icon = render(int(size * 0.7), private)
    offset = (size - icon.width) // 2
    canvas.alpha_composite(icon, (offset, offset))
    return canvas


def desktop():
    b = BRANDING
    for size in (16, 22, 24, 32, 48, 64, 128, 256):
        save(render(size), f"{b}/default{size}.png")
    save(render(192), f"{b}/content/about-logo.png")
    save(render(384), f"{b}/content/about-logo@2x.png")
    save(render(192, True), f"{b}/content/about-logo-private.png")
    save(render(384, True), f"{b}/content/about-logo-private@2x.png")

    save(render(256), f"{b}/firefox.ico", sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])
    save(render(64), f"{b}/firefox64.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
    save(render(256, True), f"{b}/pbmode.ico", sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])
    save(render(1024), f"{b}/firefox.icns")
    save(render(1024), f"{b}/disk.icns")
    save(render(1024), f"{b}/document.icns")

    # the App Store icon of a future iOS app: square, without transparency
    ios = gradient((1024, 1024), TEAL_TOP, TEAL_BOTTOM)
    ios.alpha_composite(render(1024))
    save(ios.convert("RGB"), f"{b}/ios/AppIcon-1024.png")

    save(tile(300), f"{b}/VisualElements_150.png")
    save(tile(142), f"{b}/VisualElements_70.png")
    save(tile(300, True), f"{b}/PrivateBrowsing_150.png")
    save(tile(142, True), f"{b}/PrivateBrowsing_70.png")

    assets = f"{b}/msix/Assets"
    save(tile(620), f"{assets}/LargeTile.scale-200.png")
    save(tile(300), f"{assets}/MedTile.scale-200.png")
    save(tile(142), f"{assets}/SmallTile.scale-200.png")
    save(tile(300), f"{assets}/Square150x150Logo.scale-200.png")
    save(render(88), f"{assets}/Square44x44Logo.scale-200.png")
    for name in ("targetsize-256", "altform-unplated_targetsize-256", "altform-lightunplated_targetsize-256"):
        save(render(256), f"{assets}/Square44x44Logo.{name}.png")
    save(render(100), f"{assets}/StoreLogo.scale-200.png")
    wide = Image.new("RGBA", (620, 300), (0, 0, 0, 0))
    wide.alpha_composite(render(180), (220, 60))
    save(wide, f"{assets}/Wide310x150Logo.scale-200.png")

    about = gradient((300, 236), TEAL_TOP, TEAL_BOTTOM)
    about.alpha_composite(render(150), (75, 12))
    draw_name(about, (150, 202), 30)
    save(about, f"{b}/content/about.png")

    header = Image.new("RGBA", (150, 57), WHITE)
    header.alpha_composite(render(45), (99, 6))
    save(header.convert("RGB"), f"{b}/wizHeader.bmp")
    save(header.transpose(Image.FLIP_LEFT_RIGHT).convert("RGB"), f"{b}/wizHeaderRTL.bmp")
    watermark = gradient((164, 314), TEAL_TOP, TEAL_BOTTOM)
    watermark.alpha_composite(render(112), (26, 70))
    draw_name(watermark, (82, 215), 20)
    save(watermark.convert("RGB"), f"{b}/wizWatermark.bmp")
    save(gradient((1344, 822), TEAL_TOP, TEAL_BOTTOM).convert("RGB"), f"{b}/stubinstaller/bgstub.jpg", quality=90)

    # the disk image: the app goes on the left, the Applications folder on the right of the arrow
    dmg = gradient((1440, 880), TEAL_TOP, TEAL_BOTTOM)
    draw = ImageDraw.Draw(dmg)
    draw.line((590, 387, 735, 387), fill=WHITE, width=6)
    draw.polygon([(745, 387), (715, 367), (715, 407)], fill=WHITE)
    save(dmg, f"{b}/background.png")

    save_svg(f"{b}/content/about-logo.svg", desktop_svg())
    save_svg(f"{b}/content/about-wordmark.svg", wordmark_svg("context-fill"))
    save_svg(f"{b}/content/firefox-wordmark.svg", wordmark_svg("context-fill light-dark(#03282e, #fbfbfe)"))


MPL_HEADER = """<!-- This Source Code Form is subject to the terms of the Mozilla Public
   - License, v. 2.0. If a copy of the MPL was not distributed with this
   - file, You can obtain one at http://mozilla.org/MPL/2.0/. -->
"""


def save_svg(path, body):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(MPL_HEADER + body)
    print(path)


def desktop_svg():
    paths = "".join(
        f'  <path fill="{color}" d="{path_of(transform(points, DESKTOP_SCALE))}"/>\n' for color, points in logo()
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 108 108">
  <defs>
    <linearGradient id="teal" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{TEAL_TOP}"/>
      <stop offset="1" stop-color="{TEAL_BOTTOM}"/>
    </linearGradient>
  </defs>
  <rect width="108" height="108" rx="{DESKTOP_RADIUS:g}" fill="url(#teal)"/>
{paths}</svg>
"""


def wordmark_svg(fill):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" fill="{fill}" viewBox="0 0 372 99">
  <text x="186" y="70" text-anchor="middle" font-family="Segoe UI, Helvetica Neue, Ubuntu, sans-serif"
        font-size="68" font-weight="700"><tspan fill="{GOLD}">Akhi</tspan>Browser</text>
</svg>
"""


VECTOR_HEADER = '<?xml version="1.0" encoding="utf-8"?>\n' + MPL_HEADER


def vector(paths, fill_type=None):
    attrs = f'\n      android:fillType="{fill_type}"' if fill_type else ""
    body = "".join(
        f"""  <path{attrs}
      android:fillColor="{color}"
      android:pathData="{data}"/>
"""
        for color, data in paths
    )
    return (
        VECTOR_HEADER
        + """<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="108dp"
    android:height="108dp"
    android:viewportWidth="108"
    android:viewportHeight="108">
"""
        + body
        + "</vector>\n"
    )


def background_vector():
    return (
        VECTOR_HEADER
        + f"""<vector xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:aapt="http://schemas.android.com/aapt"
    android:width="108dp"
    android:height="108dp"
    android:viewportWidth="108"
    android:viewportHeight="108">
  <path android:pathData="M0,0h108v108h-108z">
    <aapt:attr name="android:fillColor">
      <gradient
          android:type="linear"
          android:startX="54"
          android:startY="0"
          android:endX="54"
          android:endY="108"
          android:startColor="{TEAL_TOP}"
          android:endColor="{TEAL_BOTTOM}"/>
    </aapt:attr>
  </path>
</vector>
"""
    )


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(path)


def android():
    foreground = vector([(color, path_of(points)) for color, points in logo()])
    holes = " ".join(path_of(points) for _, points in logo())
    monochrome = vector([("#FF000000", holes)], fill_type="evenOdd")
    write(f"{FENIX}/main/res/drawable/ic_launcher_akhi_background.xml", background_vector())
    write(f"{FENIX}/main/res/drawable/ic_launcher_foreground.xml", foreground)
    write(f"{FENIX}/main/res/drawable/ic_launcher_monochrome.xml", monochrome)
    for variant in ("release", "beta", "nightly", "debug"):
        write(f"{FENIX}/{variant}/res/drawable/ic_launcher_foreground.xml", foreground)

    densities = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
    for variant in ("release", "beta", "nightly", "debug"):
        for density, size in densities.items():
            folder = f"{FENIX}/{variant}/res/mipmap-{density}"
            if not os.path.isdir(folder):
                continue
            save(render(size), f"{folder}/ic_launcher.webp", lossless=True)
            mask = Image.new("L", (size * 4, size * 4), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, size * 4 - 1, size * 4 - 1), fill=255)
            round_icon = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            round_icon.paste(render(size, desktop=False), (0, 0), mask.resize((size, size), Image.LANCZOS))
            save(round_icon, f"{folder}/ic_launcher_round.webp", lossless=True)

    android_in_app(foreground)


# the shield only, without the margins of the launcher icon
SHIELD_BOX = (33, 27, 42, 55)


def shield_vector(paths, width_dp, fill_type=None):
    x, y, w, h = SHIELD_BOX
    attrs = f'\n        android:fillType="{fill_type}"' if fill_type else ""
    body = "".join(
        f"""    <path{attrs}
        android:fillColor="{color}"
        android:pathData="{data}"/>
"""
        for color, data in paths
    )
    return (
        VECTOR_HEADER
        + f"""<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="{width_dp:g}dp"
    android:height="{width_dp * h / w:.2f}dp"
    android:viewportWidth="{w}"
    android:viewportHeight="{h}">
  <group android:translateX="{-x}" android:translateY="{-y}">
"""
        + body
        + "  </group>\n</vector>\n"
    )


def shield_image(height):
    """The shield alone, transparent around it"""
    x, y, w, h = SHIELD_BOX
    k = height * 8 / h
    big = Image.new("RGBA", (round(w * k), round(h * k)), (0, 0, 0, 0))
    draw = ImageDraw.Draw(big)
    for color, points in logo():
        draw.polygon([((px - x) * k, (py - y) * k) for px, py in points], fill=color)
    return big.resize((round(w * height / h), height), Image.LANCZOS)


def name_image(size, private, with_logo):
    """AkhiBrowser, with the shield in front when [with_logo]: Akhi in gold, Browser dark or white in private mode"""
    width, height = size
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    left = 0
    if with_logo:
        shield = shield_image(height)
        image.alpha_composite(shield, (0, 0))
        left = shield.width + height // 6
    text_size = int(height * (0.5 if with_logo else 0.9))
    draw = ImageDraw.Draw(image)
    while text_size > 4:
        f = font(text_size)
        akhi = draw.textlength("Akhi", font=f)
        if left + akhi + draw.textlength("Browser", font=f) <= width:
            break
        text_size -= 1
    draw.text((left, height / 2), "Akhi", fill=GOLD, font=f, anchor="lm")
    draw.text((left + akhi, height / 2), "Browser", fill=WHITE if private else INSIDE, font=f, anchor="lm")
    return image


def android_in_app(foreground):
    shield = [(color, path_of(points)) for color, points in logo()]
    holes = " ".join(path_of(points) for _, points in logo())
    for variant in ("main", "beta", "nightly", "debug"):
        path = f"{FENIX}/{variant}/res/drawable/ic_firefox.xml"
        if os.path.exists(path):
            write(path, shield_vector(shield, 52))
    write(f"{FENIX}/main/res/drawable/ic_splash_logo.xml", foreground)
    write(f"{FENIX}/main/res/drawable/ic_status_logo.xml", shield_vector([("@android:color/white", holes)], 24, "evenOdd"))

    for variant in ("main", "release", "beta", "nightly", "debug"):
        res = f"{FENIX}/{variant}/res"
        if not os.path.isdir(res):
            continue
        for folder in sorted(os.listdir(res)):
            if not folder.startswith("drawable"):
                continue
            for name in ("ic_logo_wordmark_normal", "ic_logo_wordmark_private", "ic_wordmark_logo",
                         "ic_wordmark_text_normal", "ic_wordmark_text_private"):
                webp = f"{res}/{folder}/{name}.webp"
                xml = f"{res}/{folder}/{name}.xml"
                if os.path.exists(webp):
                    size = Image.open(webp).size
                elif name.startswith("ic_wordmark_text") and os.path.exists(xml):
                    size = (419, 93)
                    os.remove(xml)
                else:
                    continue
                if name == "ic_wordmark_logo":
                    image = Image.new("RGBA", size, (0, 0, 0, 0))
                    shield = shield_image(size[1])
                    image.alpha_composite(shield, ((size[0] - shield.width) // 2, 0))
                else:
                    image = name_image(size, name.endswith("private"), name.startswith("ic_logo_wordmark"))
                save(image, webp, lossless=True)


def extension():
    save_svg(f"{EXTENSION}/icons/akhi.svg", desktop_svg())


if __name__ == "__main__":
    desktop()
    android()
    extension()
