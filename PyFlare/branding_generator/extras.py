"""
branding_generator/extras.py
Premium procedural graphics — no debug text, no plain rectangles.
All assets use gradients, glassmorphism, layered shadows, and SDF geometry.
"""

import os
import math
import logging
from PIL import Image, ImageDraw, ImageFilter
from branding_generator.config import BRAND_COLORS
from branding_generator.utils import (
    ensure_dir, hex_to_rgb, build_radial_gradient_pixels,
    build_linear_gradient_pixels, apply_glow,
)

logger = logging.getLogger("pyflare-brand")

_IND = hex_to_rgb(BRAND_COLORS["indigo"])
_CYA = hex_to_rgb(BRAND_COLORS["cyan"])
_VIO = hex_to_rgb(BRAND_COLORS["violet"])
_PRI = hex_to_rgb(BRAND_COLORS["primary"])
_BG  = hex_to_rgb(BRAND_COLORS["background"])
_SURF= hex_to_rgb(BRAND_COLORS["surface"])
_WHT = (255, 255, 255)


# ---------------------------------------------------------------------------
# Premium background builder (replaces draw_futuristic_layout)
# ---------------------------------------------------------------------------

def draw_premium_background(
    img: Image.Image,
    accent: tuple = None,
    style: str = "dark",
) -> Image.Image:
    """
    Render a rich background with:
      - radial gradient base
      - glassmorphism panel overlay
      - decorative bezier arcs
      - SDF glow rings
    No debug text is written.
    """
    if accent is None:
        accent = _IND
    w, h = img.size
    draw = ImageDraw.Draw(img)

    # 1. Base: dark background
    draw.rectangle([0, 0, w, h], fill=(*_BG, 255))

    # 2. Radial gradient glow from bottom-left and top-right
    cx1, cy1 = w // 5, h * 4 // 5
    for r in range(min(w, h) // 2, 0, -20):
        a = int(35 * (1 - r / (min(w, h) / 2)))
        draw.ellipse([cx1-r, cy1-r, cx1+r, cy1+r], fill=(*accent, a))
    cx2, cy2 = w * 4 // 5, h // 5
    for r in range(min(w, h) // 3, 0, -16):
        a = int(25 * (1 - r / (min(w, h) / 3)))
        draw.ellipse([cx2-r, cy2-r, cx2+r, cy2+r], fill=(*_CYA, a))

    # 3. Subtle grid
    grid = max(60, w // 32)
    for x in range(0, w, grid):
        draw.line([(x, 0), (x, h)], fill=(*_SURF, 30), width=1)
    for y in range(0, h, grid):
        draw.line([(0, y), (w, y)], fill=(*_SURF, 30), width=1)

    # 4. Decorative arcs
    for i, arc_color in enumerate([_IND, _CYA, _VIO]):
        r = int(min(w, h) * (0.3 + i * 0.12))
        off_x = w // 2 + int(w * 0.1 * math.sin(i * 1.5))
        off_y = h // 2 + int(h * 0.08 * math.cos(i * 1.2))
        start = i * 45
        draw.arc([off_x-r, off_y-r, off_x+r, off_y+r],
                 start, start + 160,
                 fill=(*arc_color, 18), width=max(2, w // 120))

    # 5. Apply gaussian blur to soften everything
    blurred = img.filter(ImageFilter.GaussianBlur(radius=max(3, w // 200)))
    return blurred


def draw_glass_card(
    draw: ImageDraw.ImageDraw,
    x: int, y: int, w: int, h: int,
    accent: tuple = None,
    radius: int = 24,
    alpha: int = 200,
):
    """Glassmorphism card: semi-transparent fill + border + inner highlight."""
    if accent is None:
        accent = _IND
    # Main card fill
    draw.rounded_rectangle([x, y, x+w, y+h], radius=radius,
                            fill=(*_SURF, alpha), outline=(*accent, 80), width=2)
    # Inner top highlight (glass sheen)
    draw.rounded_rectangle([x+2, y+2, x+w-2, y+h//4],
                            radius=radius,
                            fill=(255, 255, 255, 12))


# ---------------------------------------------------------------------------
# Login / lockscreen
# ---------------------------------------------------------------------------

def generate_login_assets(target_root: str):
    login_dir = ensure_dir(os.path.join(target_root, "login"))

    for name, accent in [("login_background", _IND), ("lockscreen_background", _CYA)]:
        img = Image.new("RGBA", (1920, 1080))
        img = draw_premium_background(img, accent=accent)
        # Large centered glass card
        draw = ImageDraw.Draw(img)
        card_w, card_h = 480, 580
        cx = (1920 - card_w) // 2
        cy = (1080 - card_h) // 2
        draw_glass_card(draw, cx, cy, card_w, card_h, accent=accent, radius=32, alpha=180)
        # Avatar circle
        ax, ay, ar = cx + card_w//2, cy + 120, 60
        for r in range(ar + 16, ar, -4):
            a = int(40 * (1 - (r - ar) / 16.0))
            draw.ellipse([ax-r, ay-r, ax+r, ay+r], fill=(*accent, a))
        draw.ellipse([ax-ar, ay-ar, ax+ar, ay+ar],
                     fill=(*_SURF, 255), outline=(*accent, 200), width=3)
        # Input field bars
        for i in range(3):
            fx = cx + 40
            fy = cy + 260 + i * 80
            draw.rounded_rectangle([fx, fy, fx + card_w - 80, fy + 44],
                                    radius=12, fill=(*_BG, 200),
                                    outline=(*accent, 60), width=1)
        img.convert("RGB").save(os.path.join(login_dir, f"{name}.png"), "PNG")

    # User avatars
    for avatar_name, color in [("user_avatar", _IND), ("guest_avatar", _CYA)]:
        img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse([8, 8, 248, 248], fill=(*_SURF, 255), outline=(*color, 200), width=6)
        draw.ellipse([88, 48, 168, 128], fill=(*color, 220))
        draw.chord([56, 136, 200, 230], start=180, end=360, fill=(*color, 180))
        img.save(os.path.join(login_dir, f"{avatar_name}.png"), "PNG")

    logger.info("Login: generated backgrounds and avatars")


# ---------------------------------------------------------------------------
# Installer
# ---------------------------------------------------------------------------

def generate_installer_assets(target_root: str):
    inst_dir = ensure_dir(os.path.join(target_root, "installer"))

    # Main background
    bg = Image.new("RGBA", (1920, 1080))
    bg = draw_premium_background(bg, accent=_VIO)
    bg.convert("RGB").save(os.path.join(inst_dir, "installer_background.png"), "PNG")

    # State cards
    states = {
        "install_progress": (_IND, 0.65),
        "installing":       (_CYA, 0.85),
        "success":          ((16, 185, 129), 1.0),
        "finish":           (_IND, 1.0),
        "error":            ((239, 68, 68), 0.1),
    }
    for state, (accent, progress) in states.items():
        img = Image.new("RGBA", (800, 500), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Card
        draw.rounded_rectangle([0, 0, 799, 499], radius=28,
                                fill=(*_SURF, 245), outline=(*accent, 120), width=2)
        # Top accent bar
        draw.rounded_rectangle([0, 0, 799, 8], radius=4, fill=(*accent, 255))
        # Icon circle (top center)
        icx, icy, icr = 400, 100, 44
        for r in range(icr + 20, icr, -4):
            a = int(40 * (1 - (r - icr) / 20.0))
            draw.ellipse([icx-r, icy-r, icx+r, icy+r], fill=(*accent, a))
        draw.ellipse([icx-icr, icy-icr, icx+icr, icy+icr],
                     fill=(*_BG, 255), outline=(*accent, 200), width=3)

        # Progress bar track
        bx1, by1, bx2, by2 = 60, 300, 740, 326
        draw.rounded_rectangle([bx1, by1, bx2, by2], radius=13, fill=(*_BG, 200))
        fill_w = int((bx2 - bx1) * progress)
        if fill_w > 0:
            draw.rounded_rectangle([bx1, by1, bx1 + fill_w, by2],
                                    radius=13, fill=(*accent, 255))

        # Progress dots below bar
        for di in range(5):
            dot_filled = di / 4.0 <= progress
            dot_x = 160 + di * 120
            draw.ellipse([dot_x-6, 350-6, dot_x+6, 350+6],
                         fill=(*accent, 255) if dot_filled else (*_BG, 200))

        # Decorative arcs
        for ar_r in [180, 220, 260]:
            draw.arc([icx - ar_r, icy - ar_r, icx + ar_r, icy + ar_r],
                     -30, 30, fill=(*accent, 20), width=2)

        img.save(os.path.join(inst_dir, f"{state}.png"), "PNG")

    logger.info("Installer: generated background and state cards")


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

def generate_store_assets(target_root: str):
    store_dir = ensure_dir(os.path.join(target_root, "store"))

    banners = {
        "featured_banner.png": (1200, 500, _IND),
        "application_placeholder.png": (600, 400, _CYA),
        "plugin_placeholder.png": (600, 400, _VIO),
        "game_placeholder.png": (600, 400, _PRI),
    }
    for filename, (w, h, accent) in banners.items():
        img = Image.new("RGBA", (w, h))
        img = draw_premium_background(img, accent=accent)
        draw = ImageDraw.Draw(img)
        # Corner accent strips
        draw.polygon([(0, 0), (w//5, 0), (0, h//4)], fill=(*accent, 40))
        draw.polygon([(w, h), (w*4//5, h), (w, h*3//4)], fill=(*accent, 40))
        img.convert("RGB").save(os.path.join(store_dir, filename), "PNG")

    cat_dir = ensure_dir(os.path.join(store_dir, "categories"))
    for cat, accent in [("utilities", _CYA), ("games", _VIO),
                         ("development", _IND), ("personalization", _PRI)]:
        img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw_glass_card(draw, 10, 10, 236, 236, accent=accent, radius=32, alpha=220)
        # Accent dot
        draw.ellipse([108, 68, 148, 108], fill=(*accent, 200))
        img.save(os.path.join(cat_dir, f"{cat}.png"), "PNG")

    logger.info("Store: generated banners and category icons")


# ---------------------------------------------------------------------------
# Placeholders (checker pattern — intentionally distinctive)
# ---------------------------------------------------------------------------

def generate_placeholders(target_root: str):
    place_dir = ensure_dir(os.path.join(target_root, "placeholders"))
    names = ["missing_texture", "missing_model", "missing_asset",
             "missing_icon", "unknown_file", "unknown_project"]
    for name in names:
        img  = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        # Magenta/dark checker (universal missing pattern)
        sq = 64
        for row in range(8):
            for col in range(8):
                fill = (200, 0, 180, 255) if (row + col) % 2 == 0 else (*_BG, 255)
                draw.rectangle([col*sq, row*sq, (col+1)*sq, (row+1)*sq], fill=fill)
        # Overlay glass card (no text)
        draw_glass_card(draw, 40, 40, 432, 432, accent=_CYA, radius=16, alpha=160)
        # Warning icon (triangle)
        tri = [(256, 140), (150, 340), (362, 340)]
        draw.polygon(tri, outline=(*_CYA, 200), width=4)
        draw.line([(256, 200), (256, 290)], fill=(*_CYA, 220), width=6)
        draw.ellipse([246, 306, 266, 326], fill=(*_CYA, 220))
        img.save(os.path.join(place_dir, f"{name}.png"), "PNG")

    logger.info("Placeholders: generated missing-asset tiles")


# ---------------------------------------------------------------------------
# Badges
# ---------------------------------------------------------------------------

def generate_badges(target_root: str):
    badges_dir = ensure_dir(os.path.join(target_root, "badges"))
    badges = {
        "alpha":            _CYA,
        "beta":             _IND,
        "nightly":          _VIO,
        "stable":           _PRI,
        "experimental":     hex_to_rgb("#EC4899"),
        "ai_powered":       _CYA,
        "open_source":      _IND,
        "developer_preview": _VIO,
    }
    for name, accent in badges.items():
        label = name.upper().replace("_", " ")

        # SVG badge
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="160" height="40" viewBox="0 0 160 40">\n'
            f'  <defs>\n'
            f'    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="0%">\n'
            f'      <stop offset="0%" stop-color="#{_SURF[0]:02X}{_SURF[1]:02X}{_SURF[2]:02X}"/>\n'
            f'      <stop offset="100%" stop-color="#{_BG[0]:02X}{_BG[1]:02X}{_BG[2]:02X}"/>\n'
            f'    </linearGradient>\n'
            f'    <linearGradient id="border" x1="0%" y1="0%" x2="100%" y2="0%">\n'
            f'      <stop offset="0%" stop-color="#{accent[0]:02X}{accent[1]:02X}{accent[2]:02X}"/>\n'
            f'      <stop offset="100%" stop-color="#{_CYA[0]:02X}{_CYA[1]:02X}{_CYA[2]:02X}"/>\n'
            f'    </linearGradient>\n'
            f'  </defs>\n'
            f'  <rect width="160" height="40" rx="10" fill="url(#bg)" stroke="url(#border)" stroke-width="1.5"/>\n'
            f'  <circle cx="18" cy="20" r="5" fill="#{accent[0]:02X}{accent[1]:02X}{accent[2]:02X}"/>\n'
            f'  <text x="84" y="25" fill="#F9FAFB" font-family="Inter,sans-serif" '
            f'font-size="11" text-anchor="middle" font-weight="600">{label}</text>\n'
            f'</svg>'
        )
        with open(os.path.join(badges_dir, f"{name}.svg"), "w") as f:
            f.write(svg)

        # PNG badge
        img  = Image.new("RGBA", (320, 80), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle([2, 2, 318, 78], radius=20,
                                fill=(*_SURF, 240), outline=(*accent, 180), width=3)
        draw.rounded_rectangle([2, 2, 318, 12], radius=10, fill=(*accent, 180))
        draw.ellipse([22, 30, 42, 50], fill=(*accent, 220))
        img.save(os.path.join(badges_dir, f"{name}.png"), "PNG")

    logger.info(f"Badges: generated {len(badges)} SVG + PNG badges")


# ---------------------------------------------------------------------------
# Favicon package
# ---------------------------------------------------------------------------

def generate_favicon_package(target_root: str):
    fav_dir = ensure_dir(os.path.join(target_root, "favicon"))
    logo_path = os.path.join(target_root, "logos", "png", "512x512", "pyflare.png")

    if os.path.exists(logo_path):
        src = Image.open(logo_path).convert("RGBA")
    else:
        # Generate fallback from gradient
        src = build_radial_gradient_pixels(512, 512, _IND, _BG)

    src.save(os.path.join(fav_dir, "favicon.ico"),
             format="ICO",
             sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
    for s in [16, 32, 48, 64, 128, 256, 512]:
        src.resize((s, s), Image.Resampling.LANCZOS).save(
            os.path.join(fav_dir, f"favicon-{s}.png"), "PNG"
        )
    src.resize((180, 180), Image.Resampling.LANCZOS).save(
        os.path.join(fav_dir, "apple-touch-icon.png"), "PNG"
    )
    logger.info("Favicon: generated ICO + multi-size PNGs")


# ---------------------------------------------------------------------------
# Social banners
# ---------------------------------------------------------------------------

def generate_social_banners(target_root: str):
    soc_dir = ensure_dir(os.path.join(target_root, "social"))
    socials = {
        "github_banner.png":    (1920, 640, _IND),
        "linkedin_banner.png":  (1584, 396, _PRI),
        "x_banner.png":         (1500, 500, _CYA),
        "discord_banner.png":   (960,  540, _VIO),
        "open_graph.png":       (1200, 630, _IND),
        "website_hero.png":     (1920, 1080, _CYA),
        "launch_poster.png":    (1080, 1920, _VIO),
    }
    for filename, (w, h, accent) in socials.items():
        img = Image.new("RGBA", (w, h))
        img = draw_premium_background(img, accent=accent)
        img.convert("RGB").save(os.path.join(soc_dir, filename), "PNG")
    logger.info(f"Social: generated {len(socials)} banners")


# ---------------------------------------------------------------------------
# UI backgrounds
# ---------------------------------------------------------------------------

def generate_ui_backgrounds(target_root: str):
    ui_dir = ensure_dir(os.path.join(target_root, "ui"))
    uis = {
        "about_banner.png":         (800,  300, _IND),
        "dashboard_background.png": (1920, 1080, _CYA),
        "settings_background.png":  (1920, 1080, _VIO),
        "store_background.png":     (1920, 1080, _PRI),
        "welcome_background.png":   (1920, 1080, _IND),
        "terminal_background.png":  (1920, 1080, _CYA),
    }
    for filename, (w, h, accent) in uis.items():
        img = Image.new("RGBA", (w, h))
        img = draw_premium_background(img, accent=accent)
        img.convert("RGB").save(os.path.join(ui_dir, filename), "PNG")
    logger.info(f"UI: generated {len(uis)} backgrounds")


# ---------------------------------------------------------------------------
# Mockups / screenshots
# ---------------------------------------------------------------------------

def generate_mockups_and_screenshots(target_root: str):
    for folder, accent in [("mockups", _IND), ("screenshots", _CYA)]:
        out_dir = ensure_dir(os.path.join(target_root, folder))
        for name in ["desktop", "installer", "store", "terminal", "website"]:
            img = Image.new("RGBA", (1280, 720))
            img = draw_premium_background(img, accent=accent)
            draw = ImageDraw.Draw(img)
            # Fake UI chrome
            draw.rounded_rectangle([40, 40, 1240, 680], radius=16,
                                    fill=(*_SURF, 180), outline=(*accent, 60), width=1)
            draw.rounded_rectangle([40, 40, 1240, 76], radius=10,
                                    fill=(*_BG, 200))
            for ci, cc in enumerate([(239,68,68),(245,158,11),(16,185,129)]):
                draw.ellipse([56+ci*22, 52, 68+ci*22, 64], fill=(*cc, 220))
            img.convert("RGB").save(os.path.join(out_dir, f"{name}.png"), "PNG")
    logger.info("Mockups/Screenshots: generated")


# ---------------------------------------------------------------------------
# Splash screens
# ---------------------------------------------------------------------------

def generate_splash_screens(target_root: str):
    splash_dir = ensure_dir(os.path.join(target_root, "splash"))
    for name, accent in [("splash_dark", _IND), ("splash_midnight", _VIO),
                          ("splash_light", _PRI)]:
        img = Image.new("RGBA", (1920, 1080))
        img = draw_premium_background(img, accent=accent)
        draw = ImageDraw.Draw(img)
        # Central logo placeholder circle with glow
        cx, cy, cr = 960, 540, 100
        for r in range(cr + 60, cr, -8):
            a = int(50 * (1 - (r - cr) / 60.0))
            draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=(*accent, a))
        draw.ellipse([cx-cr, cy-cr, cx+cr, cy+cr],
                     fill=(*_SURF, 220), outline=(*accent, 180), width=4)
        img.convert("RGB").save(os.path.join(splash_dir, f"{name}.png"), "PNG")
    logger.info("Splash: generated screens")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def generate_all_extras(target_root: str) -> None:
    generate_login_assets(target_root)
    generate_installer_assets(target_root)
    generate_store_assets(target_root)
    generate_placeholders(target_root)
    generate_badges(target_root)
    generate_favicon_package(target_root)
    generate_social_banners(target_root)
    generate_ui_backgrounds(target_root)
    generate_mockups_and_screenshots(target_root)
    generate_splash_screens(target_root)
    logger.info("Extras: all premium assets generated")
