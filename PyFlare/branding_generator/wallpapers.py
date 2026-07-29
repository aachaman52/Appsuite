import os
import math
import logging
from PIL import Image, ImageDraw, ImageFilter
from branding_generator.utils import ensure_dir

logger = logging.getLogger("pyflare-brand")

def generate_procedural_wallpaper(width, height, output_path, wp_type):
    img = Image.new("RGBA", (width, height), (11, 15, 25, 255))
    w_small, h_small = width // 4, height // 4
    canvas = Image.new("RGBA", (w_small, h_small), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    
    if wp_type == "default_dark":
        for x in range(w_small):
            y_indigo = int((h_small / 2) + (h_small / 5) * math.sin(x * 0.04))
            for dy in range(-35, 35):
                alpha = int(35 * (1.0 - abs(dy) / 35.0))
                if 0 <= y_indigo + dy < h_small:
                    draw.point((x, y_indigo + dy), fill=(91, 95, 255, alpha))
            y_cyan = int((h_small / 2) + (h_small / 6) * math.cos(x * 0.03 + 2.0))
            for dy in range(-30, 30):
                alpha = int(45 * (1.0 - abs(dy) / 30.0))
                if 0 <= y_cyan + dy < h_small:
                    draw.point((x, y_cyan + dy), fill=(0, 212, 255, alpha))
    elif wp_type == "aurora":
        # Wavy ribbons wrapping diagonally
        for x in range(w_small):
            y_base = int((h_small * x) / w_small + 50 * math.sin(x * 0.05))
            for dy in range(-50, 50):
                alpha = int(40 * (1.0 - abs(dy) / 50.0))
                if 0 <= y_base + dy < h_small:
                    draw.point((x, y_base + dy), fill=(138, 92, 245, alpha)) # Violet
    elif wp_type == "abstract_blue":
        # Multi-frequency concentric wave structures
        for y in range(h_small):
            for x in range(w_small):
                val = math.sin(x * 0.08) * math.cos(y * 0.08)
                if val > 0.4:
                    alpha = int(50 * (val - 0.4))
                    draw.point((x, y), fill=(0, 212, 255, alpha))
    elif wp_type == "minimal_dark":
        # Faint glow in the absolute center
        cx, cy = w_small // 2, h_small // 2
        for r in range(10, 80, 5):
            alpha = int(30 * (1.0 - r / 80.0))
            draw.ellipse([cx-r, cy-r, cx+r, cy+r], outline=(91, 95, 255, alpha), width=4)
            
    # Scale up and apply blur for organic glow
    glow_map = canvas.resize((width, height), Image.Resampling.BILINEAR)
    glow_map_blurred = glow_map.filter(ImageFilter.GaussianBlur(radius=60))
    
    final_img = Image.alpha_composite(img, glow_map_blurred)
    final_img.save(output_path, "PNG")

def generate_all_wallpapers(target_root):
    wallpapers_dir = os.path.join(target_root, "wallpapers")
    ensure_dir(wallpapers_dir)
    
    wallpapers = {
        "default_dark.png": "default_dark",
        "aurora.png": "aurora",
        "abstract_blue.png": "abstract_blue",
        "minimal_dark.png": "minimal_dark"
    }
    
    for filename, wp_type in wallpapers.items():
        output_path = os.path.join(wallpapers_dir, filename)
        generate_procedural_wallpaper(3840, 2160, output_path, wp_type)
        
    logger.info("Successfully generated all procedural desktop wallpapers")

