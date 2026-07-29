import os
import math
import logging
from PIL import Image, ImageDraw
from branding_generator.utils import ensure_dir

logger = logging.getLogger("pyflare-brand")

def generate_animated_webp(frames, output_path, duration_ms=100):
    if len(frames) > 0:
        frames[0].save(
            output_path,
            format="WEBP",
            save_all=True,
            append_images=frames[1:],
            duration=duration_ms,
            loop=0
        )

def generate_animated_gif(frames, output_path, duration_ms=100):
    if len(frames) > 0:
        # Convert frames to RGB/P mode for GIF compatibility
        gif_frames = [f.convert("RGBA") for f in frames]
        gif_frames[0].save(
            output_path,
            format="GIF",
            save_all=True,
            append_images=gif_frames[1:],
            duration=duration_ms,
            loop=0,
            disposal=2
        )

def generate_all_animations(target_root):
    anim_dir = os.path.join(target_root, "animations")
    ensure_dir(anim_dir)
    
    categories = ["boot", "shutdown", "loading", "success", "error"]
    for cat in categories:
        cat_dir = os.path.join(anim_dir, cat)
        ensure_dir(cat_dir)
        
        frames = []
        # Generate 12 frames of smooth transition/spinning
        for f in range(12):
            img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            angle = (f / 12.0) * 2 * math.pi
            
            if cat == "loading":
                # Spinning circular track dots
                for i in range(8):
                    dot_angle = angle + (i / 8.0) * 2 * math.pi
                    cx = 128 + int(70 * math.cos(dot_angle))
                    cy = 128 + int(70 * math.sin(dot_angle))
                    alpha = int(255 * (i / 8.0))
                    draw.ellipse([cx-10, cy-10, cx+10, cy+10], fill=(0, 212, 255, alpha))
            else:
                # Pulse scaling logo
                scale = 0.8 + 0.2 * math.sin(angle)
                size = int(60 * scale)
                draw.polygon([
                    (128, 128 - size),
                    (128 - size, 128 + size),
                    (128 + size, 128 + size)
                ], fill=(91, 95, 255, 255))
                
            frame_path = os.path.join(cat_dir, f"frame_{f:02d}.png")
            img.save(frame_path, "PNG")
            frames.append(img)
            
        # Compile WebP and GIF animations directly into the animations directory
        generate_animated_webp(frames, os.path.join(anim_dir, f"{cat}.webp"))
        generate_animated_gif(frames, os.path.join(anim_dir, f"{cat}.gif"))
        
    logger.info("Successfully generated boot and system animations (WebP + GIF + frame sequences)")

