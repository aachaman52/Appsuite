# PyFlare Branding Generator — Central Configuration
# All colour constants, token definitions, and pipeline parameters live here.
# Other modules import from this file; do not duplicate values elsewhere.

VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Core brand palette (hex strings)
# ---------------------------------------------------------------------------
BRAND_COLORS = {
    "primary":    "#3B82F6",   # Electric blue
    "cyan":       "#00D4FF",   # Vibrant cyan
    "indigo":     "#5B5FFF",   # Electric indigo
    "violet":     "#8A5CF5",   # Deep violet
    "magenta":    "#EC4899",   # Accent magenta
    "background": "#0B0F19",   # Matte dark navy
    "surface":    "#111827",   # Card surface
    "border":     "#1F2937",   # Subtle border
    "white":      "#FFFFFF",
    "black":      "#000000",
}

# RGB tuples for PIL (no alpha)
BRAND_COLORS_RGB = {
    "primary":    (59,  130, 246),
    "cyan":       (0,   212, 255),
    "indigo":     (91,  95,  255),
    "violet":     (138, 92,  245),
    "magenta":    (236, 72,  153),
    "background": (11,  15,  25),
    "surface":    (17,  24,  39),
    "border":     (31,  41,  55),
    "white":      (255, 255, 255),
    "black":      (0,   0,   0),
}

# ---------------------------------------------------------------------------
# Typography
# ---------------------------------------------------------------------------
TYPOGRAPHY = {
    "primary":   "Inter",
    "headings":  "Space Grotesk",
    "monospace": "JetBrains Mono",
}

FONT_SOURCES = {
    "Inter": {
        "url": "https://github.com/rsms/inter/releases/download/v4.0/Inter-4.0.zip",
        "license": "SIL Open Font License 1.1",
        "files": ["Inter-Regular.ttf", "Inter-Medium.ttf", "Inter-SemiBold.ttf", "Inter-Bold.ttf"],
    },
    "Space Grotesk": {
        "url": "https://fonts.google.com/download?family=Space+Grotesk",
        "license": "SIL Open Font License 1.1",
        "files": ["SpaceGrotesk-Regular.ttf", "SpaceGrotesk-Medium.ttf", "SpaceGrotesk-Bold.ttf"],
    },
    "JetBrains Mono": {
        "url": "https://github.com/JetBrains/JetBrainsMono/releases/download/v2.304/JetBrainsMono-2.304.zip",
        "license": "SIL Open Font License 1.1",
        "files": ["JetBrainsMono-Regular.ttf", "JetBrainsMono-Medium.ttf", "JetBrainsMono-Bold.ttf"],
    },
}

# ---------------------------------------------------------------------------
# Icon export sizes (px)
# ---------------------------------------------------------------------------
ICON_SIZES = [16, 24, 32, 48, 64, 96, 128, 256, 512, 1024]

# ---------------------------------------------------------------------------
# Gradient definitions  (for SVG <linearGradient> / CSS / JSON)
# ---------------------------------------------------------------------------
GRADIENT_DEFINITIONS = {
    "primary_gradient": {
        "type": "linear",
        "angle": 135,
        "stops": [
            {"offset": "0%",   "color": "#5B5FFF"},
            {"offset": "50%",  "color": "#3B82F6"},
            {"offset": "100%", "color": "#00D4FF"},
        ],
    },
    "violet_gradient": {
        "type": "linear",
        "angle": 135,
        "stops": [
            {"offset": "0%",   "color": "#8A5CF5"},
            {"offset": "100%", "color": "#5B5FFF"},
        ],
    },
    "warm_gradient": {
        "type": "linear",
        "angle": 90,
        "stops": [
            {"offset": "0%",   "color": "#EC4899"},
            {"offset": "100%", "color": "#8A5CF5"},
        ],
    },
    "surface_glow": {
        "type": "radial",
        "stops": [
            {"offset": "0%",   "color": "#1F2937"},
            {"offset": "100%", "color": "#0B0F19"},
        ],
    },
}

# ---------------------------------------------------------------------------
# Full design-token theme schemes
# ---------------------------------------------------------------------------
THEME_SCHEMES = {
    "dark": {
        "name":              "PyFlare Dark",
        "variant":           "dark",
        # Surfaces
        "background":        "#0B0F19",
        "surface":           "#111827",
        "surface_variant":   "#1F2937",
        "overlay":           "#374151",
        # Primary
        "primary":           "#3B82F6",
        "primary_container": "#1D4ED8",
        "on_primary":        "#FFFFFF",
        # Accent
        "accent":            "#00D4FF",
        "accent_dim":        "#0891B2",
        # Text
        "text":              "#F9FAFB",
        "text_secondary":    "#9CA3AF",
        "text_disabled":     "#4B5563",
        # Semantic
        "error":             "#EF4444",
        "error_container":   "#7F1D1D",
        "warning":           "#F59E0B",
        "warning_container": "#78350F",
        "success":           "#10B981",
        "success_container": "#064E3B",
        "info":              "#3B82F6",
        # Interactive states
        "hover":             "#1F2937",
        "pressed":           "#374151",
        "focus_ring":        "#5B5FFF",
        "selected":          "#1E3A5F",
        "disabled_bg":       "#111827",
        "disabled_fg":       "#4B5563",
        # Border
        "border":            "#1F2937",
        "border_strong":     "#374151",
        # Typography
        "font_family":       "Inter, system-ui, sans-serif",
        "font_heading":      "Space Grotesk, Inter, sans-serif",
        "font_mono":         "JetBrains Mono, monospace",
        "font_size_xs":      "11px",
        "font_size_sm":      "13px",
        "font_size_base":    "15px",
        "font_size_lg":      "18px",
        "font_size_xl":      "24px",
        "font_size_2xl":     "32px",
        "font_weight_normal": "400",
        "font_weight_medium": "500",
        "font_weight_bold":   "700",
        # Spacing (4px base grid)
        "spacing_1":   "4px",
        "spacing_2":   "8px",
        "spacing_3":   "12px",
        "spacing_4":   "16px",
        "spacing_6":   "24px",
        "spacing_8":   "32px",
        "spacing_12":  "48px",
        # Radius
        "radius_sm":   "4px",
        "radius_md":   "8px",
        "radius_lg":   "12px",
        "radius_xl":   "16px",
        "radius_full": "9999px",
        # Elevation / shadows
        "shadow_sm":   "0 1px 3px rgba(0,0,0,0.5)",
        "shadow_md":   "0 4px 16px rgba(0,0,0,0.6)",
        "shadow_lg":   "0 8px 32px rgba(0,0,0,0.7)",
        "shadow_glow": "0 0 24px rgba(91,95,255,0.4)",
        # Opacity
        "opacity_disabled": "0.38",
        "opacity_overlay":  "0.6",
        "opacity_backdrop": "0.8",
        # Animation / transitions
        "transition_fast":   "100ms ease",
        "transition_base":   "200ms ease",
        "transition_slow":   "350ms ease",
        "anim_duration_short": "200ms",
        "anim_duration_base":  "400ms",
        "anim_duration_long":  "800ms",
        "anim_easing":         "cubic-bezier(0.4, 0, 0.2, 1)",
        # Icon sizes
        "icon_xs":  "12px",
        "icon_sm":  "16px",
        "icon_md":  "24px",
        "icon_lg":  "32px",
        "icon_xl":  "48px",
        "icon_2xl": "64px",
    },
    "light": {
        "name":              "PyFlare Light",
        "variant":           "light",
        "background":        "#F9FAFB",
        "surface":           "#FFFFFF",
        "surface_variant":   "#F3F4F6",
        "overlay":           "#E5E7EB",
        "primary":           "#2563EB",
        "primary_container": "#DBEAFE",
        "on_primary":        "#FFFFFF",
        "accent":            "#0891B2",
        "accent_dim":        "#0E7490",
        "text":              "#111827",
        "text_secondary":    "#6B7280",
        "text_disabled":     "#9CA3AF",
        "error":             "#DC2626",
        "error_container":   "#FEE2E2",
        "warning":           "#D97706",
        "warning_container": "#FEF3C7",
        "success":           "#059669",
        "success_container": "#D1FAE5",
        "info":              "#2563EB",
        "hover":             "#F3F4F6",
        "pressed":           "#E5E7EB",
        "focus_ring":        "#3B82F6",
        "selected":          "#DBEAFE",
        "disabled_bg":       "#F9FAFB",
        "disabled_fg":       "#9CA3AF",
        "border":            "#E5E7EB",
        "border_strong":     "#D1D5DB",
        "font_family":       "Inter, system-ui, sans-serif",
        "font_heading":      "Space Grotesk, Inter, sans-serif",
        "font_mono":         "JetBrains Mono, monospace",
        "font_size_xs":      "11px",
        "font_size_sm":      "13px",
        "font_size_base":    "15px",
        "font_size_lg":      "18px",
        "font_size_xl":      "24px",
        "font_size_2xl":     "32px",
        "font_weight_normal": "400",
        "font_weight_medium": "500",
        "font_weight_bold":   "700",
        "spacing_1":   "4px",
        "spacing_2":   "8px",
        "spacing_3":   "12px",
        "spacing_4":   "16px",
        "spacing_6":   "24px",
        "spacing_8":   "32px",
        "spacing_12":  "48px",
        "radius_sm":   "4px",
        "radius_md":   "8px",
        "radius_lg":   "12px",
        "radius_xl":   "16px",
        "radius_full": "9999px",
        "shadow_sm":   "0 1px 3px rgba(0,0,0,0.1)",
        "shadow_md":   "0 4px 16px rgba(0,0,0,0.15)",
        "shadow_lg":   "0 8px 32px rgba(0,0,0,0.2)",
        "shadow_glow": "0 0 20px rgba(59,130,246,0.3)",
        "opacity_disabled": "0.38",
        "opacity_overlay":  "0.4",
        "opacity_backdrop": "0.6",
        "transition_fast":   "100ms ease",
        "transition_base":   "200ms ease",
        "transition_slow":   "350ms ease",
        "anim_duration_short": "200ms",
        "anim_duration_base":  "400ms",
        "anim_duration_long":  "800ms",
        "anim_easing":         "cubic-bezier(0.4, 0, 0.2, 1)",
        "icon_xs":  "12px",
        "icon_sm":  "16px",
        "icon_md":  "24px",
        "icon_lg":  "32px",
        "icon_xl":  "48px",
        "icon_2xl": "64px",
    },
    "midnight": {
        "name":              "PyFlare Midnight",
        "variant":           "dark",
        "background":        "#020617",
        "surface":           "#0F172A",
        "surface_variant":   "#1E293B",
        "overlay":           "#334155",
        "primary":           "#5B5FFF",
        "primary_container": "#312E81",
        "on_primary":        "#FFFFFF",
        "accent":            "#8A5CF5",
        "accent_dim":        "#6D28D9",
        "text":              "#F8FAFC",
        "text_secondary":    "#94A3B8",
        "text_disabled":     "#64748B",
        "error":             "#F43F5E",
        "error_container":   "#881337",
        "warning":           "#FB923C",
        "warning_container": "#7C2D12",
        "success":           "#34D399",
        "success_container": "#064E3B",
        "info":              "#60A5FA",
        "hover":             "#1E293B",
        "pressed":           "#334155",
        "focus_ring":        "#8A5CF5",
        "selected":          "#1E1B4B",
        "disabled_bg":       "#0F172A",
        "disabled_fg":       "#64748B",
        "border":            "#1E293B",
        "border_strong":     "#334155",
        "font_family":       "Inter, system-ui, sans-serif",
        "font_heading":      "Space Grotesk, Inter, sans-serif",
        "font_mono":         "JetBrains Mono, monospace",
        "font_size_xs":      "11px",
        "font_size_sm":      "13px",
        "font_size_base":    "15px",
        "font_size_lg":      "18px",
        "font_size_xl":      "24px",
        "font_size_2xl":     "32px",
        "font_weight_normal": "400",
        "font_weight_medium": "500",
        "font_weight_bold":   "700",
        "spacing_1":   "4px",
        "spacing_2":   "8px",
        "spacing_3":   "12px",
        "spacing_4":   "16px",
        "spacing_6":   "24px",
        "spacing_8":   "32px",
        "spacing_12":  "48px",
        "radius_sm":   "6px",
        "radius_md":   "12px",
        "radius_lg":   "16px",
        "radius_xl":   "24px",
        "radius_full": "9999px",
        "shadow_sm":   "0 1px 4px rgba(0,0,0,0.7)",
        "shadow_md":   "0 4px 20px rgba(0,0,0,0.8)",
        "shadow_lg":   "0 12px 40px rgba(0,0,0,0.9)",
        "shadow_glow": "0 0 32px rgba(138,92,245,0.5)",
        "opacity_disabled": "0.38",
        "opacity_overlay":  "0.7",
        "opacity_backdrop": "0.9",
        "transition_fast":   "80ms ease",
        "transition_base":   "180ms ease",
        "transition_slow":   "320ms ease",
        "anim_duration_short": "180ms",
        "anim_duration_base":  "360ms",
        "anim_duration_long":  "720ms",
        "anim_easing":         "cubic-bezier(0.4, 0, 0.2, 1)",
        "icon_xs":  "12px",
        "icon_sm":  "16px",
        "icon_md":  "24px",
        "icon_lg":  "32px",
        "icon_xl":  "48px",
        "icon_2xl": "64px",
    },
}

# ---------------------------------------------------------------------------
# Cursor definitions — name → (hotspot_x, hotspot_y)
# All cursor images rendered at 48×48; hotspot in that coordinate space.
# ---------------------------------------------------------------------------
CURSOR_DEFINITIONS = {
    "default":            (4,   4),
    "pointer":            (4,   4),
    "hand":               (16,  2),
    "text":               (12, 12),
    "busy":               (24, 24),
    "working":            (4,   4),
    "move":               (24, 24),
    "crosshair":          (24, 24),
    "forbidden":          (24, 24),
    "resize_horizontal":  (24, 12),
    "resize_vertical":    (12, 24),
    "resize_diagonal_nw": (24, 24),
    "resize_diagonal_ne": (24, 24),
    "precision_select":   (24, 24),
}

# Linux XCursor size sequence (pixels)
XCURSOR_SIZES = [24, 32, 48, 64, 96]

# ---------------------------------------------------------------------------
# Animation configuration
# ---------------------------------------------------------------------------
ANIMATION_CONFIGS = {
    "boot": {
        "frame_count": 30,
        "fps": 30,
        "duration_ms": 1000,
        "easing": "ease_in_out_cubic",
        "size": 256,
        "loop": False,
    },
    "shutdown": {
        "frame_count": 30,
        "fps": 30,
        "duration_ms": 1000,
        "easing": "ease_in_expo",
        "size": 256,
        "loop": False,
    },
    "loading": {
        "frame_count": 24,
        "fps": 24,
        "duration_ms": 1000,
        "easing": "linear",
        "size": 256,
        "loop": True,
    },
    "success": {
        "frame_count": 20,
        "fps": 30,
        "duration_ms": 667,
        "easing": "ease_out_elastic",
        "size": 256,
        "loop": False,
    },
    "error": {
        "frame_count": 18,
        "fps": 30,
        "duration_ms": 600,
        "easing": "ease_in_out_cubic",
        "size": 256,
        "loop": False,
    },
}

# ---------------------------------------------------------------------------
# Wallpaper types and target resolutions
# ---------------------------------------------------------------------------
WALLPAPER_TYPES = [
    "default_dark",
    "aurora",
    "abstract_blue",
    "minimal_dark",
    "nebula",
    "circuit",
    "geometric",
    "deep_space",
]

WALLPAPER_RESOLUTIONS = [
    (3840, 2160, "4K"),
    (2560, 1440, "QHD"),
    (1920, 1080, "FHD"),
]
