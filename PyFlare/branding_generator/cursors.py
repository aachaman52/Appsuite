import os
import struct
import logging
from PIL import Image
from branding_generator.utils import ensure_dir

logger = logging.getLogger("pyflare-brand")

CURSORS_CONFIG = {
    "default": (0, 0),
    "pointer": (0, 0),
    "hand": (16, 0),
    "text": (16, 16),
    "busy": (16, 16),
    "working": (16, 16),
    "move": (16, 16),
    "crosshair": (16, 16),
    "forbidden": (16, 16),
    "resize_horizontal": (16, 16),
    "resize_vertical": (16, 16),
    "resize_diagonal": (16, 16),
    "precision_select": (16, 16)
}

def save_win_cur(png_path, cur_path, hotspot=(0, 0)):
    # Read PNG image
    img = Image.open(png_path)
    img = img.resize((32, 32), Image.Resampling.LANCZOS)
    
    # Write CUR binary structure
    # Header: Reserved (2 bytes), Type (2 bytes, value=2 for CUR), Count (2 bytes, value=1)
    header = struct.pack("<HHH", 0, 2, 1)
    
    # Save image as PNG raw bytes to embed in the cursor
    import io
    png_bytes = io.BytesIO()
    img.save(png_bytes, format="PNG")
    png_data = png_bytes.getvalue()
    
    # Directory entry: Width (1), Height (1), ColorCount (1), Reserved (1), Hotspot X (2), Hotspot Y (2), BytesSize (4), Offset (4)
    # Note: 0 for width/height means 256, but here we use 32
    w, h = img.size
    entry = struct.pack("<BBBBHHII", w, h, 0, 0, hotspot[0], hotspot[1], len(png_data), 22)
    
    with open(cur_path, "wb") as f:
        f.write(header)
        f.write(entry)
        f.write(png_data)

def generate_cursor_themes(target_root):
    cursors_dir = os.path.join(target_root, "cursors")
    ensure_dir(cursors_dir)
    
    # Create Linux index.theme
    index_theme = '''[Icon Theme]
Name=PyFlare
Comment=Premium PyFlare OS Cursor Theme
Inherits=Adwaita
'''
    with open(os.path.join(cursors_dir, "index.theme"), "w") as f:
        f.write(index_theme)
        
    # Generate .cur files for Windows
    for name, hotspot in CURSORS_CONFIG.items():
        src_png = os.path.join(cursors_dir, f"{name}.png")
        if os.path.exists(src_png):
            cur_path = os.path.join(cursors_dir, f"{name}.cur")
            save_win_cur(src_png, cur_path, hotspot)
            
    logger.info("Successfully generated cursor themes for Windows and Linux")
