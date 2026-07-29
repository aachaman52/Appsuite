import os
import logging
from PIL import Image, ImageDraw
from branding_generator.utils import ensure_dir

logger = logging.getLogger("pyflare-brand")

def generate_preview_grid(image_paths, output_path, cols=4, tile_size=128):
    if not image_paths:
        return
    rows = (len(image_paths) + cols - 1) // cols
    grid_img = Image.new("RGBA", (cols * tile_size, rows * tile_size), (11, 15, 25, 255))
    
    for idx, path in enumerate(image_paths):
        if not os.path.exists(path):
            continue
        with Image.open(path) as tile:
            tile_resized = tile.resize((tile_size - 10, tile_size - 10), Image.Resampling.LANCZOS)
            x = (idx % cols) * tile_size + 5
            y = (idx // cols) * tile_size + 5
            grid_img.paste(tile_resized, (x, y), tile_resized.convert("RGBA"))
            
    grid_img.save(output_path, "PNG")

def generate_all_previews(target_root):
    previews_dir = os.path.join(target_root, "previews")
    ensure_dir(previews_dir)
    
    # 1. Icons Preview Grid
    png_dir = os.path.join(target_root, "logos", "png", "256x256")
    icon_paths = []
    if os.path.exists(png_dir):
        icon_paths = [os.path.join(png_dir, f) for f in os.listdir(png_dir) if f.endswith(".png")]
    generate_preview_grid(icon_paths, os.path.join(previews_dir, "branding_preview.png"), cols=4, tile_size=256)
    
    # 2. Wallpapers Preview
    wp_dir = os.path.join(target_root, "wallpapers")
    wp_paths = []
    if os.path.exists(wp_dir):
        wp_paths = [os.path.join(wp_dir, f) for f in os.listdir(wp_dir) if f.endswith(".png")]
    generate_preview_grid(wp_paths, os.path.join(previews_dir, "wallpaper_preview.png"), cols=2, tile_size=512)
    
    # 3. Badges Preview
    bg_dir = os.path.join(target_root, "badges")
    bg_paths = []
    if os.path.exists(bg_dir):
        bg_paths = [os.path.join(bg_dir, f) for f in os.listdir(bg_dir) if f.endswith(".png")]
    generate_preview_grid(bg_paths, os.path.join(previews_dir, "badge_preview.png"), cols=4, tile_size=180)
    
    logger.info("Successfully generated preview sheets for icons, wallpapers, and badges")
