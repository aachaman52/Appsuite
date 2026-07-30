"""
branding_generator/icons.py
SVG-first icon generation for the PyFlare brand.

Every icon is authored as a 512×512 SVG with:
  - Named <linearGradient> / <radialGradient> defs
  - <filter> based drop-shadow and glow effects
  - Proper stroke-linecap/linejoin="round"
  - 32px safe-zone margin

PNG exports at all ICON_SIZES use cairosvg (output_width/output_height —
the correct parameter names). PIL provides a high-quality fallback
that renders a gradient circle in the icon's dominant colour rather than
a plain solid circle.
"""

import os
import logging
from branding_generator.config import BRAND_COLORS, ICON_SIZES, VERSION
from branding_generator.utils import (
    ensure_dir, file_sha256, content_sha256,
    svg_linear_gradient, svg_radial_gradient,
    svg_drop_shadow_filter, svg_glow_filter,
    ProgressReporter, BuildCache,
)

logger = logging.getLogger("pyflare-brand")

# ---------------------------------------------------------------------------
# Colour aliases (shorter names inside SVG strings)
# ---------------------------------------------------------------------------
_IND  = BRAND_COLORS["indigo"]    # #5B5FFF
_CYA  = BRAND_COLORS["cyan"]      # #00D4FF
_VIO  = BRAND_COLORS["violet"]    # #8A5CF5
_PRI  = BRAND_COLORS["primary"]   # #3B82F6
_BG   = BRAND_COLORS["background"]  # #0B0F19
_SURF = BRAND_COLORS["surface"]   # #111827
_WHT  = BRAND_COLORS["white"]


def _svg_wrap(defs_content: str, body_content: str, viewbox: str = "0 0 512 512") -> str:
    """Wrap defs + body inside a well-formed SVG root element."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}" '
        f'width="512" height="512">\n'
        f'<defs>\n{defs_content}</defs>\n'
        f'{body_content}\n'
        f'</svg>'
    )


# ---------------------------------------------------------------------------
# Icon SVG definitions
# ---------------------------------------------------------------------------

def _icon_pyflare() -> str:
    defs = (
        svg_linear_gradient("flameGrad", [("0%", _IND), ("50%", _PRI), ("100%", _CYA)],
                             x1="20%", y1="0%", x2="80%", y2="100%") +
        svg_linear_gradient("flameLeft", [("0%", _IND), ("100%", _VIO)],
                             x1="0%", y1="0%", x2="100%", y2="100%") +
        svg_radial_gradient("glowCenter", [("0%", _CYA + "99"), ("100%", _IND + "00")]) +
        svg_glow_filter("flameGlow", _CYA, stddev=16) +
        svg_drop_shadow_filter("flameShadow", dy=8, stddev=12, opacity=0.6)
    )
    body = """
  <!-- Outer left petal -->
  <path d="M256,52 C195,120 128,205 128,320 C128,400 185,456 240,472
           C200,440 178,380 195,298 C210,228 240,178 256,148 Z"
        fill="url(#flameLeft)" filter="url(#flameShadow)"/>
  <!-- Outer right petal -->
  <path d="M256,52 C317,120 384,205 384,320 C384,400 327,456 272,472
           C312,440 334,380 317,298 C302,228 272,178 256,148 Z"
        fill="url(#flameGrad)" filter="url(#flameShadow)"/>
  <!-- Core inner flame -->
  <path d="M256,140 C220,210 196,278 196,340 C196,410 226,460 256,472
           C286,460 316,410 316,340 C316,278 292,210 256,140 Z"
        fill="url(#flameGrad)" filter="url(#flameGlow)"/>
  <!-- Glow core -->
  <ellipse cx="256" cy="380" rx="48" ry="36" fill="url(#glowCenter)" opacity="0.7"/>
"""
    return _svg_wrap(defs, body)


def _icon_power() -> str:
    defs = (
        svg_linear_gradient("pwrGrad", [("0%", _CYA), ("100%", _IND)],
                             x1="0%", y1="0%", x2="0%", y2="100%") +
        svg_glow_filter("pwrGlow", _CYA, stddev=10) +
        svg_drop_shadow_filter("pwrShadow", dy=4, stddev=8, opacity=0.5)
    )
    body = """
  <!-- Ring arc -->
  <path d="M148,176 A132,132 0 1 0 364,176"
        stroke="url(#pwrGrad)" stroke-width="36" stroke-linecap="round"
        fill="none" filter="url(#pwrGlow)"/>
  <!-- Stem -->
  <line x1="256" y1="56" x2="256" y2="216"
        stroke="url(#pwrGrad)" stroke-width="36" stroke-linecap="round"
        filter="url(#pwrGlow)"/>
  <!-- Inner ring glow -->
  <circle cx="256" cy="280" r="60" fill="none"
          stroke="url(#pwrGrad)" stroke-width="4" opacity="0.3"/>
"""
    return _svg_wrap(defs, body)


def _icon_lock() -> str:
    defs = (
        svg_linear_gradient("lockBody", [("0%", _IND), ("100%", _VIO)],
                             x1="0%", y1="0%", x2="0%", y2="100%") +
        svg_linear_gradient("lockShackle", [("0%", _CYA), ("100%", _IND)],
                             x1="0%", y1="0%", x2="100%", y2="0%") +
        svg_drop_shadow_filter("lockShadow", dy=6, stddev=10, opacity=0.5) +
        svg_glow_filter("lockGlow", _IND, stddev=8)
    )
    body = f"""
  <!-- Shackle -->
  <path d="M164,216 v-88 a92,92 0 0 1 184,0 v88"
        stroke="url(#lockShackle)" stroke-width="28" stroke-linecap="round"
        fill="none" filter="url(#lockGlow)"/>
  <!-- Body -->
  <rect x="96" y="212" width="320" height="244" rx="28"
        fill="url(#lockBody)" filter="url(#lockShadow)"/>
  <!-- Keyhole ring -->
  <circle cx="256" cy="312" r="28" fill="{_BG}" opacity="0.9"/>
  <!-- Keyhole stem -->
  <rect x="246" y="326" width="20" height="44" rx="10" fill="{_BG}" opacity="0.9"/>
"""
    return _svg_wrap(defs, body)


def _icon_password() -> str:
    defs = (
        svg_linear_gradient("passGrad", [("0%", _IND), ("100%", _PRI)],
                             x1="0%", y1="0%", x2="100%", y2="0%") +
        svg_radial_gradient("dotGlow", [("0%", _CYA), ("100%", _CYA + "00")]) +
        svg_drop_shadow_filter("passShadow", dy=4, stddev=8, opacity=0.4)
    )
    body = f"""
  <!-- Card body -->
  <rect x="60" y="148" width="392" height="216" rx="36"
        fill="{_SURF}" stroke="url(#passGrad)" stroke-width="20"
        filter="url(#passShadow)"/>
  <!-- Gloss line -->
  <rect x="60" y="148" width="392" height="72" rx="36"
        fill="white" opacity="0.04"/>
  <!-- Key icon left -->
  <circle cx="148" cy="260" r="36" fill="none" stroke="url(#passGrad)"
          stroke-width="16"/>
  <line x1="184" y1="260" x2="240" y2="260" stroke="url(#passGrad)"
        stroke-width="16" stroke-linecap="round"/>
  <line x1="232" y1="260" x2="232" y2="288" stroke="url(#passGrad)"
        stroke-width="14" stroke-linecap="round"/>
  <line x1="210" y1="260" x2="210" y2="280" stroke="url(#passGrad)"
        stroke-width="14" stroke-linecap="round"/>
  <!-- Dot indicators -->
  <circle cx="320" cy="260" r="14" fill="url(#dotGlow)"/>
  <circle cx="364" cy="260" r="14" fill="url(#dotGlow)"/>
  <circle cx="408" cy="260" r="14" fill="url(#dotGlow)" opacity="0.4"/>
"""
    return _svg_wrap(defs, body)


def _icon_settings() -> str:
    defs = (
        svg_linear_gradient("gearGrad", [("0%", _IND), ("100%", _CYA)],
                             x1="0%", y1="0%", x2="100%", y2="100%") +
        svg_radial_gradient("innerGlow", [("0%", _CYA + "aa"), ("100%", _CYA + "00")]) +
        svg_drop_shadow_filter("gearShadow", dy=4, stddev=10, opacity=0.5)
    )
    # 8-tooth gear: generate tooth path mathematically
    import math
    R_outer = 180  # tooth tip radius
    R_inner = 140  # tooth base radius
    R_bore  = 52   # center bore
    teeth   = 8
    pts = []
    for i in range(teeth):
        base_angle = (2 * math.pi / teeth) * i
        half_tooth = math.pi / teeth * 0.42
        for angle, r in [
            (base_angle - half_tooth * 1.4, R_inner),
            (base_angle - half_tooth,       R_outer),
            (base_angle + half_tooth,       R_outer),
            (base_angle + half_tooth * 1.4, R_inner),
        ]:
            x = 256 + r * math.cos(angle)
            y = 256 + r * math.sin(angle)
            pts.append(f"{x:.1f},{y:.1f}")
    gear_path = "M " + " L ".join(pts) + " Z"
    body = f"""
  <!-- Gear body -->
  <path d="{gear_path}"
        fill="url(#gearGrad)" filter="url(#gearShadow)"/>
  <!-- Center bore -->
  <circle cx="256" cy="256" r="{R_bore}" fill="{_BG}"/>
  <!-- Inner ring accent -->
  <circle cx="256" cy="256" r="36" fill="url(#innerGlow)" opacity="0.9"/>
  <circle cx="256" cy="256" r="22" fill="{_CYA}" opacity="0.8"/>
"""
    return _svg_wrap(defs, body)


def _icon_package_manager() -> str:
    defs = (
        svg_linear_gradient("boxTop",   [("0%", _CYA),  ("100%", _IND)],
                             x1="0%", y1="0%", x2="100%", y2="0%") +
        svg_linear_gradient("boxFront", [("0%", _IND),  ("100%", _VIO)],
                             x1="0%", y1="0%", x2="0%",   y2="100%") +
        svg_linear_gradient("boxSide",  [("0%", _VIO),  ("100%", _IND + "88")],
                             x1="0%", y1="0%", x2="100%", y2="0%") +
        svg_drop_shadow_filter("boxShadow", dy=8, stddev=12, opacity=0.5)
    )
    body = """
  <!-- Isometric box — front face -->
  <polygon points="256,290 100,200 100,380 256,470"
           fill="url(#boxFront)" filter="url(#boxShadow)"/>
  <!-- Right/side face -->
  <polygon points="256,290 412,200 412,380 256,470"
           fill="url(#boxSide)"/>
  <!-- Top face -->
  <polygon points="256,120 412,200 256,290 100,200"
           fill="url(#boxTop)"/>
  <!-- Top edge ribbon -->
  <line x1="256" y1="120" x2="256" y2="290"
        stroke="white" stroke-width="6" opacity="0.2"/>
  <!-- Center crease lines -->
  <line x1="100" y1="200" x2="412" y2="200"
        stroke="white" stroke-width="4" opacity="0.15"/>
"""
    return _svg_wrap(defs, body)


def _icon_update() -> str:
    defs = (
        svg_linear_gradient("arrGrad1", [("0%", _CYA),  ("100%", _IND)],
                             x1="0%", y1="0%", x2="100%", y2="100%") +
        svg_linear_gradient("arrGrad2", [("0%", _IND),  ("100%", _VIO)],
                             x1="100%", y1="0%", x2="0%", y2="100%") +
        svg_glow_filter("arrGlow", _CYA, stddev=8)
    )
    body = """
  <!-- Outer clockwise arc -->
  <path d="M140,256 A116,116 0 1 1 372,372"
        stroke="url(#arrGrad1)" stroke-width="32" stroke-linecap="round"
        fill="none" filter="url(#arrGlow)"/>
  <!-- Outer arrowhead -->
  <polygon points="372,372 316,308 428,308" fill="url(#arrGrad1)"/>
  <!-- Inner counter-clockwise arc -->
  <path d="M372,256 A116,116 0 1 1 140,140"
        stroke="url(#arrGrad2)" stroke-width="24" stroke-linecap="round"
        fill="none"/>
  <!-- Inner arrowhead -->
  <polygon points="140,140 196,204 84,204" fill="url(#arrGrad2)"/>
"""
    return _svg_wrap(defs, body)


def _icon_security() -> str:
    defs = (
        svg_linear_gradient("shieldGrad", [("0%", _IND), ("100%", _VIO)],
                             x1="20%", y1="0%", x2="80%", y2="100%") +
        svg_linear_gradient("checkGrad",  [("0%", _CYA), ("100%", _IND)],
                             x1="0%", y1="0%", x2="100%", y2="0%") +
        svg_radial_gradient("shieldGlow", [("0%", _IND + "55"), ("100%", _IND + "00")]) +
        svg_drop_shadow_filter("shieldShadow", dy=6, stddev=12, opacity=0.5) +
        svg_glow_filter("checkGlow", _CYA, stddev=8)
    )
    body = """
  <!-- Shield body -->
  <path d="M256,52 L400,104 L400,268
           C400,362 334,432 256,472
           C178,432 112,362 112,268 L112,104 Z"
        fill="url(#shieldGrad)" filter="url(#shieldShadow)"/>
  <!-- Shield inner highlight -->
  <path d="M256,80 L380,124 L380,268
           C380,350 322,412 256,448
           C190,412 132,350 132,268 L132,124 Z"
        fill="url(#shieldGlow)" opacity="0.4"/>
  <!-- Checkmark -->
  <path d="M176,248 L228,300 L336,192"
        stroke="url(#checkGrad)" stroke-width="28"
        stroke-linecap="round" stroke-linejoin="round"
        fill="none" filter="url(#checkGlow)"/>
"""
    return _svg_wrap(defs, body)


def _icon_ai() -> str:
    defs = (
        svg_linear_gradient("aiGrad",  [("0%", _IND),  ("100%", _CYA)],
                             x1="0%", y1="0%", x2="100%", y2="100%") +
        svg_radial_gradient("aiCore",  [("0%", _CYA),  ("100%", _IND)]) +
        svg_radial_gradient("nodeGlow",[("0%", _CYA + "ff"), ("100%", _CYA + "00")]) +
        svg_glow_filter("aiGlow", _CYA, stddev=12)
    )
    # Hexagonal neural net: center + 6 outer nodes
    import math
    cx, cy = 256, 256
    r_out = 148
    nodes = [(cx, cy)]  # center
    for i in range(6):
        a = math.pi / 6 + i * math.pi / 3
        nodes.append((cx + r_out * math.cos(a), cy + r_out * math.sin(a)))
    # Connections from center to each outer + ring connections
    connections = [(0, i) for i in range(1, 7)] + [(i, i % 6 + 1) for i in range(1, 7)]
    conn_paths = "".join(
        f'  <line x1="{nodes[a][0]:.1f}" y1="{nodes[a][1]:.1f}" '
        f'x2="{nodes[b][0]:.1f}" y2="{nodes[b][1]:.1f}" '
        f'stroke="url(#aiGrad)" stroke-width="10" opacity="0.5"/>\n'
        for a, b in connections
    )
    node_circles = "".join(
        f'  <circle cx="{x:.1f}" cy="{y:.1f}" r="{20 if i==0 else 14}" '
        f'fill="url(#nodeGlow)" filter="url(#aiGlow)"/>\n'
        for i, (x, y) in enumerate(nodes)
    )
    body = conn_paths + node_circles
    return _svg_wrap(defs, body)


def _icon_marketplace() -> str:
    defs = (
        svg_linear_gradient("bagGrad",    [("0%", _IND), ("100%", _VIO)],
                             x1="0%", y1="0%", x2="0%", y2="100%") +
        svg_linear_gradient("handleGrad", [("0%", _CYA), ("100%", _IND)],
                             x1="0%", y1="0%", x2="100%", y2="0%") +
        svg_drop_shadow_filter("bagShadow", dy=6, stddev=10, opacity=0.5) +
        svg_glow_filter("bagGlow", _IND, stddev=8)
    )
    body = f"""
  <!-- Bag body with trapezoid shape -->
  <path d="M80,168 L432,168 L388,436 L124,436 Z"
        fill="url(#bagGrad)" filter="url(#bagShadow)"/>
  <!-- Gloss overlay -->
  <path d="M80,168 L432,168 L420,232 L92,232 Z"
        fill="white" opacity="0.06"/>
  <!-- Handle arcs -->
  <path d="M168,168 v-44 a88,88 0 0 1 176,0 v44"
        stroke="url(#handleGrad)" stroke-width="24"
        stroke-linecap="round" fill="none" filter="url(#bagGlow)"/>
  <!-- Center tag label -->
  <rect x="208" y="280" width="96" height="56" rx="12" fill="{_BG}" opacity="0.5"/>
  <line x1="256" y1="280" x2="256" y2="224" stroke="{_CYA}"
        stroke-width="6" stroke-dasharray="4,4" opacity="0.5"/>
"""
    return _svg_wrap(defs, body)


def _icon_store() -> str:
    defs = (
        svg_linear_gradient("storeGrad", [("0%", _CYA), ("100%", _IND)],
                             x1="0%", y1="0%", x2="100%", y2="100%") +
        svg_linear_gradient("roofGrad",  [("0%", _IND), ("100%", _VIO)],
                             x1="0%", y1="0%", x2="100%", y2="0%") +
        svg_drop_shadow_filter("storeShadow", dy=6, stddev=10, opacity=0.5)
    )
    body = f"""
  <!-- Building body -->
  <rect x="76" y="200" width="360" height="280" rx="12"
        fill="url(#storeGrad)" filter="url(#storeShadow)"/>
  <!-- Roof / awning -->
  <polygon points="52,200 256,80 460,200"
           fill="url(#roofGrad)"/>
  <!-- Windows -->
  <rect x="116" y="252" width="100" height="80" rx="8"
        fill="{_BG}" opacity="0.6"/>
  <rect x="296" y="252" width="100" height="80" rx="8"
        fill="{_BG}" opacity="0.6"/>
  <!-- Door -->
  <rect x="200" y="360" width="112" height="120" rx="10"
        fill="{_BG}" opacity="0.6"/>
  <!-- Awning stripe -->
  <rect x="52" y="188" width="408" height="20" rx="6"
        fill="{_CYA}" opacity="0.4"/>
"""
    return _svg_wrap(defs, body)


def _icon_browser() -> str:
    defs = (
        svg_linear_gradient("globeGrad",  [("0%", _IND),  ("100%", _CYA)],
                             x1="0%", y1="0%", x2="100%", y2="100%") +
        svg_linear_gradient("barGrad",    [("0%", _CYA),  ("100%", _IND)],
                             x1="0%", y1="0%", x2="100%", y2="0%") +
        svg_radial_gradient("globeShine", [("0%", "white"), ("100%", "transparent")]) +
        svg_drop_shadow_filter("globeShadow", dy=4, stddev=8, opacity=0.4)
    )
    body = f"""
  <!-- Address bar background -->
  <rect x="52" y="52" width="408" height="56" rx="16"
        fill="{_SURF}" stroke="url(#barGrad)" stroke-width="4"/>
  <!-- Traffic lights -->
  <circle cx="92"  cy="80" r="10" fill="#EF4444"/>
  <circle cx="120" cy="80" r="10" fill="#F59E0B"/>
  <circle cx="148" cy="80" r="10" fill="#10B981"/>
  <!-- URL bar fill -->
  <rect x="176" y="64" width="248" height="28" rx="8"
        fill="{_BG}" opacity="0.8"/>
  <!-- Globe outer ring -->
  <circle cx="256" cy="316" r="168" fill="none"
          stroke="url(#globeGrad)" stroke-width="24"
          filter="url(#globeShadow)"/>
  <!-- Meridian ellipse -->
  <ellipse cx="256" cy="316" rx="76" ry="168" fill="none"
           stroke="url(#globeGrad)" stroke-width="14"/>
  <!-- Equator line -->
  <line x1="88" y1="316" x2="424" y2="316"
        stroke="url(#globeGrad)" stroke-width="14"/>
  <!-- Tropic arcs -->
  <path d="M112,248 Q256,220 400,248" stroke="url(#globeGrad)"
        stroke-width="10" fill="none" opacity="0.5"/>
  <path d="M112,384 Q256,412 400,384" stroke="url(#globeGrad)"
        stroke-width="10" fill="none" opacity="0.5"/>
  <!-- Shine highlight -->
  <ellipse cx="220" cy="280" rx="36" ry="24"
           fill="url(#globeShine)" opacity="0.12" transform="rotate(-20,220,280)"/>
"""
    return _svg_wrap(defs, body)


def _icon_files() -> str:
    defs = (
        svg_linear_gradient("docGrad1",   [("0%", _IND),  ("100%", _VIO)],
                             x1="0%", y1="0%", x2="0%", y2="100%") +
        svg_linear_gradient("docGrad2",   [("0%", _PRI),  ("100%", _IND)],
                             x1="0%", y1="0%", x2="0%", y2="100%") +
        svg_linear_gradient("cornerGrad", [("0%", _CYA),  ("100%", _IND)],
                             x1="0%", y1="0%", x2="100%", y2="100%") +
        svg_drop_shadow_filter("docShadow", dy=6, stddev=10, opacity=0.5)
    )
    body = f"""
  <!-- Back document (shadow) -->
  <path d="M148,80 h172 l88,88 v280 h-260 Z"
        fill="url(#docGrad2)" opacity="0.5" transform="translate(16,-8)"/>
  <!-- Main document -->
  <path d="M116,96 h188 l96,96 v280 h-284 Z"
        fill="url(#docGrad1)" filter="url(#docShadow)"/>
  <!-- Folded corner -->
  <path d="M304,96 v96 h96 Z" fill="url(#cornerGrad)"/>
  <!-- Fold crease line -->
  <line x1="304" y1="96" x2="304" y2="192"
        stroke="white" stroke-width="4" opacity="0.2"/>
  <!-- Content lines -->
  <line x1="164" y1="264" x2="348" y2="264"
        stroke="white" stroke-width="12" stroke-linecap="round" opacity="0.25"/>
  <line x1="164" y1="308" x2="316" y2="308"
        stroke="white" stroke-width="12" stroke-linecap="round" opacity="0.18"/>
  <line x1="164" y1="352" x2="332" y2="352"
        stroke="white" stroke-width="12" stroke-linecap="round" opacity="0.18"/>
  <line x1="164" y1="396" x2="280" y2="396"
        stroke="white" stroke-width="12" stroke-linecap="round" opacity="0.12"/>
"""
    return _svg_wrap(defs, body)


# ---------------------------------------------------------------------------
# Registry: name → generator function
# ---------------------------------------------------------------------------

SVG_GENERATORS = {
    "pyflare":         _icon_pyflare,
    "power":           _icon_power,
    "lock":            _icon_lock,
    "password":        _icon_password,
    "settings":        _icon_settings,
    "package_manager": _icon_package_manager,
    "update":          _icon_update,
    "security":        _icon_security,
    "ai":              _icon_ai,
    "marketplace":     _icon_marketplace,
    "store":           _icon_store,
    "browser":         _icon_browser,
    "files":           _icon_files,
}

# Dominant colour per icon (used in PIL fallback gradient)
ICON_DOMINANT_COLOR = {
    "pyflare":         (91,  95,  255),
    "power":           (0,   212, 255),
    "lock":            (91,  95,  255),
    "password":        (59,  130, 246),
    "settings":        (0,   212, 255),
    "package_manager": (138, 92,  245),
    "update":          (0,   212, 255),
    "security":        (91,  95,  255),
    "ai":              (0,   212, 255),
    "marketplace":     (91,  95,  255),
    "store":           (0,   212, 255),
    "browser":         (91,  95,  255),
    "files":           (138, 92,  245),
}


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------

def _export_svg_to_png_cairosvg(svg_path: str, out_path: str, size: int) -> bool:
    """Export SVG → PNG using cairosvg. Returns True on success."""
    try:
        import cairosvg
        cairosvg.svg2png(
            url=svg_path,
            write_to=out_path,
            output_width=size,      # correct parameter name
            output_height=size,
        )
        return True
    except ImportError:
        return False
    except Exception as e:
        logger.warning(f"cairosvg failed for {svg_path} @ {size}px: {e}")
        return False


def _export_svg_to_png_pil_fallback(name: str, out_path: str, size: int):
    """
    High-quality PIL fallback: renders a gradient circle in the icon's
    dominant colour instead of a plain solid fill.
    """
    from PIL import Image, ImageFilter
    from branding_generator.utils import build_radial_gradient_pixels, rgb_lerp, apply_glow

    dominant = ICON_DOMINANT_COLOR.get(name, (91, 95, 255))
    dark_bg   = (11, 15, 25)

    # Background
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    # Radial gradient disc
    grad = build_radial_gradient_pixels(size, size, dominant, dark_bg)
    # Mask to a circle
    from PIL import ImageDraw
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse(
        [size // 8, size // 8, size * 7 // 8, size * 7 // 8], fill=255
    )
    grad.putalpha(mask)
    img = Image.alpha_composite(img, grad)

    # Subtle glow
    img = apply_glow(img, dominant, radius=size // 6, intensity=0.4)
    img.save(out_path, "PNG")


def export_svg_to_png(svg_path: str, out_path: str, size: int, icon_name: str = ""):
    """Try cairosvg first, fall back to PIL gradient if unavailable."""
    if not _export_svg_to_png_cairosvg(svg_path, out_path, size):
        _export_svg_to_png_pil_fallback(icon_name, out_path, size)


# ---------------------------------------------------------------------------
# Main generation entry point
# ---------------------------------------------------------------------------

def generate_all_icons(
    target_root: str,
    cache: "BuildCache | None" = None,
    incremental: bool = False,
) -> None:
    svg_dir = ensure_dir(os.path.join(target_root, "logos", "svg"))
    png_dir = ensure_dir(os.path.join(target_root, "logos", "png"))

    total = len(SVG_GENERATORS) * (1 + len(ICON_SIZES))
    with ProgressReporter(total, desc="Icons") as prog:
        for name, gen_fn in SVG_GENERATORS.items():
            # 1. Generate SVG content
            svg_content = gen_fn()
            svg_path    = os.path.join(svg_dir, f"{name}.svg")

            # Incremental build check
            src_hash = content_sha256(svg_content.encode())
            if (
                incremental
                and cache
                and os.path.exists(svg_path)
                and cache.is_fresh(svg_path, src_hash)
            ):
                prog.advance(1 + len(ICON_SIZES), postfix=f"{name} (cached)")
                continue

            with open(svg_path, "w", encoding="utf-8") as f:
                f.write(svg_content)
            if cache:
                cache.mark(svg_path, src_hash)
            prog.advance(1, postfix=f"SVG {name}")

            # 2. Export multi-size PNGs
            for size in ICON_SIZES:
                size_dir = ensure_dir(os.path.join(png_dir, f"{size}x{size}"))
                out_png  = os.path.join(size_dir, f"{name}.png")
                export_svg_to_png(svg_path, out_png, size, icon_name=name)
                prog.advance(1, postfix=f"PNG {name}@{size}")

    logger.info(
        f"Icons: generated {len(SVG_GENERATORS)} SVGs "
        f"× {len(ICON_SIZES)} sizes = "
        f"{len(SVG_GENERATORS) * len(ICON_SIZES)} PNG exports"
    )
