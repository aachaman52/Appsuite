import os
import shutil
import logging
from branding_generator.utils import ensure_dir

logger = logging.getLogger("pyflare-brand")

def export_vector_logos(target_root):
    export_dir = os.path.join(target_root, "export")
    ensure_dir(export_dir)
    
    svg_path = os.path.join(target_root, "logos", "svg", "pyflare.svg")
    if not os.path.exists(svg_path):
        logger.error(f"Source SVG not found at {svg_path}")
        return
        
    # Copy main SVG
    shutil.copy2(svg_path, os.path.join(export_dir, "logo.svg"))
    
    # Try using cairosvg for proper conversion
    try:
        import cairosvg
        cairosvg.svg2pdf(url=svg_path, write_to=os.path.join(export_dir, "logo.pdf"))
        cairosvg.svg2ps(url=svg_path, write_to=os.path.join(export_dir, "logo.eps"))
        logger.info("Successfully exported PDF and EPS using CairoSVG")
    except ImportError:
        logger.warning("cairosvg not installed, writing basic SVG structure as PDF/EPS placeholders")
        # Save placeholder EPS/PDF files
        with open(os.path.join(export_dir, "logo.pdf"), "w") as f:
            f.write("%PDF-1.4\n%Placeholder for PyFlare Vector PDF logo")
        with open(os.path.join(export_dir, "logo.eps"), "w") as f:
            f.write("%!PS-Adobe-3.0 EPSF-3.0\n%Placeholder for PyFlare EPS logo")
            
    # Copy raster PNG logo
    png_src = os.path.join(target_root, "logos", "png", "1024x1024", "pyflare.png")
    if os.path.exists(png_src):
        shutil.copy2(png_src, os.path.join(export_dir, "logo.png"))
