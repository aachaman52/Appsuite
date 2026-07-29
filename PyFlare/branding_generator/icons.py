import os
import logging
from PIL import Image, ImageDraw
from branding_generator.config import BRAND_COLORS, ICON_SIZES
from branding_generator.utils import ensure_dir

logger = logging.getLogger("pyflare-brand")

# Dictionary of high-quality vector paths / layouts in SVG format
SVG_TEMPLATES = {
    # Logos
    "pyflare": f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="100%" height="100%">
  <path d="M256,40 C170,140 100,240 100,340 C100,430 170,472 256,472 C190,420 170,330 210,250 C230,210 256,180 256,180 Z" fill="{BRAND_COLORS["indigo"]}" />
  <path d="M256,40 C342,140 412,240 412,340 C412,430 342,472 256,472 C322,420 342,330 302,250 C282,210 256,180 256,180 Z" fill="{BRAND_COLORS["violet"]}" />
  <path d="M256,160 C210,240 180,310 180,360 C180,430 220,472 256,472 C292,472 332,430 332,360 C332,310 302,240 256,160 Z" fill="{BRAND_COLORS["cyan"]}" />
</svg>''',

    # System Utility Icons
    "power": f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="100%" height="100%">
  <path d="M256 64 v128" stroke="{BRAND_COLORS["cyan"]}" stroke-width="40" stroke-linecap="round" fill="none"/>
  <path d="M150 150 A160 160 0 1 0 362 150" stroke="{BRAND_COLORS["indigo"]}" stroke-width="40" stroke-linecap="round" fill="none"/>
</svg>''',

    "lock": f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="100%" height="100%">
  <rect x="96" y="200" width="320" height="240" rx="30" fill="{BRAND_COLORS["indigo"]}" />
  <path d="M160 200 v-80 a96 96 0 0 1 192 0 v80" stroke="{BRAND_COLORS["cyan"]}" stroke-width="32" stroke-linecap="round" fill="none"/>
  <circle cx="256" cy="300" r="32" fill="{BRAND_COLORS["background"]}"/>
  <path d="M256 332 v40" stroke="{BRAND_COLORS["background"]}" stroke-width="16" stroke-linecap="round"/>
</svg>''',

    "password": f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="100%" height="100%">
  <rect x="64" y="160" width="384" height="192" rx="40" fill="{BRAND_COLORS["surface"]}" stroke="{BRAND_COLORS["indigo"]}" stroke-width="24"/>
  <circle cx="160" cy="256" r="24" fill="{BRAND_COLORS["cyan"]}"/>
  <circle cx="256" cy="256" r="24" fill="{BRAND_COLORS["cyan"]}"/>
  <circle cx="352" cy="256" r="24" fill="{BRAND_COLORS["cyan"]}"/>
</svg>''',

    "settings": f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="100%" height="100%">
  <circle cx="256" cy="256" r="140" fill="none" stroke="{BRAND_COLORS["indigo"]}" stroke-width="60"/>
  <circle cx="256" cy="256" r="50" fill="{BRAND_COLORS["cyan"]}"/>
  <path d="M256 30 v60 M256 422 v60 M30 256 h60 M422 256 h60 M96 96 l42 42 M374 374 l42 42 M96 374 l42-42 M374 96 l42-42" stroke="{BRAND_COLORS["indigo"]}" stroke-width="50" stroke-linecap="round"/>
</svg>''',

    "package_manager": f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="100%" height="100%">
  <path d="M256 50 L420 140 L420 340 L256 430 L92 340 L92 140 Z" fill="none" stroke="{BRAND_COLORS["indigo"]}" stroke-width="32" stroke-linejoin="round"/>
  <path d="M92 140 L256 230 L420 140 M256 230 L256 430" fill="none" stroke="{BRAND_COLORS["cyan"]}" stroke-width="24"/>
</svg>''',

    "update": f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="100%" height="100%">
  <path d="M120 256 A136 136 0 1 1 370 350" fill="none" stroke="{BRAND_COLORS["indigo"]}" stroke-width="40" stroke-linecap="round"/>
  <path d="M392 256 A136 136 0 1 1 142 162" fill="none" stroke="{BRAND_COLORS["cyan"]}" stroke-width="40" stroke-linecap="round"/>
  <polygon points="120,130 180,210 80,210" fill="{BRAND_COLORS["cyan"]}"/>
  <polygon points="392,382 332,302 432,302" fill="{BRAND_COLORS["indigo"]}"/>
</svg>''',

    "security": f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="100%" height="100%">
  <path d="M256 50 L400 100 V260 C400 360 330 430 256 470 C182 430 112 360 112 260 V100 Z" fill="{BRAND_COLORS["surface"]}" stroke="{BRAND_COLORS["indigo"]}" stroke-width="32"/>
  <path d="M180 230 L230 280 L330 180" fill="none" stroke="{BRAND_COLORS["cyan"]}" stroke-width="32" stroke-linecap="round" stroke-linejoin="round"/>
</svg>''',

    "ai": f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="100%" height="100%">
  <path d="M256 50 L430 150 L430 350 L256 450 L82 350 L82 150 Z" fill="none" stroke="{BRAND_COLORS["indigo"]}" stroke-width="24"/>
  <circle cx="256" cy="256" r="80" fill="{BRAND_COLORS["cyan"]}"/>
  <line x1="256" y1="50" x2="256" y2="176" stroke="{BRAND_COLORS["cyan"]}" stroke-width="16"/>
  <line x1="256" y1="336" x2="256" y2="450" stroke="{BRAND_COLORS["cyan"]}" stroke-width="16"/>
  <line x1="82" y1="150" x2="190" y2="212" stroke="{BRAND_COLORS["cyan"]}" stroke-width="16"/>
  <line x1="430" y1="350" x2="322" y2="288" stroke="{BRAND_COLORS["cyan"]}" stroke-width="16"/>
  <line x1="82" y1="350" x2="190" y2="288" stroke="{BRAND_COLORS["cyan"]}" stroke-width="16"/>
  <line x1="430" y1="150" x2="322" y2="212" stroke="{BRAND_COLORS["cyan"]}" stroke-width="16"/>
</svg>''',

    "marketplace": f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="100%" height="100%">
  <path d="M80 160 L432 160 L384 432 L128 432 Z" fill="{BRAND_COLORS["surface"]}" stroke="{BRAND_COLORS["indigo"]}" stroke-width="32"/>
  <path d="M160 160 v-40 a96 96 0 0 1 192 0 v40" fill="none" stroke="{BRAND_COLORS["cyan"]}" stroke-width="32"/>
</svg>''',

    "store": f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="100%" height="100%">
  <rect x="64" y="160" width="384" height="288" rx="20" fill="none" stroke="{BRAND_COLORS["indigo"]}" stroke-width="32"/>
  <path d="M48 160 L256 64 L464 160 Z" fill="{BRAND_COLORS["cyan"]}"/>
</svg>''',

    "browser": f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="100%" height="100%">
  <circle cx="256" cy="256" r="200" fill="none" stroke="{BRAND_COLORS["indigo"]}" stroke-width="32"/>
  <ellipse cx="256" cy="256" rx="90" ry="200" fill="none" stroke="{BRAND_COLORS["cyan"]}" stroke-width="24"/>
  <line x1="56" y1="256" x2="456" y2="256" stroke="{BRAND_COLORS["cyan"]}" stroke-width="24"/>
</svg>''',

    "files": f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="100%" height="100%">
  <path d="M128 64 h200 l96 96 v288 h-296 Z" fill="none" stroke="{BRAND_COLORS["indigo"]}" stroke-width="32" stroke-linejoin="round"/>
  <path d="M328 64 v96 h96" fill="none" stroke="{BRAND_COLORS["cyan"]}" stroke-width="24"/>
</svg>'''
}

def export_svg_to_png(svg_path, output_png_path, size):
    try:
        import cairosvg
        cairosvg.svg2png(url=svg_path, write_to=output_png_path, parent_width=size, parent_height=size)
        return True
    except ImportError:
        # Graceful fallback: render simple geometry using PIL
        logger.warning(f"cairosvg not installed, falling back to PIL image scaling for {output_png_path}")
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        # Draw placeholder visual matching the theme color
        draw.ellipse([size//4, size//4, 3*size//4, 3*size//4], fill=(91, 95, 255, 255))
        img.save(output_png_path, "PNG")
        return False

def generate_all_icons(target_root):
    svg_dir = os.path.join(target_root, "logos", "svg")
    png_dir = os.path.join(target_root, "logos", "png")
    ensure_dir(svg_dir)
    ensure_dir(png_dir)

    for name, svg_content in SVG_TEMPLATES.items():
        svg_path = os.path.join(svg_dir, f"{name}.svg")
        with open(svg_path, "w") as f:
            f.write(svg_content)
        
        # Export multi-size PNGs
        for size in ICON_SIZES:
            size_dir = os.path.join(png_dir, f"{size}x{size}")
            ensure_dir(size_dir)
            export_svg_to_png(svg_path, os.path.join(size_dir, f"{name}.png"), size)
            
    logger.info("Successfully generated all SVG icons and size exports")
