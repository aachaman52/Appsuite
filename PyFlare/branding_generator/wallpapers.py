import os
import math
import logging
from PIL import Image, ImageDraw, ImageFilter
from branding_generator.utils import ensure_dir

logger = logging.getLogger("pyflare-brand")

def generate_procedural_wallpaper(width, height, output_path):
    # Generates a premium math-based light trail / aurora wallpaper
    img = Image.new("RGBA", (width, height), (11, 15, 25, 255))
    
    # We render the gradient trails at 1/4 resolution for performance and blend quality
    w_small, h_small = width // 4, height // 4
    canvas = Image.new("RGBA", (w_small, h_small), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    
    for x in range(w_small):
        # Upper indigo trail
        y_indigo = int((h_small / 2) + (h_small / 5) * math.sin(x * 0.04))
        for dy in range(-35, 35):
            alpha = int(35 * (1.0 - abs(dy) / 35.0))
            if 0 <= y_indigo + dy < h_small:
                draw.point((x, y_indigo + dy), fill=(91, 95, 255, alpha))
                
        # Lower cyan trail
        y_cyan = int((h_small / 2) + (h_small / 6) * math.cos(x * 0.03 + 2.0))
        for dy in range(-30, 30):
            alpha = int(45 * (1.0 - abs(dy) / 30.0))
            if 0 <= y_cyan + dy < h_small:
                draw.point((x, y_cyan + dy), fill=(0, 212, 255, alpha))
                
    # Scale up and apply blur for organic glow
    glow_map = canvas.resize((width, height), Image.Resampling.BILINEAR)
    glow_map_blurred = glow_map.filter(ImageFilter.GaussianBlur(radius=60))
    
    final_img = Image.alpha_composite(img, glow_map_blurred)
    final_img.save(output_path, "PNG")

def generate_all_wallpapers(target_root):
    wallpapers_dir = os.path.join(target_root, "wallpapers")
    ensure_dir(wallpapers_dir)
    
    wallpapers = {
        "default_dark.png": (3840, 2160),
        "aurora.png": (3840, 2160),
        "abstract_blue.png": (3840, 2160),
        "minimal_dark.png": (3840, 2160)
    }
    
    for filename, size in wallpapers.items():
        output_path = os.path.join(wallpapers_dir, filename)
        generate_procedural_wallpaper(size[0], size[1], output_path)
        
    logger.info("Successfully generated all procedural desktop wallpapers")
