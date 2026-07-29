import os
import math
import logging

def setup_logger(verbose=False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s [%(levelname)s] %(message)s")
    return logging.getLogger("pyflare-brand")

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

# Math & SDF helper functions
def sdf_circle(x, y, cx, cy, r):
    return math.sqrt((x - cx) ** 2 + (y - cy) ** 2) - r

def sdf_box(x, y, cx, cy, w, h):
    dx = abs(x - cx) - w / 2
    dy = abs(y - cy) - h / 2
    return math.sqrt(max(dx, 0) ** 2 + max(dy, 0) ** 2) + min(max(dx, dy), 0.0)

def smoothstep(edge0, edge1, x):
    t = max(0.0, min(1.0, (x - edge0) / (edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)
