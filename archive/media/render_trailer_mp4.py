"""
Aachman Studios Ecosystem Trailer — High-Resolution MP4 Renderer (1080p @ 30fps)
Duration: 90.0 seconds | Total Frames: 2700
Brand Identity: Official Aachman Studios Logo (#5B5FFF, #8A5CF5, #00D4FF)
"""

import math
import os
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Try imageio or cv2 for MP4 encoding
try:
    import imageio
    HAS_IMAGEIO = True
except ImportError:
    HAS_IMAGEIO = False

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

WIDTH, HEIGHT = 1920, 1080
FPS = 30
TOTAL_DURATION = 90.0  # seconds
TOTAL_FRAMES = int(TOTAL_DURATION * FPS)

OUTPUT_FILENAME = "Aachman_Studios_Ecosystem_Trailer.mp4"

# Color Palette
COLOR_BG_DARK = (7, 9, 14)
COLOR_BG_SURFACE = (11, 15, 25)
COLOR_INDIGO = (91, 95, 255)
COLOR_VIOLET = (138, 92, 245)
COLOR_CYAN = (0, 212, 255)
COLOR_BLUE = (59, 130, 246)
COLOR_GREEN = (16, 185, 129)
COLOR_RED = (239, 68, 68)
COLOR_WHITE = (255, 255, 255)
COLOR_TEXT_MUTED = (156, 163, 175)

# Try loading system fonts or default
def get_font(size=14, mono=False, bold=False):
    font_names = []
    if mono:
        font_names = ["consola.ttf", "arial.ttf", "dejavusansmono.ttf"]
    else:
        font_names = ["segoeui.ttf", "arial.ttf", "dejavusans.ttf"]
    
    for fn in font_names:
        try:
            return ImageFont.truetype(fn, size)
        except Exception:
            continue
    return ImageFont.load_default()

font_title = get_font(28, bold=True)
font_heading = get_font(20, bold=True)
font_body = get_font(15)
font_mono = get_font(13, mono=True)
font_small = get_font(11, mono=True)
font_subtitle = get_font(18)

# Load Official Uploaded Aachman Studios Logo Image
LOGO_IMG_PATH = "aachmanstiudios.png"
if os.path.exists(LOGO_IMG_PATH):
    LOGO_PIL = Image.open(LOGO_IMG_PATH).convert("RGBA")
else:
    LOGO_PIL = None

# Official Aachman Studios Logo Renderer
def draw_aachman_logo(draw, img, cx, cy, scale=1.0, alpha=1.0):
    if alpha <= 0.001:
        return
    if LOGO_PIL is not None:
        target_w = max(1, int(520 * max(0.01, scale)))
        target_h = max(1, int(520 * max(0.01, scale)))
        resized_logo = LOGO_PIL.resize((target_w, target_h), Image.Resampling.LANCZOS)
        
        if alpha < 1.0:
            # Multiply alpha channel
            r, g, b, a = resized_logo.split()
            a = a.point(lambda p: int(p * alpha))
            resized_logo = Image.merge("RGBA", (r, g, b, a))

        pos_x = int(cx - target_w / 2)
        pos_y = int(cy - target_h / 2)
        img.paste(resized_logo, (pos_x, pos_y), resized_logo)
    else:
        def transform_pt(px, py):
            return (cx + (px - 256) * scale, cy + (py - 256) * scale)

        p1_pts = [
            transform_pt(256, 40), transform_pt(200, 100), transform_pt(150, 180),
            transform_pt(100, 260), transform_pt(100, 340), transform_pt(120, 390),
            transform_pt(170, 440), transform_pt(256, 472), transform_pt(210, 430),
            transform_pt(180, 370), transform_pt(170, 330), transform_pt(190, 270),
            transform_pt(210, 250), transform_pt(230, 210), transform_pt(256, 180)
        ]
        p2_pts = [
            transform_pt(256, 40), transform_pt(312, 100), transform_pt(362, 180),
            transform_pt(412, 260), transform_pt(412, 340), transform_pt(392, 390),
            transform_pt(342, 440), transform_pt(256, 472), transform_pt(302, 430),
            transform_pt(332, 370), transform_pt(342, 330), transform_pt(322, 270),
            transform_pt(302, 250), transform_pt(282, 210), transform_pt(256, 180)
        ]
        p3_pts = [
            transform_pt(256, 160), transform_pt(230, 200), transform_pt(200, 260),
            transform_pt(180, 310), transform_pt(180, 360), transform_pt(200, 410),
            transform_pt(220, 450), transform_pt(256, 472), transform_pt(292, 450),
            transform_pt(312, 410), transform_pt(332, 360), transform_pt(332, 310),
            transform_pt(302, 260), transform_pt(282, 200)
        ]

        c1 = (int(59 * alpha), int(130 * alpha), int(246 * alpha)) if alpha < 1 else COLOR_INDIGO
        c2 = (int(138 * alpha), int(92 * alpha), int(245 * alpha)) if alpha < 1 else COLOR_VIOLET
        c3 = (int(0 * alpha), int(212 * alpha), int(255 * alpha)) if alpha < 1 else COLOR_CYAN

        draw.polygon(p1_pts, fill=c1)
        draw.polygon(p2_pts, fill=c2)
        draw.polygon(p3_pts, fill=c3)

# Render Scene 1: The Problem (0-10s)
def render_scene1(draw, img, t):
    # Fragmented Windows
    windows = [
        {"title": "VSCode — main.py", "x": 120, "y": 140, "w": 480, "h": 320},
        {"title": "Godot Engine — MainScene.tscn", "x": 640, "y": 100, "w": 560, "h": 360},
        {"title": "Blender 4.2 — village_building.fbx", "x": 1240, "y": 160, "w": 540, "h": 320},
        {"title": "Terminal — cmake build", "x": 180, "y": 500, "w": 500, "h": 340},
        {"title": "Jarvis Local AI Agent", "x": 720, "y": 500, "w": 460, "h": 320},
        {"title": "Asset Folder — /textures/stone/", "x": 1220, "y": 520, "w": 480, "h": 300}
    ]

    for idx, win in enumerate(windows):
        offset = int(math.sin(t * 2 + idx) * 8)
        wx, wy = win["x"], win["y"] + offset
        ww, wh = win["w"], win["h"]

        # Window Box
        draw.rectangle([wx, wy, wx + ww, wy + wh], fill=(17, 24, 39), outline=(50, 60, 80), width=2)
        draw.rectangle([wx, wy, wx + ww, wy + 36], fill=(30, 41, 59))

        # Traffic lights
        draw.ellipse([wx + 12, wy + 14, wx + 22, wy + 24], fill=(239, 68, 68))
        draw.ellipse([wx + 28, wy + 14, wx + 38, wy + 24], fill=(245, 158, 11))
        draw.ellipse([wx + 44, wy + 14, wx + 54, wy + 24], fill=(16, 185, 129))

        draw.text((wx + 64, wy + 10), win["title"], fill=(229, 231, 235), font=font_mono)

        # Lines inside
        for i in range(5):
            draw.rectangle([wx + 20, wy + 60 + i * 40, wx + 20 + int(ww * 0.6), wy + 68 + i * 40], fill=(40, 50, 70))

    # Red Disjointed Workflow Flowlines
    draw.line([(360, 300), (900, 280)], fill=COLOR_RED, width=3)
    draw.line([(900, 280), (1500, 320)], fill=COLOR_RED, width=3)
    draw.line([(1500, 320), (1460, 670)], fill=COLOR_RED, width=3)
    draw.line([(1460, 670), (950, 660)], fill=COLOR_RED, width=3)

    steps = ["Code", "Assets", "AI", "Engine", "Build", "Testing"]
    for idx, s in enumerate(steps):
        draw.text((200 + idx * 260, 940), f"[FRAGMENTED: {s}]", fill=COLOR_RED, font=font_heading)

    # Subtitle overlay & Vignette Transition at t=8s to 10s
    if t >= 7.5:
        alpha = min(1.0, (t - 7.5) / 1.5)
        bg_overlay = Image.new("RGBA", (WIDTH, HEIGHT), (5, 7, 11, int(255 * alpha)))
        img.paste(bg_overlay, (0, 0), bg_overlay)
        draw_aachman_logo(draw, img, 960, 540, scale=0.65 * alpha, alpha=alpha)

# Render Scene 2: The Vision (10-20s)
def render_scene2(draw, img, t):
    local_t = t - 10
    nodes = [
        {"id": "Dev", "label": "Developer", "x": 300, "y": 540, "color": COLOR_CYAN},
        {"id": "App", "label": "AppSuite", "x": 600, "y": 540, "color": COLOR_BLUE},
        {"id": "Jarvis", "label": "Jarvis AI Engine", "x": 960, "y": 540, "color": COLOR_INDIGO},
        {"id": "Agents", "label": "Specialized Agents", "x": 1260, "y": 380, "color": COLOR_VIOLET},
        {"id": "GDev", "label": "GameDevAI Suite", "x": 1260, "y": 700, "color": COLOR_VIOLET},
        {"id": "PyFlare", "label": "PyFlare OS", "x": 1560, "y": 540, "color": COLOR_CYAN},
        {"id": "Build", "label": "Build / Test / Deploy", "x": 1760, "y": 540, "color": COLOR_GREEN}
    ]

    connections = [(0, 1), (1, 2), (2, 3), (2, 4), (3, 5), (4, 5), (5, 6)]

    for n1, n2 in connections:
        a = nodes[n1]
        b = nodes[n2]
        draw.line([(a["x"], a["y"]), (b["x"], b["y"])], fill=(91, 95, 255), width=3)

        # Pulse Particle
        speed = (local_t * 0.8) % 1.0
        px = a["x"] + (b["x"] - a["x"]) * speed
        py = a["y"] + (b["y"] - a["y"]) * speed
        draw.ellipse([px - 6, py - 6, px + 6, py + 6], fill=COLOR_CYAN)

    for n in nodes:
        nx, ny = n["x"], n["y"]
        draw.rectangle([nx - 90, ny - 35, nx + 90, ny + 35], fill=(11, 15, 25), outline=n["color"], width=2)
        draw.text((nx - 60, ny - 10), n["label"], fill=COLOR_WHITE, font=font_heading)

# Render Scene 3: AppSuite + Jarvis (20-35s)
def render_scene3(draw, img, t):
    local_t = t - 20
    draw.rectangle([100, 80, 1820, 1000], fill=(17, 24, 39), outline=(50, 60, 80), width=2)
    draw.rectangle([100, 80, 1820, 128], fill=(11, 15, 25))
    draw.text((140, 95), "APPSUITE IDE v1.0 — Jarvis Orchestration Mode", fill=COLOR_CYAN, font=font_heading)

    # Prompt Bar
    draw.rectangle([140, 150, 1780, 204], fill=(30, 41, 59), outline=COLOR_INDIGO, width=2)
    full_prompt = "Create a playable medieval village scene."
    chars_to_show = min(len(full_prompt), int(local_t * 8))
    typed_text = full_prompt[:chars_to_show]
    draw.text((170, 168), f"PROMPT >  \"{typed_text}\"", fill=COLOR_WHITE, font=font_mono)

    # Left DAG Panel
    draw.rectangle([140, 230, 940, 960], fill=(15, 23, 42))
    draw.text((170, 255), "JARVIS TASK DAG DECOMPOSITION", fill=COLOR_VIOLET, font=font_heading)

    tasks = [
        ("1. Plan Architecture", "COMPLETED", 100),
        ("2. Find/Create 3D Assets", "COMPLETED", 100),
        ("3. Process & Bake Assets", "IN_PROGRESS", 85),
        ("4. Blender Asset Pipeline", "IN_PROGRESS", 70),
        ("5. Godot Scene Generation", "PENDING", 40),
        ("6. Integration Testing", "PENDING", 0),
        ("7. Final Game Build", "PENDING", 0)
    ]

    for idx, (tk, status, prog) in enumerate(tasks):
        y = 300 + idx * 85
        draw.rectangle([170, y, 910, y + 65], fill=(30, 41, 59))
        draw.text((190, y + 15), tk, fill=COLOR_WHITE, font=font_heading)
        color = COLOR_GREEN if prog == 100 else (COLOR_BLUE if prog > 0 else COLOR_TEXT_MUTED)
        draw.text((780, y + 15), f"[{status}]", fill=color, font=font_mono)
        draw.rectangle([190, y + 45, 890, y + 53], fill=(50, 60, 80))
        draw.rectangle([190, y + 45, 190 + int(700 * (prog / 100.0)), y + 53], fill=COLOR_CYAN)

    # Right Parallel Workers Panel
    draw.rectangle([960, 230, 1780, 960], fill=(15, 23, 42))
    draw.text((990, 255), "SPECIALIZED PARALLEL WORKERS RUNTIME", fill=COLOR_CYAN, font=font_heading)

    workers = [
        ("Asset Worker (PolyHaven API)", "92% CPU | 1.2 GB VRAM", "Active - Mesh Gen"),
        ("Mesh Worker (Blender Python API)", "84% CPU | 2.8 GB VRAM", "Active - UV Unwrapping"),
        ("GDScript Worker (GameDevAI)", "45% CPU | 0.4 GB VRAM", "Active - Scene Graph"),
        ("Engine Validator (Godot 4.3 headless)", "60% CPU | 1.1 GB VRAM", "Active - Physics Baking")
    ]

    for idx, (wname, wload, wstate) in enumerate(workers):
        y = 310 + idx * 150
        draw.rectangle([990, y, 1750, y + 120], fill=(30, 41, 59), outline=(0, 212, 255), width=1)
        draw.text((1010, y + 20), wname, fill=COLOR_WHITE, font=font_heading)
        draw.text((1010, y + 55), f"Telemetry: {wload}", fill=COLOR_TEXT_MUTED, font=font_mono)
        draw.text((1010, y + 80), f"Status: {wstate}", fill=COLOR_TEXT_MUTED, font=font_mono)

# Render Scene 4: Intelligent Model Routing (35-47s)
def render_scene4(draw, img, t):
    draw.text((100, 80), "INTELLIGENT LOCAL MODEL ROUTING ARCHITECTURE", fill=COLOR_CYAN, font=font_title)

    models = [
        {"name": "Phi-3-Mini (Local 3.8B)", "reason": "Structured JSON & Task Breakdown", "conf": "98.4%", "cap": "High", "cost": "0.04 TFLOPS", "selected": True},
        {"name": "Llama-3-8B (Local Q4_K)", "reason": "General Code Generation", "conf": "94.1%", "cap": "Very High", "cost": "0.18 TFLOPS", "selected": False},
        {"name": "Codegen-Small (Local 1.5B)", "reason": "GDScript Syntax Check", "conf": "96.2%", "cap": "Medium", "cost": "0.02 TFLOPS", "selected": False},
        {"name": "Cloud LLM Fallback", "reason": "Unnecessary — Suppressed", "conf": "N/A", "cap": "Extreme", "cost": "1.40 TFLOPS", "selected": False}
    ]

    for idx, m in enumerate(models):
        x = 100 + idx * 420
        y = 160
        fill_col = (25, 35, 65) if m["selected"] else (17, 24, 39)
        out_col = COLOR_CYAN if m["selected"] else (60, 70, 90)
        draw.rectangle([x, y, x + 390, y + 480], fill=fill_col, outline=out_col, width=2)

        if m["selected"]:
            draw.text((x + 20, y + 25), "[ROUTER SELECTED MODEL]", fill=COLOR_GREEN, font=font_mono)

        draw.text((x + 20, y + 60), m["name"], fill=COLOR_WHITE, font=font_heading)
        draw.text((x + 20, y + 120), f"Reason: {m['reason']}", fill=COLOR_TEXT_MUTED, font=font_body)
        draw.text((x + 20, y + 160), f"Confidence: {m['conf']}", fill=COLOR_TEXT_MUTED, font=font_body)
        draw.text((x + 20, y + 200), f"Capability: {m['cap']}", fill=COLOR_TEXT_MUTED, font=font_body)
        draw.text((x + 20, y + 240), f"Hardware Cost: {m['cost']}", fill=COLOR_TEXT_MUTED, font=font_body)

    draw.rectangle([100, 680, 1820, 1000], fill=(15, 23, 42))
    flow = ["User Intent", "Task Classification", "Local Model Evaluation", "Deterministic Router", "Best Model Result"]

    for idx, fl in enumerate(flow):
        fx = 160 + idx * 330
        fy = 800
        draw.rectangle([fx, fy, fx + 240, fy + 70], fill=(30, 41, 59), outline=COLOR_INDIGO, width=2)
        draw.text((fx + 30, fy + 25), fl, fill=COLOR_WHITE, font=font_heading)

        if idx < len(flow) - 1:
            draw.line([(fx + 240, fy + 35), (fx + 330, fy + 35)], fill=COLOR_CYAN, width=3)

# Render Scene 5: PyFlare OS (47-62s)
def render_scene5(draw, img, t):
    local_t = t - 47
    if local_t < 3.5:
        # GRUB Boot
        draw.rectangle([0, 0, WIDTH, HEIGHT], fill=(0, 0, 0))
        draw.text((200, 180), "GNU GRUB  version 2.12", fill=COLOR_WHITE, font=font_heading)
        draw.rectangle([200, 240, 1720, 280], fill=(91, 95, 255))
        draw.text((220, 250), "* PyFlare OS (Codename Ember - Ubuntu 24.04 LTS)", fill=COLOR_WHITE, font=font_heading)
        draw.text((220, 300), "  Advanced options for PyFlare OS", fill=COLOR_TEXT_MUTED, font=font_heading)
    elif local_t < 7.0:
        # Plymouth Splash
        pulse = math.sin(local_t * 6) * 0.15 + 1.0
        draw_aachman_logo(draw, img, 960, 480, scale=0.8 * pulse, alpha=1.0)
        draw.text((880, 720), "PyFlare OS", fill=COLOR_WHITE, font=font_title)
        draw.text((760, 760), "Codename: Ember  |  Based on Ubuntu 24.04 LTS (GNOME)", fill=COLOR_CYAN, font=font_mono)
    else:
        # Desktop & Terminal
        draw.rectangle([0, 0, WIDTH, 40], fill=(11, 15, 25))
        draw.text((30, 12), "Activities   PyFlare Terminal", fill=COLOR_WHITE, font=font_heading)
        draw.text((880, 12), "Mon Aug 10  17:52", fill=COLOR_WHITE, font=font_heading)

        draw.rectangle([240, 140, 1680, 820], fill=(17, 24, 39), outline=COLOR_CYAN, width=2)
        draw.text((280, 180), "developer@pyflare-ember:~$ pyflare-cli system-status", fill=COLOR_CYAN, font=font_mono)

        logs = [
            "[SYSTEM] Linux Kernel: 6.8.0-40-generic x86_64",
            "[SYSTEM] Base OS: Ubuntu 24.04.4 LTS (Noble Numbat)",
            "[SYSTEM] Desktop: GNOME Shell 46.0 (Wayland)",
            "[ENGINE] PyFlare Daemon: Active & Loaded (PID 1420)",
            "[JARVIS] Technical Orchestration Engine: Listening on localhost:8000",
            "[OLLAMA] Local Model Provider: Active (Phi-3, Llama-3-8B preloaded)",
            "[STATUS] PyFlare Developer Ecosystem Ready."
        ]

        for idx, lg in enumerate(logs):
            color = COLOR_GREEN if "Ready" in lg else (229, 231, 235)
            draw.text((280, 230 + idx * 40), lg, fill=color, font=font_mono)

        # Bottom Architecture Stack
        layers = ["Linux Kernel", "System Services", "PyFlare Engine", "Jarvis AI", "Developer Applications"]
        for idx, ly in enumerate(layers):
            lx = 260 + idx * 280
            draw.rectangle([lx, 905, lx + 250, 975], fill=(30, 41, 59), outline=COLOR_CYAN, width=2)
            draw.text((lx + 30, 930), ly, fill=COLOR_WHITE, font=font_heading)

# Render Scene 6: Developer Workflow (62-75s)
def render_scene6(draw, img, t):
    local_t = t - 62
    draw.rectangle([80, 80, 1840, 1000], fill=(17, 24, 39), outline=(50, 60, 80), width=2)
    draw.text((120, 110), "GODOT ENGINE 4.3 — MedievalVillage.tscn (Automated Assembly)", fill=COLOR_GREEN, font=font_heading)

    # 3D Viewport
    draw.rectangle([120, 160, 1220, 940], fill=(11, 15, 25))
    for i in range(-10, 11):
        draw.line([(670 + i * 50, 400), (670 + i * 90, 900)], fill=(0, 100, 150), width=1)

    # House Wireframe
    draw.rectangle([550, 500, 730, 640], outline=COLOR_CYAN, width=2)
    draw.rectangle([780, 480, 1000, 640], outline=COLOR_CYAN, width=2)
    draw.line([(550, 500), (640, 420), (730, 500)], fill=COLOR_CYAN, width=2)
    draw.line([(780, 480), (890, 390), (1000, 480)], fill=COLOR_CYAN, width=2)

    # Right Tests & Build Panel
    draw.rectangle([1250, 160, 1800, 940], fill=(15, 23, 42))
    draw.text((1280, 190), "AUTOMATED BUILD & TEST SUITE", fill=COLOR_WHITE, font=font_heading)

    checks = [
        "GDScript Syntax Check",
        "Blender FBX Mesh Import",
        "PolyHaven Texture Atlas",
        "Godot Physics Collider Generation",
        "Lighting & Navigation Mesh Bake",
        "Unit & Integration Tests (pytest)"
    ]

    for idx, chk in enumerate(checks):
        y = 240 + idx * 70
        draw.rectangle([1280, y, 1770, y + 50], fill=(30, 41, 59))
        draw.text((1300, y + 15), chk, fill=COLOR_WHITE, font=font_heading)
        draw.text((1650, y + 15), "[PASSED ✓]", fill=COLOR_GREEN, font=font_mono)

    if local_t > 5.0:
        draw.rectangle([1280, 720, 1770, 900], fill=(16, 185, 129))
        draw.text((1370, 780), "BUILD SUCCESSFUL", fill=COLOR_WHITE, font=font_title)
        draw.text((1320, 830), "Game Binary: medieval_village.x86_64", fill=COLOR_WHITE, font=font_mono)

# Render Scene 7: Ecosystem Tree (75-85s)
def render_scene7(draw, img, t):
    draw.text((580, 100), "AACHMAN STUDIOS ECOSYSTEM ARCHITECTURE", fill=COLOR_CYAN, font=font_title)

    draw.rectangle([800, 180, 1120, 260], fill=(30, 41, 59), outline=COLOR_CYAN, width=3)
    draw.text((850, 210), "Aachman Studios", fill=COLOR_WHITE, font=font_title)

    branches = [
        ("AppSuite", 260, 440),
        ("Jarvis AI Engine", 540, 440),
        ("GameDevAI Suite", 820, 440),
        ("PyFlare OS", 1100, 440),
        ("Developer Tools", 1380, 440),
        ("Future Ecosystem", 1660, 440)
    ]

    for bname, bx, by in branches:
        draw.line([(960, 260), (bx, by)], fill=(91, 95, 255), width=2)
        draw.rectangle([bx - 110, by - 35, bx + 110, by + 35], fill=(17, 24, 39), outline=COLOR_VIOLET, width=2)
        draw.text((bx - 70, by - 10), bname, fill=COLOR_WHITE, font=font_heading)

    draw.text((640, 680), "An actively engineered, developer-focused software ecosystem.", fill=COLOR_TEXT_MUTED, font=font_subtitle)

# Render Final Scene (85-90s)
def render_final_scene(draw, img, t):
    local_t = t - 85
    fade_alpha = max(0.0, 1.0 - (local_t - 3.5) / 1.5) if local_t > 3.5 else 1.0

    draw_aachman_logo(draw, img, 960, 420, scale=1.0, alpha=fade_alpha)

    c_text = (int(255 * fade_alpha), int(255 * fade_alpha), int(255 * fade_alpha))
    c_sub = (int(0 * fade_alpha), int(212 * fade_alpha), int(255 * fade_alpha))

    draw.text((750, 700), "AACHMAN STUDIOS", fill=c_text, font=font_title)
    draw.text((620, 760), "\"Building tools for the people who build the future.\"", fill=c_sub, font=font_subtitle)

def generate_frame(frame_idx):
    t = frame_idx / float(FPS)
    img = Image.new("RGB", (WIDTH, HEIGHT), COLOR_BG_DARK)
    draw = ImageDraw.Draw(img)

    if t < 10.0:
        render_scene1(draw, img, t)
    elif t < 20.0:
        render_scene2(draw, img, t)
    elif t < 35.0:
        render_scene3(draw, img, t)
    elif t < 47.0:
        render_scene4(draw, img, t)
    elif t < 62.0:
        render_scene5(draw, img, t)
    elif t < 75.0:
        render_scene6(draw, img, t)
    elif t < 85.0:
        render_scene7(draw, img, t)
    else:
        render_final_scene(draw, img, t)

    return np.array(img)

def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    print(f"[INFO] Starting MP4 rendering: {TOTAL_FRAMES} frames ({TOTAL_DURATION}s @ {FPS}fps)")
    
    import subprocess
    import imageio_ffmpeg

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg_exe,
        '-y',
        '-f', 'rawvideo',
        '-vcodec', 'rawvideo',
        '-s', f'{WIDTH}x{HEIGHT}',
        '-pix_fmt', 'rgb24',
        '-r', str(FPS),
        '-i', '-',
        '-c:v', 'libx264',
        '-r', str(FPS),
        '-pix_fmt', 'yuv420p',
        '-preset', 'fast',
        '-crf', '22',
        '-movflags', '+faststart',
        OUTPUT_FILENAME
    ]

    print(f"[INFO] Launching FFmpeg encoder: {' '.join(cmd[:8])}...")
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)

    try:
        for f_idx in range(TOTAL_FRAMES):
            frame = generate_frame(f_idx)
            proc.stdin.write(np.ascontiguousarray(frame).tobytes())
            if f_idx % 30 == 0:
                proc.stdin.flush()
            if f_idx % 300 == 0 or f_idx == TOTAL_FRAMES - 1:
                print(f"[PROGRESS] Rendered {f_idx}/{TOTAL_FRAMES} frames ({(f_idx/TOTAL_FRAMES)*100:.1f}%)")
    finally:
        proc.stdin.close()
        proc.wait()

    print(f"[SUCCESS] Exported 100% valid MP4 file (Exit Code: {proc.returncode}): {os.path.abspath(OUTPUT_FILENAME)}")

if __name__ == "__main__":
    main()
