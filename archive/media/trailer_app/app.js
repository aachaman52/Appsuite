/**
 * Aachman Studios — Cinematic Technology Trailer Engine
 * Duration: 90.0 seconds | Frame Rate: 60 FPS
 * Brand Identity: Official Aachman Studios Logo (#5B5FFF, #8A5CF5, #00D4FF)
 */

(function () {
  'use strict';

  // Constants & State
  const TOTAL_DURATION = 90.0; // Seconds
  let currentTime = 0.0;
  let isPlaying = false;
  let playbackRate = 1.0;
  let audioEnabled = true;
  let subtitlesEnabled = true;
  let lastFrameTime = performance.now();
  let fps = 60;
  let frameCount = 0;
  let lastFpsUpdate = performance.now();

  // Audio Context (Web Audio API Synthesizer)
  let audioCtx = null;
  let synthGain = null;
  let droneOsc1 = null;
  let droneOsc2 = null;

  // DOM Elements
  const canvas = document.getElementById('trailer-canvas');
  const ctx = canvas.getContext('2d');
  const btnPlay = document.getElementById('btn-play');
  const iconPlay = document.getElementById('icon-play');
  const iconPause = document.getElementById('icon-pause');
  const btnRestart = document.getElementById('btn-restart');
  const btnAudio = document.getElementById('btn-audio');
  const btnSubtitles = document.getElementById('btn-subtitles');
  const btnFullscreen = document.getElementById('btn-fullscreen');
  const speedSelect = document.getElementById('speed-select');
  const timelineProgress = document.getElementById('timeline-progress');
  const timelineScrubber = document.getElementById('timeline-scrubber');
  const timelineBar = document.getElementById('timeline-bar');
  const timeDisplay = document.getElementById('time-display');
  const sceneBadge = document.getElementById('scene-badge');
  const sceneTitleActive = document.getElementById('scene-title-active');
  const fpsDisplay = document.getElementById('fps-display');
  const narrationContainer = document.getElementById('narration-container');
  const narrationText = document.getElementById('narration-text');
  const markerButtons = document.querySelectorAll('.scene-markers .marker');

  // Scene Definitions
  const SCENES = [
    { id: 1, start: 0, end: 10, title: 'Scene 1 — The Problem', badge: 'SCENE 1: THE PROBLEM' },
    { id: 2, start: 10, end: 20, title: 'Scene 2 — The Vision', badge: 'SCENE 2: THE VISION' },
    { id: 3, start: 20, end: 35, title: 'Scene 3 — AppSuite + Jarvis', badge: 'SCENE 3: APPSUITE + JARVIS' },
    { id: 4, start: 35, end: 47, title: 'Scene 4 — Intelligent Model Routing', badge: 'SCENE 4: MODEL ROUTING' },
    { id: 5, start: 47, end: 62, title: 'Scene 5 — PyFlare OS', badge: 'SCENE 5: PYFLARE OS' },
    { id: 6, start: 62, end: 75, title: 'Scene 6 — The Developer Workflow', badge: 'SCENE 6: WORKFLOW' },
    { id: 7, start: 75, end: 85, title: 'Scene 7 — The Ecosystem', badge: 'SCENE 7: ECOSYSTEM TREE' },
    { id: 8, start: 85, end: 90, title: 'Final Scene — Aachman Studios', badge: 'FINAL SCENE' }
  ];

  // Narration Script Cues
  const NARRATIONS = [
    { time: 2.0, text: "Game development shouldn't feel like managing 20 different systems." },
    { time: 10.5, text: "Aachman Studios is building an ecosystem where development tools work together instead of working against each other." },
    { time: 20.5, text: "AppSuite pairs with Jarvis AI as a technical orchestration layer to coordinate specialized development agents." },
    { time: 35.5, text: "Use the right intelligence for the right task. Intelligent routing selects local models deterministically without wasting resources." },
    { time: 47.5, text: "PyFlare OS — An AI-native Linux operating system built on Ubuntu 24.04 LTS, designed for developers." },
    { time: 62.5, text: "From prompt to scene assembly, automated testing, and compilation — a single connected workflow." },
    { time: 75.5, text: "An actively engineered ecosystem built for independence, performance, and complete developer empowerment." },
    { time: 85.5, text: "Aachman Studios. Building tools for the people who build the future." }
  ];

  // Particle System Data
  const particles = Array.from({ length: 60 }, () => ({
    x: Math.random() * 1920,
    y: Math.random() * 1080,
    vx: (Math.random() - 0.5) * 0.8,
    vy: (Math.random() - 0.5) * 0.8,
    size: Math.random() * 2.5 + 1,
    alpha: Math.random() * 0.5 + 0.2
  }));

  // Helper: Format Time string MM:SS.S
  function formatTime(sec) {
    const mins = Math.floor(sec / 60);
    const secs = (sec % 60).toFixed(1);
    return `${mins.toString().padStart(2, '0')}:${secs.padStart(4, '0')}`;
  }

  // Audio System Initialization (Synthesizer Drone & UI Sound FX)
  function initAudio() {
    if (audioCtx) return;
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      audioCtx = new AudioCtx();

      synthGain = audioCtx.createGain();
      synthGain.gain.setValueAtTime(0.08, audioCtx.currentTime);

      // Low Ambient Drone 1 (Indigo/Cyan Harmonic)
      droneOsc1 = audioCtx.createOscillator();
      droneOsc1.type = 'sawtooth';
      droneOsc1.frequency.setValueAtTime(55.0, audioCtx.currentTime); // A1 note

      // Low Ambient Drone 2
      droneOsc2 = audioCtx.createOscillator();
      droneOsc2.type = 'sine';
      droneOsc2.frequency.setValueAtTime(110.0, audioCtx.currentTime); // A2 note

      const filter = audioCtx.createBiquadFilter();
      filter.type = 'lowpass';
      filter.frequency.setValueAtTime(220, audioCtx.currentTime);

      droneOsc1.connect(filter);
      droneOsc2.connect(filter);
      filter.connect(synthGain);
      synthGain.connect(audioCtx.destination);

      droneOsc1.start();
      droneOsc2.start();
    } catch (e) {
      console.warn("Web Audio API not allowed or supported:", e);
    }
  }

  function triggerBeep(freq = 440, duration = 0.08) {
    if (!audioCtx || !audioEnabled) return;
    try {
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
      gain.gain.setValueAtTime(0.05, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + duration);
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.start();
      osc.stop(audioCtx.currentTime + duration);
    } catch (e) {}
  }

  // Official Uploaded Aachman Studios Logo Image Element
  const logoImage = new Image();
  logoImage.src = 'aachmanstiudios.png';

  // Official Aachman Studios Logo Drawer
  function drawAachmanLogo(c, x, y, scale = 1.0, alpha = 1.0) {
    c.save();
    c.translate(x, y);
    c.scale(scale, scale);
    c.globalAlpha = alpha;

    // Glowing Ambient Shadow Effect
    c.shadowColor = '#00D4FF';
    c.shadowBlur = 30 * scale;

    if (logoImage.complete && logoImage.naturalWidth > 0) {
      const w = 480;
      const h = 480;
      c.drawImage(logoImage, -w / 2, -h / 2, w, h);
    } else {
      // Fallback path shapes if image loading
      const p1 = new Path2D("M0,-216 C-86,-116 -156,-16 -156,84 C-156,174 -86,216 0,216 C-66,164 -86,74 -46,-6 C-26,-46 0,-76 0,-76 Z");
      c.fillStyle = "#5B5FFF"; c.fill(p1);
      const p2 = new Path2D("M0,-216 C86,-116 156,-16 156,84 C156,174 86,216 0,216 C66,164 86,74 46,-6 C26,-46 0,-76 0,-76 Z");
      c.fillStyle = "#8A5CF5"; c.fill(p2);
      const p3 = new Path2D("M0,-96 C-46,-16 -76,54 -76,104 C-76,174 -36,216 0,216 C36,216 76,174 76,104 C76,54 46,-16 0,-96 Z");
      c.fillStyle = "#00D4FF"; c.fill(p3);
    }

    c.restore();
  }

  // Render Scene 1: The Problem (0-10s)
  function renderScene1(t) {
    // Workspace dark gradient
    const grad = ctx.createRadialGradient(960, 540, 100, 960, 540, 1000);
    grad.addColorStop(0, '#0d1322');
    grad.addColorStop(1, '#05070b');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, 1920, 1080);

    // Fragmented Windows Mockup
    const windows = [
      { title: 'VSCode — main.py', x: 120, y: 140, w: 480, h: 320, color: '#3B82F6' },
      { title: 'Godot Engine — MainScene.tscn', x: 640, y: 100, w: 560, h: 360, color: '#8A5CF5' },
      { title: 'Blender 4.2 — village_building.fbx', x: 1240, y: 160, w: 540, h: 320, color: '#00D4FF' },
      { title: 'Terminal — cmake build', x: 180, y: 500, w: 500, h: 340, color: '#10B981' },
      { title: 'Jarvis Local AI Agent', x: 720, y: 500, w: 460, h: 320, color: '#5B5FFF' },
      { title: 'Asset Folder — /textures/stone/', x: 1220, y: 520, w: 480, h: 300, color: '#F59E0B' }
    ];

    windows.forEach((win, idx) => {
      // Float animation
      const offset = Math.sin(t * 2 + idx) * 8;
      const wx = win.x;
      const wy = win.y + offset;

      // Window Frame
      ctx.fillStyle = 'rgba(17, 24, 39, 0.85)';
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.12)';
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.roundRect(wx, wy, win.w, win.h, 8);
      ctx.fill();
      ctx.stroke();

      // Window Header Bar
      ctx.fillStyle = 'rgba(30, 41, 59, 0.9)';
      ctx.beginPath();
      ctx.roundRect(wx, wy, win.w, 36, [8, 8, 0, 0]);
      ctx.fill();

      // Traffic Lights
      ctx.fillStyle = '#EF4444'; ctx.beginPath(); ctx.arc(wx + 16, wy + 18, 5, 0, Math.PI*2); ctx.fill();
      ctx.fillStyle = '#F59E0B'; ctx.beginPath(); ctx.arc(wx + 32, wy + 18, 5, 0, Math.PI*2); ctx.fill();
      ctx.fillStyle = '#10B981'; ctx.beginPath(); ctx.arc(wx + 48, wy + 18, 5, 0, Math.PI*2); ctx.fill();

      // Window Title
      ctx.fillStyle = '#E5E7EB';
      ctx.font = '12px "JetBrains Mono"';
      ctx.fillText(win.title, wx + 64, wy + 22);

      // Window Content Lines Mockup
      ctx.fillStyle = 'rgba(255, 255, 255, 0.15)';
      for (let i = 0; i < 6; i++) {
        ctx.fillRect(wx + 20, wy + 60 + i * 36, (win.w - 40) * (0.4 + (i % 3) * 0.25), 8);
      }
    });

    // Disjointed Workflow Flowlines (Red/Orange dashed lines)
    ctx.strokeStyle = '#EF4444';
    ctx.lineWidth = 2;
    ctx.setLineDash([8, 6]);
    ctx.beginPath();
    ctx.moveTo(360, 300); ctx.lineTo(900, 280);
    ctx.moveTo(900, 280); ctx.lineTo(1500, 320);
    ctx.moveTo(1500, 320); ctx.lineTo(1460, 670);
    ctx.moveTo(1460, 670); ctx.lineTo(950, 660);
    ctx.moveTo(950, 660); ctx.lineTo(430, 670);
    ctx.stroke();
    ctx.setLineDash([]);

    // Workflow Labels overlay
    const steps = ['Code', 'Assets', 'AI', 'Engine', 'Build', 'Testing'];
    ctx.font = '700 13px "Space Grotesk"';
    ctx.fillStyle = '#EF4444';
    steps.forEach((s, idx) => {
      ctx.fillText(`[FRAGMENTED: ${s}]`, 200 + idx * 260, 940);
    });

    // Subtitle reveal effect at t=8s to 10s logo transition
    if (t >= 7.5) {
      const alpha = Math.min(1.0, (t - 7.5) / 1.5);
      ctx.fillStyle = `rgba(5, 7, 11, ${alpha * 0.9})`;
      ctx.fillRect(0, 0, 1920, 1080);
      drawAachmanLogo(ctx, 960, 540, 0.65 * alpha, alpha);
    }
  }

  // Render Scene 2: The Vision (10-20s)
  function renderScene2(t) {
    const localT = t - 10;
    ctx.fillStyle = '#07090e';
    ctx.fillRect(0, 0, 1920, 1080);

    // Network Nodes Definition
    const nodes = [
      { id: 'Dev', label: 'Developer', x: 300, y: 540, color: '#00D4FF' },
      { id: 'App', label: 'AppSuite', x: 600, y: 540, color: '#3B82F6' },
      { id: 'Jarvis', label: 'Jarvis AI Engine', x: 960, y: 540, color: '#5B5FFF' },
      { id: 'Agents', label: 'Specialized Agents', x: 1260, y: 380, color: '#8A5CF5' },
      { id: 'GDev', label: 'GameDevAI Suite', x: 1260, y: 700, color: '#8A5CF5' },
      { id: 'PyFlare', label: 'PyFlare OS', x: 1560, y: 540, color: '#00D4FF' },
      { id: 'Build', label: 'Build / Test / Deploy', x: 1760, y: 540, color: '#10B981' }
    ];

    const connections = [
      [0, 1], [1, 2], [2, 3], [2, 4], [3, 5], [4, 5], [5, 6]
    ];

    // Draw Connections with Animated Glowing Data Streams
    connections.forEach(([n1, n2]) => {
      const a = nodes[n1];
      const b = nodes[n2];

      ctx.strokeStyle = 'rgba(91, 95, 255, 0.3)';
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      ctx.stroke();

      // Data Packet Pulse
      const speed = (localT * 0.8) % 1.0;
      const px = a.x + (b.x - a.x) * speed;
      const py = a.y + (b.y - a.y) * speed;

      ctx.fillStyle = '#00D4FF';
      ctx.shadowColor = '#00D4FF';
      ctx.shadowBlur = 12;
      ctx.beginPath();
      ctx.arc(px, py, 5, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;
    });

    // Draw Nodes
    nodes.forEach(node => {
      ctx.fillStyle = 'rgba(11, 15, 25, 0.95)';
      ctx.strokeStyle = node.color;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.roundRect(node.x - 90, node.y - 35, 180, 70, 10);
      ctx.fill();
      ctx.stroke();

      ctx.fillStyle = '#FFFFFF';
      ctx.font = '600 13px "Space Grotesk"';
      ctx.textAlign = 'center';
      ctx.fillText(node.label, node.x, node.y + 5);
    });

    ctx.textAlign = 'left';
  }

  // Render Scene 3: AppSuite + Jarvis (20-35s)
  function renderScene3(t) {
    const localT = t - 20;
    ctx.fillStyle = '#070A12';
    ctx.fillRect(0, 0, 1920, 1080);

    // AppSuite Desktop Outer Container
    ctx.fillStyle = 'rgba(17, 24, 39, 0.7)';
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.roundRect(100, 80, 1720, 920, 12);
    ctx.fill();
    ctx.stroke();

    // AppSuite Top Navigation Bar
    ctx.fillStyle = 'rgba(11, 15, 25, 0.9)';
    ctx.beginPath();
    ctx.roundRect(100, 80, 1720, 48, [12, 12, 0, 0]);
    ctx.fill();

    ctx.fillStyle = '#00D4FF';
    ctx.font = '700 14px "Space Grotesk"';
    ctx.fillText('APPSUITE IDE v1.0 — Jarvis Orchestration Mode', 140, 110);

    // Prompt Bar
    ctx.fillStyle = 'rgba(30, 41, 59, 0.9)';
    ctx.strokeStyle = '#5B5FFF';
    ctx.beginPath();
    ctx.roundRect(140, 150, 1640, 54, 8);
    ctx.fill();
    ctx.stroke();

    // Typewriter Prompt Text
    const fullPrompt = 'Create a playable medieval village scene.';
    const charsToShow = Math.min(fullPrompt.length, Math.floor(localT * 8));
    const typedText = fullPrompt.substring(0, charsToShow);

    ctx.fillStyle = '#FFFFFF';
    ctx.font = '500 16px "JetBrains Mono"';
    ctx.fillText(`PROMPT >  "${typedText}${charsToShow < fullPrompt.length ? '|' : ''}"`, 170, 184);

    // Jarvis Orchestration Task Decomposition (DAG Execution View)
    ctx.fillStyle = 'rgba(15, 23, 42, 0.9)';
    ctx.roundRect(140, 230, 800, 730, 8);
    ctx.fill();

    ctx.fillStyle = '#8A5CF5';
    ctx.font = '700 14px "Space Grotesk"';
    ctx.fillText('JARVIS TASK DAG DECOMPOSITION', 170, 265);

    const tasks = [
      { step: '1. Plan Architecture', status: 'COMPLETED', progress: 100 },
      { step: '2. Find/Create 3D Assets', status: 'COMPLETED', progress: 100 },
      { step: '3. Process & Bake Assets', status: 'IN_PROGRESS', progress: 85 },
      { step: '4. Blender Asset Pipeline', status: 'IN_PROGRESS', progress: 70 },
      { step: '5. Godot Scene Generation', status: 'PENDING', progress: 40 },
      { step: '6. Integration Testing', status: 'PENDING', progress: 0 },
      { step: '7. Final Game Build', status: 'PENDING', progress: 0 }
    ];

    tasks.forEach((tk, i) => {
      const y = 300 + i * 85;
      ctx.fillStyle = 'rgba(30, 41, 59, 0.6)';
      ctx.roundRect(170, y, 740, 65, 6);
      ctx.fill();

      ctx.fillStyle = '#E5E7EB';
      ctx.font = '600 14px "Space Grotesk"';
      ctx.fillText(tk.step, 190, y + 28);

      // Status Pill
      ctx.fillStyle = tk.progress === 100 ? '#10B981' : (tk.progress > 0 ? '#3B82F6' : '#6B7280');
      ctx.font = '700 11px "JetBrains Mono"';
      ctx.fillText(`[${tk.status}]`, 780, y + 28);

      // Progress bar
      ctx.fillStyle = 'rgba(255, 255, 255, 0.1)';
      ctx.fillRect(190, y + 42, 700, 8);
      ctx.fillStyle = '#00D4FF';
      ctx.fillRect(190, y + 42, 700 * (tk.progress / 100), 8);
    });

    // Right Telemetry Panel: Parallel Workers Execution
    ctx.fillStyle = 'rgba(15, 23, 42, 0.9)';
    ctx.roundRect(960, 230, 820, 730, 8);
    ctx.fill();

    ctx.fillStyle = '#00D4FF';
    ctx.font = '700 14px "Space Grotesk"';
    ctx.fillText('SPECIALIZED PARALLEL WORKERS RUNTIME', 990, 265);

    const workers = [
      { name: 'Asset Worker (PolyHaven API)', load: '92% CPU | 1.2 GB VRAM', state: 'Active - Mesh Gen' },
      { name: 'Mesh Worker (Blender Python API)', load: '84% CPU | 2.8 GB VRAM', state: 'Active - UV Unwrapping' },
      { name: 'GDScript Worker (GameDevAI)', load: '45% CPU | 0.4 GB VRAM', state: 'Active - Scene Graph' },
      { name: 'Engine Validator (Godot 4.3 headless)', load: '60% CPU | 1.1 GB VRAM', state: 'Active - Physics Baking' }
    ];

    workers.forEach((w, i) => {
      const y = 310 + i * 150;
      ctx.fillStyle = 'rgba(30, 41, 59, 0.8)';
      ctx.strokeStyle = 'rgba(0, 212, 255, 0.2)';
      ctx.lineWidth = 1;
      ctx.roundRect(990, y, 760, 120, 8);
      ctx.fill(); ctx.stroke();

      ctx.fillStyle = '#FFFFFF';
      ctx.font = '700 15px "Space Grotesk"';
      ctx.fillText(w.name, 1010, y + 35);

      ctx.fillStyle = '#9CA3AF';
      ctx.font = '500 13px "JetBrains Mono"';
      ctx.fillText(`Telemetry: ${w.load}`, 1010, y + 65);
      ctx.fillText(`Status: ${w.state}`, 1010, y + 90);
    });
  }

  // Render Scene 4: Intelligent Model Routing (35-47s)
  function renderScene4(t) {
    const localT = t - 35;
    ctx.fillStyle = '#06080F';
    ctx.fillRect(0, 0, 1920, 1080);

    // Header
    ctx.fillStyle = '#00D4FF';
    ctx.font = '700 22px "Space Grotesk"';
    ctx.fillText('INTELLIGENT LOCAL MODEL ROUTING ARCHITECTURE', 100, 100);

    // Model Cards Evaluation Matrix
    const models = [
      { name: 'Phi-3-Mini (Local 3.8B)', reason: 'Structured JSON & Task Breakdown', conf: '98.4%', cap: 'High', cost: '0.04 TFLOPS', selected: true },
      { name: 'Llama-3-8B (Local Q4_K)', reason: 'General Code Generation', conf: '94.1%', cap: 'Very High', cost: '0.18 TFLOPS', selected: false },
      { name: 'Codegen-Small (Local 1.5B)', reason: 'GDScript Syntax Check', conf: '96.2%', cap: 'Medium', cost: '0.02 TFLOPS', selected: false },
      { name: 'Cloud LLM Fallback', reason: 'Unnecessary — Suppressed', conf: 'N/A', cap: 'Extreme', cost: '1.40 TFLOPS', selected: false }
    ];

    models.forEach((m, i) => {
      const x = 100 + i * 420;
      const y = 160;
      ctx.fillStyle = m.selected ? 'rgba(91, 95, 255, 0.18)' : 'rgba(17, 24, 39, 0.7)';
      ctx.strokeStyle = m.selected ? '#00D4FF' : 'rgba(255, 255, 255, 0.1)';
      ctx.lineWidth = m.selected ? 2.5 : 1;
      ctx.roundRect(x, y, 390, 480, 10);
      ctx.fill(); ctx.stroke();

      if (m.selected) {
        ctx.fillStyle = '#10B981';
        ctx.font = '700 11px "JetBrains Mono"';
        ctx.fillText('[ROUTER SELECTED MODEL]', x + 20, y + 35);
      }

      ctx.fillStyle = '#FFFFFF';
      ctx.font = '700 16px "Space Grotesk"';
      ctx.fillText(m.name, x + 20, y + 70);

      ctx.fillStyle = '#9CA3AF';
      ctx.font = '500 13px "Inter"';
      ctx.fillText(`Reason: ${m.reason}`, x + 20, y + 120);
      ctx.fillText(`Confidence: ${m.conf}`, x + 20, y + 160);
      ctx.fillText(`Capability: ${m.cap}`, x + 20, y + 200);
      ctx.fillText(`Hardware Cost: ${m.cost}`, x + 20, y + 240);
    });

    // Lower Architecture Pipeline Diagram
    ctx.fillStyle = 'rgba(15, 23, 42, 0.9)';
    ctx.roundRect(100, 680, 1720, 320, 10);
    ctx.fill();

    const flow = ['User Intent', 'Task Classification', 'Local Model Evaluation', 'Deterministic Router', 'Best Model Result'];
    flow.forEach((fl, idx) => {
      const fx = 160 + idx * 330;
      const fy = 800;
      ctx.fillStyle = 'rgba(30, 41, 59, 0.9)';
      ctx.strokeStyle = '#5B5FFF';
      ctx.lineWidth = 1.5;
      ctx.roundRect(fx, fy, 240, 70, 8);
      ctx.fill(); ctx.stroke();

      ctx.fillStyle = '#FFFFFF';
      ctx.font = '600 13px "Space Grotesk"';
      ctx.textAlign = 'center';
      ctx.fillText(fl, fx + 120, fy + 40);

      if (idx < flow.length - 1) {
        ctx.strokeStyle = '#00D4FF';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(fx + 240, fy + 35);
        ctx.lineTo(fx + 330, fy + 35);
        ctx.stroke();
      }
    });

    ctx.textAlign = 'left';
  }

  // Render Scene 5: PyFlare OS (47-62s)
  function renderScene5(t) {
    const localT = t - 47;
    ctx.fillStyle = '#05070B';
    ctx.fillRect(0, 0, 1920, 1080);

    // Boot sequence timeline progression
    if (localT < 3.5) {
      // 1. GRUB Bootloader View
      ctx.fillStyle = '#000000'; ctx.fillRect(0, 0, 1920, 1080);
      ctx.fillStyle = '#FFFFFF'; ctx.font = '700 18px "JetBrains Mono"';
      ctx.fillText('GNU GRUB  version 2.12', 200, 180);

      ctx.fillStyle = 'rgba(91, 95, 255, 0.3)';
      ctx.fillRect(200, 240, 1520, 40);
      ctx.fillStyle = '#00D4FF';
      ctx.fillText('* PyFlare OS (Codename Ember - Ubuntu 24.04 LTS)', 220, 266);
      ctx.fillStyle = '#AAAAAA';
      ctx.fillText('  Advanced options for PyFlare OS', 220, 316);
      ctx.fillText('  Memory test (memtest86+)', 220, 366);
    } else if (localT < 7.0) {
      // 2. PyFlare Plymouth Boot Splash
      ctx.fillStyle = '#070A12'; ctx.fillRect(0, 0, 1920, 1080);

      const pulse = Math.sin(localT * 6) * 0.15 + 1.0;
      drawAachmanLogo(ctx, 960, 480, 0.8 * pulse, 1.0);

      ctx.fillStyle = '#FFFFFF';
      ctx.font = '700 24px "Space Grotesk"';
      ctx.textAlign = 'center';
      ctx.fillText('PyFlare OS', 960, 720);
      ctx.font = '500 14px "JetBrains Mono"';
      ctx.fillStyle = '#00D4FF';
      ctx.fillText('Codename: Ember  |  Based on Ubuntu 24.04 LTS (GNOME)', 960, 760);
      ctx.textAlign = 'left';
    } else {
      // 3. PyFlare GNOME Desktop View
      ctx.fillStyle = '#0B0F19'; ctx.fillRect(0, 0, 1920, 1080);

      // Desktop Top Bar
      ctx.fillStyle = 'rgba(11, 15, 25, 0.95)';
      ctx.fillRect(0, 0, 1920, 40);
      ctx.fillStyle = '#FFFFFF'; ctx.font = '600 13px "Space Grotesk"';
      ctx.fillText('Activities', 30, 25);
      ctx.fillText('PyFlare Terminal', 130, 25);
      ctx.textAlign = 'center';
      ctx.fillText('Mon Aug 10  17:52', 960, 25);
      ctx.textAlign = 'right';
      ctx.fillText('100% [+]  Wi-Fi  Jarvis AI Active', 1890, 25);
      ctx.textAlign = 'left';

      // Open Terminal Window (pyflare-cli)
      ctx.fillStyle = 'rgba(17, 24, 39, 0.95)';
      ctx.strokeStyle = '#00D4FF';
      ctx.lineWidth = 1.5;
      ctx.roundRect(240, 140, 1440, 680, 8);
      ctx.fill(); ctx.stroke();

      ctx.fillStyle = '#00D4FF';
      ctx.font = '700 15px "JetBrains Mono"';
      ctx.fillText('developer@pyflare-ember:~$ pyflare-cli system-status', 280, 200);

      const logs = [
        '[SYSTEM] Linux Kernel: 6.8.0-40-generic x86_64',
        '[SYSTEM] Base OS: Ubuntu 24.04.4 LTS (Noble Numbat)',
        '[SYSTEM] Desktop: GNOME Shell 46.0 (Wayland)',
        '[ENGINE] PyFlare Daemon: Active & Loaded (PID 1420)',
        '[JARVIS] Technical Orchestration Engine: Listening on localhost:8000',
        '[OLLAMA] Local Model Provider: Active (Phi-3, Llama-3-8B preloaded)',
        '[STATUS] PyFlare Developer Ecosystem Ready.'
      ];

      logs.forEach((lg, idx) => {
        ctx.fillStyle = lg.includes('Ready') ? '#10B981' : '#D1D5DB';
        ctx.fillText(lg, 280, 250 + idx * 40);
      });

      // OS Architecture Layer Bar Footer
      ctx.fillStyle = 'rgba(15, 23, 42, 0.95)';
      ctx.fillRect(240, 880, 1440, 120);

      const layers = ['Linux Kernel', 'System Services', 'PyFlare Engine', 'Jarvis AI', 'Developer Applications'];
      layers.forEach((ly, i) => {
        const lx = 260 + i * 280;
        ctx.fillStyle = 'rgba(91, 95, 255, 0.2)';
        ctx.strokeStyle = '#00D4FF';
        ctx.roundRect(lx, 905, 250, 70, 6);
        ctx.fill(); ctx.stroke();

        ctx.fillStyle = '#FFFFFF';
        ctx.font = '600 13px "Space Grotesk"';
        ctx.textAlign = 'center';
        ctx.fillText(ly, lx + 125, 945);
      });
      ctx.textAlign = 'left';
    }
  }

  // Render Scene 6: The Developer Workflow (62-75s)
  function renderScene6(t) {
    const localT = t - 62;
    ctx.fillStyle = '#060810';
    ctx.fillRect(0, 0, 1920, 1080);

    // Continuous Workflow Automation View: Godot Engine 4.3 Viewport
    ctx.fillStyle = 'rgba(17, 24, 39, 0.9)';
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
    ctx.roundRect(80, 80, 1760, 920, 10);
    ctx.fill(); ctx.stroke();

    // Godot Header
    ctx.fillStyle = '#10B981';
    ctx.font = '700 16px "Space Grotesk"';
    ctx.fillText('GODOT ENGINE 4.3 — MedievalVillage.tscn (Automated Assembly)', 120, 120);

    // 3D Wireframe Viewport Preview Box
    ctx.fillStyle = '#0B0F19';
    ctx.roundRect(120, 160, 1100, 780, 8);
    ctx.fill();

    // Render 3D Perspective Village Grid & Buildings
    ctx.strokeStyle = 'rgba(0, 212, 255, 0.25)';
    ctx.lineWidth = 1;
    for (let i = -10; i <= 10; i++) {
      ctx.beginPath();
      ctx.moveTo(670 + i * 50, 400); ctx.lineTo(670 + i * 90, 900);
      ctx.stroke();
    }

    // Render 3D Village Houses Wireframe
    const houseAlpha = Math.min(1.0, localT * 0.3);
    ctx.strokeStyle = `rgba(0, 212, 255, ${houseAlpha})`;
    ctx.lineWidth = 2;
    ctx.strokeRect(550, 500, 180, 140);
    ctx.strokeRect(780, 480, 220, 160);

    // House Roof Pyramids
    ctx.beginPath();
    ctx.moveTo(550, 500); ctx.lineTo(640, 420); ctx.lineTo(730, 500);
    ctx.moveTo(780, 480); ctx.lineTo(890, 390); ctx.lineTo(1000, 480);
    ctx.stroke();

    // Right Test & Build Pipeline Panel
    ctx.fillStyle = 'rgba(15, 23, 42, 0.9)';
    ctx.roundRect(1250, 160, 550, 780, 8);
    ctx.fill();

    ctx.fillStyle = '#FFFFFF';
    ctx.font = '700 15px "Space Grotesk"';
    ctx.fillText('AUTOMATED BUILD & TEST SUITE', 1280, 200);

    const checks = [
      { name: 'GDScript Syntax Check', pass: true },
      { name: 'Blender FBX Mesh Import', pass: true },
      { name: 'PolyHaven Texture Atlas', pass: true },
      { name: 'Godot Physics Collider Generation', pass: true },
      { name: 'Lighting & Navigation Mesh Bake', pass: true },
      { name: 'Unit & Integration Tests (pytest)', pass: true }
    ];

    checks.forEach((chk, idx) => {
      const y = 250 + idx * 70;
      ctx.fillStyle = 'rgba(30, 41, 59, 0.8)';
      ctx.roundRect(1280, y, 490, 50, 6);
      ctx.fill();

      ctx.fillStyle = '#E5E7EB';
      ctx.font = '500 13px "Space Grotesk"';
      ctx.fillText(chk.name, 1300, y + 30);

      ctx.fillStyle = '#10B981';
      ctx.font = '700 13px "JetBrains Mono"';
      ctx.fillText('[PASSED ✓]', 1670, y + 30);
    });

    // Glowing Success Banner
    if (localT > 5.0) {
      ctx.fillStyle = 'rgba(16, 185, 129, 0.95)';
      ctx.roundRect(1280, 720, 490, 180, 8);
      ctx.fill();

      ctx.fillStyle = '#FFFFFF';
      ctx.font = '700 24px "Space Grotesk"';
      ctx.textAlign = 'center';
      ctx.fillText('BUILD SUCCESSFUL', 1525, 800);
      ctx.font = '500 14px "JetBrains Mono"';
      ctx.fillText('Game Binary Generated: medieval_village.x86_64', 1525, 840);
      ctx.textAlign = 'left';
    }
  }

  // Render Scene 7: The Ecosystem (75-85s)
  function renderScene7(t) {
    const localT = t - 75;
    ctx.fillStyle = '#05070C';
    ctx.fillRect(0, 0, 1920, 1080);

    // Ecosystem Tree Hierarchy
    ctx.fillStyle = '#00D4FF';
    ctx.font = '700 24px "Space Grotesk"';
    ctx.textAlign = 'center';
    ctx.fillText('AACHMAN STUDIOS ECOSYSTEM ARCHITECTURE', 960, 120);

    // Root Node
    ctx.fillStyle = 'rgba(91, 95, 255, 0.3)';
    ctx.strokeStyle = '#00D4FF';
    ctx.lineWidth = 2.5;
    ctx.roundRect(800, 180, 320, 80, 10);
    ctx.fill(); ctx.stroke();

    ctx.fillStyle = '#FFFFFF';
    ctx.font = '700 18px "Space Grotesk"';
    ctx.fillText('Aachman Studios', 960, 228);

    // Sub-nodes
    const branches = [
      { name: 'AppSuite', x: 260, y: 440 },
      { name: 'Jarvis AI Engine', x: 540, y: 440 },
      { name: 'GameDevAI Suite', x: 820, y: 440 },
      { name: 'PyFlare OS', x: 1100, y: 440 },
      { name: 'Developer Tools', x: 1380, y: 440 },
      { name: 'Future Ecosystem', x: 1660, y: 440 }
    ];

    branches.forEach(b => {
      ctx.strokeStyle = 'rgba(91, 95, 255, 0.4)';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(960, 260);
      ctx.lineTo(b.x, b.y);
      ctx.stroke();

      ctx.fillStyle = 'rgba(17, 24, 39, 0.9)';
      ctx.strokeStyle = '#8A5CF5';
      ctx.roundRect(b.x - 110, b.y - 35, 220, 70, 8);
      ctx.fill(); ctx.stroke();

      ctx.fillStyle = '#FFFFFF';
      ctx.font = '600 14px "Space Grotesk"';
      ctx.fillText(b.name, b.x, b.y + 7);
    });

    ctx.fillStyle = '#9CA3AF';
    ctx.font = '500 15px "Inter"';
    ctx.fillText('An actively engineered, developer-focused software ecosystem.', 960, 680);

    ctx.textAlign = 'left';
  }

  // Render Final Scene: Aachman Studios (85-90s)
  function renderFinalScene(t) {
    const localT = t - 85;
    ctx.fillStyle = '#040508';
    ctx.fillRect(0, 0, 1920, 1080);

    const fadeAlpha = localT > 3.5 ? Math.max(0.0, 1.0 - (localT - 3.5) / 1.5) : 1.0;

    // Draw Official Aachman Studios Logo
    drawAachmanLogo(ctx, 960, 420, 1.0, fadeAlpha);

    // Title
    ctx.save();
    ctx.globalAlpha = fadeAlpha;
    ctx.fillStyle = '#FFFFFF';
    ctx.font = '700 42px "Space Grotesk"';
    ctx.textAlign = 'center';
    ctx.letterSpacing = '4px';
    ctx.fillText('AACHMAN STUDIOS', 960, 720);

    // Tagline
    ctx.font = '400 18px "Inter"';
    ctx.fillStyle = '#00D4FF';
    ctx.fillText('"Building tools for the people who build the future."', 960, 780);
    ctx.restore();

    ctx.textAlign = 'left';
  }

  // Main Render Dispatcher Loop
  function render(now) {
    const delta = (now - lastFrameTime) / 1000;
    lastFrameTime = now;

    // FPS calculation
    frameCount++;
    if (now - lastFpsUpdate >= 1000) {
      fps = Math.round((frameCount * 1000) / (now - lastFpsUpdate));
      fpsDisplay.textContent = `${fps} FPS`;
      frameCount = 0;
      lastFpsUpdate = now;
    }

    if (isPlaying) {
      currentTime += delta * playbackRate;
      if (currentTime >= TOTAL_DURATION) {
        currentTime = TOTAL_DURATION;
        isPlaying = false;
        updatePlayButtonUI();
      }
    }

    // Determine Active Scene
    const currentScene = SCENES.find(s => currentTime >= s.start && currentTime < s.end) || SCENES[SCENES.length - 1];

    // Update UI HUD
    sceneBadge.textContent = currentScene.badge;
    sceneTitleActive.textContent = currentScene.title;
    timeDisplay.textContent = `${formatTime(currentTime)} / 01:30.0`;

    const progressPct = (currentTime / TOTAL_DURATION) * 100;
    timelineProgress.style.width = `${progressPct}%`;
    timelineScrubber.style.left = `${progressPct}%`;

    // Update Narration Subtitle Overlay
    const activeNarration = NARRATIONS.slice().reverse().find(n => currentTime >= n.time);
    if (activeNarration && subtitlesEnabled) {
      narrationContainer.style.opacity = '1';
      narrationText.textContent = activeNarration.text;
    } else {
      narrationContainer.style.opacity = '0';
    }

    // Canvas Clear
    ctx.clearRect(0, 0, 1920, 1080);

    // Render Active Scene
    if (currentTime < 10) renderScene1(currentTime);
    else if (currentTime < 20) renderScene2(currentTime);
    else if (currentTime < 35) renderScene3(currentTime);
    else if (currentTime < 47) renderScene4(currentTime);
    else if (currentTime < 62) renderScene5(currentTime);
    else if (currentTime < 75) renderScene6(currentTime);
    else if (currentTime < 85) renderScene7(currentTime);
    else renderFinalScene(currentTime);

    requestAnimationFrame(render);
  }

  // UI Event Handlers
  function updatePlayButtonUI() {
    if (isPlaying) {
      iconPlay.style.display = 'none';
      iconPause.style.display = 'block';
    } else {
      iconPlay.style.display = 'block';
      iconPause.style.display = 'none';
    }
  }

  btnPlay.addEventListener('click', () => {
    initAudio();
    isPlaying = !isPlaying;
    if (currentTime >= TOTAL_DURATION) currentTime = 0;
    updatePlayButtonUI();
    triggerBeep(600, 0.05);
  });

  btnRestart.addEventListener('click', () => {
    currentTime = 0;
    isPlaying = true;
    updatePlayButtonUI();
    triggerBeep(800, 0.05);
  });

  btnAudio.addEventListener('click', () => {
    audioEnabled = !audioEnabled;
    btnAudio.classList.toggle('active', audioEnabled);
    if (synthGain && audioCtx) {
      synthGain.gain.setValueAtTime(audioEnabled ? 0.08 : 0.001, audioCtx.currentTime);
    }
  });

  btnSubtitles.addEventListener('click', () => {
    subtitlesEnabled = !subtitlesEnabled;
    btnSubtitles.classList.toggle('active', subtitlesEnabled);
  });

  speedSelect.addEventListener('change', (e) => {
    playbackRate = parseFloat(e.target.value);
  });

  const btnExportMp4 = document.getElementById('btn-export-mp4');
  let mediaRecorder = null;
  let recordedChunks = [];

  if (btnExportMp4) {
    btnExportMp4.addEventListener('click', () => {
      if (mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop();
        btnExportMp4.querySelector('span').textContent = 'EXPORT MP4';
        return;
      }

      recordedChunks = [];
      const stream = canvas.captureStream(30); // 30 FPS canvas stream
      const options = { mimeType: 'video/webm;codecs=vp9' };
      
      try {
        mediaRecorder = new MediaRecorder(stream, options);
      } catch (e) {
        mediaRecorder = new MediaRecorder(stream);
      }

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) recordedChunks.push(e.data);
      };

      mediaRecorder.onstop = () => {
        const blob = new Blob(recordedChunks, { type: 'video/mp4' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'Aachman_Studios_Ecosystem_Trailer.mp4';
        a.click();
        URL.revokeObjectURL(url);
      };

      // Restart trailer and record full duration
      currentTime = 0;
      isPlaying = true;
      updatePlayButtonUI();
      mediaRecorder.start(100);
      btnExportMp4.querySelector('span').textContent = 'STOP & SAVE';
    });
  }

  btnFullscreen.addEventListener('click', () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(err => console.warn(err));
    } else {
      document.exitFullscreen().catch(err => console.warn(err));
    }
  });

  // Timeline Click / Scrubbing
  timelineBar.addEventListener('click', (e) => {
    const rect = timelineBar.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const pct = Math.max(0, Math.min(1, clickX / rect.width));
    currentTime = pct * TOTAL_DURATION;
    triggerBeep(500, 0.05);
  });

  // Scene Marker Jump Buttons
  markerButtons.forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const targetSec = parseFloat(btn.dataset.time);
      currentTime = targetSec;
      triggerBeep(700, 0.05);
    });
  });

  // Start Animation Loop
  requestAnimationFrame(render);
})();
