import os
import math
import logging
from PIL import Image, ImageDraw, ImageFilter
from branding_generator.config import BRAND_COLORS, TYPOGRAPHY
from branding_generator.utils import ensure_dir

logger = logging.getLogger("pyflare-brand")

def draw_futuristic_layout(draw, title, width, height, theme_color):
    # Base dark theme background
    draw.rectangle([0, 0, width, height], fill=(11, 15, 25, 255))
    
    # Grid lines
    grid_spacing = 80
    for x in range(0, width, grid_spacing):
        draw.line([(x, 0), (x, height)], fill=(31, 41, 55, 50), width=1)
    for y in range(0, height, grid_spacing):
        draw.line([(0, y), (width, y)], fill=(31, 41, 55, 50), width=1)
        
    # Cybernetic header border line
    draw.line([(0, 60), (width, 60)], fill=theme_color, width=4)
    
    # Modern text titles
    draw.text((30, 15), f"PYFLARE OS // {title.upper()}", fill=(255, 255, 255, 255))

def generate_login_assets(target_root):
    login_dir = os.path.join(target_root, "login")
    ensure_dir(login_dir)
    
    # Unique high-fidelity backgrounds
    bg_size = (1920, 1080)
    for name, theme_color in [("login_background", (91, 95, 255, 255)), ("lockscreen_background", (0, 212, 255, 255))]:
        img = Image.new("RGBA", bg_size)
        draw = ImageDraw.Draw(img)
        draw_futuristic_layout(draw, name.replace("_", " "), bg_size[0], bg_size[1], theme_color)
        img.save(os.path.join(login_dir, f"{name}.png"), "PNG")
        
    # Avatars & Icons
    for avatar in ["user_avatar", "guest_avatar"]:
        img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse([20, 20, 236, 236], fill=(17, 24, 39, 255), outline=BRAND_COLORS["indigo"], width=8)
        draw.ellipse([96, 60, 160, 124], fill=BRAND_COLORS["cyan"])
        draw.chord([64, 124, 192, 220], start=180, end=360, fill=BRAND_COLORS["indigo"])
        img.save(os.path.join(login_dir, f"{avatar}.png"), "PNG")

def generate_installer_assets(target_root):
    inst_dir = os.path.join(target_root, "installer")
    ensure_dir(inst_dir)
    
    # Installer Background
    img = Image.new("RGBA", (1920, 1080))
    draw = ImageDraw.Draw(img)
    draw_futuristic_layout(draw, "SYSTEM INSTALLER", 1920, 1080, (138, 92, 245, 255))
    img.save(os.path.join(inst_dir, "installer_background.png"), "PNG")
    
    # Installer progress states
    states = ["install_progress", "installing", "success", "finish", "error"]
    for state in states:
        img = Image.new("RGBA", (800, 500), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle([20, 20, 780, 480], radius=24, fill=(17, 24, 39, 255), outline=BRAND_COLORS["indigo"], width=6)
        draw.text((60, 80), f"INSTALLATION STATE: {state.upper()}", fill=(255, 255, 255, 255))
        # Draw a custom progress bar
        bar_color = BRAND_COLORS["cyan"] if state != "error" else "#EF4444"
        progress = 1.0 if state in ["success", "finish"] else (0.1 if state == "error" else 0.65)
        draw.rounded_rectangle([60, 240, 740, 270], radius=10, fill=(31, 41, 55, 255))
        draw.rounded_rectangle([60, 240, int(60 + 680 * progress), 270], radius=10, fill=bar_color)
        img.save(os.path.join(inst_dir, f"{state}.png"), "PNG")

def generate_store_assets(target_root):
    store_dir = os.path.join(target_root, "store")
    ensure_dir(store_dir)
    
    # Feature banners and app placeholders
    banners = {
        "featured_banner.png": (1200, 500, BRAND_COLORS["indigo"]),
        "application_placeholder.png": (600, 400, BRAND_COLORS["cyan"]),
        "plugin_placeholder.png": (600, 400, BRAND_COLORS["violet"]),
        "game_placeholder.png": (600, 400, BRAND_COLORS["primary"])
    }
    for filename, (w, h, theme_color) in banners.items():
        img = Image.new("RGBA", (w, h), (17, 24, 39, 255))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle([15, 15, w-15, h-15], radius=20, fill=(11, 15, 25, 255), outline=theme_color, width=6)
        draw.text((50, 50), filename.replace(".png", "").replace("_", " ").upper(), fill=(255, 255, 255, 255))
        img.save(os.path.join(store_dir, filename), "PNG")
        
    # Category Icons
    cat_dir = os.path.join(store_dir, "categories")
    ensure_dir(cat_dir)
    categories = {
        "utilities": BRAND_COLORS["cyan"],
        "games": BRAND_COLORS["violet"],
        "development": BRAND_COLORS["indigo"],
        "personalization": BRAND_COLORS["primary"]
    }
    for cat, color in categories.items():
        img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle([10, 10, 246, 246], radius=32, fill=(17, 24, 39, 255), outline=color, width=8)
        draw.text((40, 110), cat.upper()[:12], fill=(255, 255, 255, 255))
        img.save(os.path.join(cat_dir, f"{cat}.png"), "PNG")

def generate_placeholders(target_root):
    place_dir = os.path.join(target_root, "placeholders")
    ensure_dir(place_dir)
    placeholders = ["missing_texture", "missing_model", "missing_asset", "missing_icon", "unknown_file", "unknown_project"]
    for name in placeholders:
        img = Image.new("RGBA", (512, 512), (17, 24, 39, 255))
        draw = ImageDraw.Draw(img)
        # Cyber check pattern
        draw.rectangle([0, 0, 256, 256], fill=(255, 0, 220, 255))
        draw.rectangle([256, 256, 512, 512], fill=(255, 0, 220, 255))
        # Overlay details
        draw.rounded_rectangle([40, 40, 472, 472], radius=16, fill=(11, 15, 25, 200), outline=BRAND_COLORS["cyan"], width=4)
        draw.text((80, 240), f"MISSING: {name.upper()}", fill=(255, 255, 255, 255))
        img.save(os.path.join(place_dir, f"{name}.png"), "PNG")

def generate_badges(target_root):
    badges_dir = os.path.join(target_root, "badges")
    ensure_dir(badges_dir)
    badges = {
        "alpha": BRAND_COLORS["cyan"],
        "beta": BRAND_COLORS["indigo"],
        "nightly": BRAND_COLORS["violet"],
        "stable": BRAND_COLORS["primary"],
        "experimental": "#EC4899",
        "ai_powered": BRAND_COLORS["cyan"],
        "open_source_ready": BRAND_COLORS["indigo"],
        "developer_preview": BRAND_COLORS["violet"]
    }
    for name, color in badges.items():
        svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg" width="160" height="40" viewBox="0 0 160 40">
  <rect width="160" height="40" rx="10" fill="#111827" stroke="{color}" stroke-width="2"/>
  <text x="80" y="25" fill="#FFFFFF" font-family="sans-serif" font-size="12" text-anchor="middle" font-weight="bold">{name.upper().replace("_", " ")}</text>
</svg>'''
        with open(os.path.join(badges_dir, f"{name}.svg"), "w") as f:
            f.write(svg_content)
            
        # Draw high-fidelity PNG badge
        img = Image.new("RGBA", (320, 80), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle([4, 4, 316, 76], radius=20, fill=(17, 24, 39, 255), outline=color, width=4)
        draw.text((60, 26), name.upper().replace("_", " "), fill=(255, 255, 255, 255))
        img.save(os.path.join(badges_dir, f"{name}.png"), "PNG")

def generate_favicon_package(target_root):
    fav_dir = os.path.join(target_root, "favicon")
    ensure_dir(fav_dir)
    
    logo_path = os.path.join(target_root, "logos", "png", "512x512", "pyflare.png")
    if os.path.exists(logo_path):
        with Image.open(logo_path) as logo:
            logo.save(os.path.join(fav_dir, "favicon.ico"), format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
            for s in [16, 32, 48, 64, 128, 256, 512]:
                logo.resize((s, s), Image.Resampling.LANCZOS).save(os.path.join(fav_dir, f"favicon-{s}.png"), "PNG")
            logo.resize((180, 180), Image.Resampling.LANCZOS).save(os.path.join(fav_dir, "apple-touch-icon.png"), "PNG")
    else:
        # Fallback empty ICO if main logo not generated yet
        img = Image.new("RGBA", (128, 128), BRAND_COLORS["indigo"])
        img.save(os.path.join(fav_dir, "favicon.ico"))

def generate_social_banners(target_root):
    soc_dir = os.path.join(target_root, "social")
    ensure_dir(soc_dir)
    
    socials = {
        "github_banner.png": (1920, 640, BRAND_COLORS["indigo"]),
        "linkedin_banner.png": (1584, 396, BRAND_COLORS["primary"]),
        "x_banner.png": (1500, 500, BRAND_COLORS["cyan"]),
        "discord_banner.png": (960, 540, BRAND_COLORS["violet"]),
        "reddit_banner.png": (1200, 400, BRAND_COLORS["indigo"]),
        "website_hero.png": (1920, 1080, BRAND_COLORS["cyan"]),
        "profile_header.png": (1200, 600, BRAND_COLORS["primary"]),
        "open_graph.png": (1200, 630, BRAND_COLORS["indigo"]),
        "launch_poster.png": (1080, 1920, BRAND_COLORS["violet"]),
        "community_banner.png": (1200, 400, BRAND_COLORS["cyan"])
    }
    
    for filename, (w, h, theme_color) in socials.items():
        img = Image.new("RGBA", (w, h))
        draw = ImageDraw.Draw(img)
        draw_futuristic_layout(draw, filename.replace(".png", "").replace("_", " "), w, h, theme_color)
        img.save(os.path.join(soc_dir, filename), "PNG")

def generate_ui_backgrounds(target_root):
    ui_dir = os.path.join(target_root, "ui")
    ensure_dir(ui_dir)
    
    uis = {
        "about_banner.png": (800, 300, BRAND_COLORS["indigo"]),
        "dashboard_background.png": (1920, 1080, BRAND_COLORS["cyan"]),
        "settings_background.png": (1920, 1080, BRAND_COLORS["violet"]),
        "store_background.png": (1920, 1080, BRAND_COLORS["primary"]),
        "welcome_background.png": (1920, 1080, BRAND_COLORS["indigo"]),
        "terminal_background.png": (1920, 1080, BRAND_COLORS["cyan"])
    }
    
    for filename, (w, h, theme_color) in uis.items():
        img = Image.new("RGBA", (w, h))
        draw = ImageDraw.Draw(img)
        draw_futuristic_layout(draw, filename.replace(".png", "").replace("_", " "), w, h, theme_color)
        img.save(os.path.join(ui_dir, filename), "PNG")

def generate_mockups_and_screenshots(target_root):
    mock_dir = os.path.join(target_root, "mockups")
    screen_dir = os.path.join(target_root, "screenshots")
    ensure_dir(mock_dir)
    ensure_dir(screen_dir)
    
    files = ["desktop", "installer", "store", "terminal", "website"]
    for f in files:
        # Mockups
        img_mock = Image.new("RGBA", (1280, 720))
        draw_mock = ImageDraw.Draw(img_mock)
        draw_futuristic_layout(draw_mock, f"mockup: {f}", 1280, 720, BRAND_COLORS["indigo"])
        img_mock.save(os.path.join(mock_dir, f"{f}.png"), "PNG")
        
        # Screenshots
        img_screen = Image.new("RGBA", (1280, 720))
        draw_screen = ImageDraw.Draw(img_screen)
        draw_futuristic_layout(draw_screen, f"screenshot: {f}", 1280, 720, BRAND_COLORS["cyan"])
        img_screen.save(os.path.join(screen_dir, f"{f}.png" if "desktop" not in f else f"{f}_dark.png"), "PNG")

def generate_all_extras(target_root):
    generate_login_assets(target_root)
    generate_installer_assets(target_root)
    generate_store_assets(target_root)
    generate_placeholders(target_root)
    generate_badges(target_root)
    generate_favicon_package(target_root)
    generate_social_banners(target_root)
    generate_ui_backgrounds(target_root)
    generate_mockups_and_screenshots(target_root)
    logger.info("Successfully generated all high-fidelity extra branding layouts")
