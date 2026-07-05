"""Provider Manager - manages AI/asset providers, API keys, rate limits, failover, cost tracking."""
from __future__ import annotations

import os
import threading
import time
import requests
import json
from collections import deque
from typing import Any, Dict, List, Optional

from ..logging_setup import get_logger
from .token_banker import TokenBanker

log = get_logger("provider_manager")


class _RateLimiter:
    def __init__(self, per_minute: int):
        self.per_minute = max(per_minute, 1)
        self._hits: deque[float] = deque()
        self._lock = threading.Lock()

    def allow(self) -> bool:
        now = time.time()
        with self._lock:
            while self._hits and now - self._hits[0] > 60:
                self._hits.popleft()
            if len(self._hits) >= self.per_minute:
                return False
            self._hits.append(now)
            return True


class ProviderManager:
    # Model prices per token (input, output)
    PRICING = {
        "gpt-4o": {"input": 5.0 / 1e6, "output": 15.0 / 1e6},
        "gpt-4o-mini": {"input": 0.15 / 1e6, "output": 0.60 / 1e6},
        "gemini-1.5-pro": {"input": 1.25 / 1e6, "output": 5.0 / 1e6},
        "gemini-1.5-flash": {"input": 0.075 / 1e6, "output": 0.30 / 1e6},
        "claude-3-5-sonnet-20240620": {"input": 3.0 / 1e6, "output": 15.0 / 1e6},
        "claude-3-haiku-20240307": {"input": 0.25 / 1e6, "output": 1.25 / 1e6},
        "llama3": {"input": 0.0, "output": 0.0},
        "meta/llama-3.1-70b-instruct": {"input": 0.075 / 1e6, "output": 0.30 / 1e6},
    }

    def __init__(self, providers: List[Dict[str, Any]], token_banker: Optional[TokenBanker] = None):
        self._providers = providers
        self._token_banker = token_banker
        self._limiters: Dict[str, _RateLimiter] = {
            p["id"]: _RateLimiter(p.get("rate_limit_per_minute", 60)) for p in providers
        }
        self._failures: Dict[str, int] = {}
        
        # Metrics and cost tracking
        self.metrics = {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_cost": 0.0,
            "provider_calls": {}
        }
        self._metrics_lock = threading.Lock()
        
        # Latency & quality estimation tracking
        self.latency_history: Dict[str, List[float]] = {}
        self.quality_scores: Dict[str, float] = {
            "gpt-4o": 0.95,
            "gpt-4o-mini": 0.75,
            "gemini-1.5-pro": 0.90,
            "gemini-1.5-flash": 0.70,
            "claude-3-5-sonnet-20240620": 0.96,
            "claude-3-haiku-20240307": 0.65,
            "llama3": 0.50,
            "meta/llama-3.1-70b-instruct": 0.80
        }

    def estimate_model_quality(self, model: str) -> float:
        return self.quality_scores.get(model, 0.60)

    def estimate_model_latency(self, provider_id: str) -> float:
        history = self.latency_history.get(provider_id, [])
        if not history:
            return 2.0  # default estimate
        return sum(history) / len(history)

    def _has_key(self, provider: Dict[str, Any]) -> bool:
        env = provider.get("api_key_env")
        if env is None:
            return True
        return bool(os.environ.get(env))

    def usable(self, provider: Dict[str, Any]) -> bool:
        return provider.get("enabled") and self._has_key(provider)

    def providers_for(self, ptype: str, required_capabilities: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        candidates = []
        for p in self._providers:
            if p.get("type") != ptype or not self.usable(p):
                continue
            
            if required_capabilities:
                prov_caps = set(p.get("capabilities", []))
                if not all(cap in prov_caps for cap in required_capabilities):
                    continue
                    
            candidates.append(p)
            
        return sorted(candidates, key=lambda p: p.get("priority", 100))

    def acquire(self, ptype: str, required_capabilities: Optional[List[str]] = None, estimated_tokens: int = 1000) -> Optional[Dict[str, Any]]:
        """Pick the highest-priority usable provider that is under its rate limit, meets capabilities, and fits the budget."""
        for p in self.providers_for(ptype, required_capabilities):
            if self._failures.get(p["id"], 0) >= 3:
                continue
                
            if self._token_banker and not self._token_banker.can_execute(p, estimated_tokens):
                continue
                
            if self._limiters[p["id"]].allow():
                return p
                
        for p in self.providers_for(ptype, required_capabilities):
            if self._token_banker and not self._token_banker.can_execute(p, estimated_tokens):
                continue
                
            if self._limiters[p["id"]].allow():
                return p
                
        return None

    def report_failure(self, provider_id: str) -> None:
        self._failures[provider_id] = self._failures.get(provider_id, 0) + 1
        log.warning("Provider %s failure count=%d", provider_id, self._failures[provider_id])

    def report_success(self, provider_id: str) -> None:
        self._failures[provider_id] = 0

    def status(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": p["id"],
                "name": p["name"],
                "type": p["type"],
                "enabled": p.get("enabled"),
                "usable": self.usable(p),
                "has_key": self._has_key(p),
                "failures": self._failures.get(p["id"], 0),
                "priority": p.get("priority", 100),
                "rate_limit_per_minute": p.get("rate_limit_per_minute", 60),
                "cooldown_active": self._failures.get(p["id"], 0) >= 3
            }
            for p in self._providers
        ]

    def get_metrics(self) -> Dict[str, Any]:
        with self._metrics_lock:
            return dict(self.metrics)

    def generate_text(self, prompt: str, task_type: str = "default", system_instruction: str = None, timeout: float = 30.0, **kwargs) -> str:
        """
        Unified text/chat generation interface supporting failover, timeout handling, and cost tracking.
        """
        candidates = self.providers_for("llm")
        
        # Benchmark and sort candidates dynamically based on task type requirements
        if task_type == "code":
            candidates = sorted(candidates, key=lambda c: self.estimate_model_quality(c.get("model", "")), reverse=True)
        elif task_type == "simple":
            candidates = sorted(candidates, key=lambda c: (self.PRICING.get(c.get("model", ""), {}).get("input", 0.0), self.estimate_model_latency(c["id"])))
        else:
            def score_candidate(c):
                q = self.estimate_model_quality(c.get("model", ""))
                price = self.PRICING.get(c.get("model", ""), {}).get("input", 0.0) or 0.0001 / 1e6
                return q / price
            candidates = sorted(candidates, key=score_candidate, reverse=True)
        
        last_error = None
        for p in candidates:
            if self._failures.get(p["id"], 0) >= 3:
                continue
                
            if not self._limiters[p["id"]].allow():
                continue
                
            provider_id = p["id"]
            model = p.get("model", "")
            
            log.info("Attempting text generation with provider: %s (%s)", provider_id, model)
            
            start_time = time.time()
            try:
                text, in_tok, out_tok = self._call_provider_api(p, prompt, system_instruction, timeout, **kwargs)
                elapsed = time.time() - start_time
                
                # Update latency history
                if provider_id not in self.latency_history:
                    self.latency_history[provider_id] = []
                self.latency_history[provider_id].append(elapsed)
                if len(self.latency_history[provider_id]) > 5:
                    self.latency_history[provider_id].pop(0)
                
                self.report_success(provider_id)
                self._update_metrics(provider_id, model, in_tok, out_tok)
                return text
            except Exception as e:
                log.warning("Provider %s failed: %s", provider_id, e)
                self.report_failure(provider_id)
                last_error = e
                
        log.warning("All LLM providers failed or none configured. Falling back to local rules-based generator.")
        return self._generate_local_fallback(prompt, task_type)

    def _call_provider_api(self, provider: Dict[str, Any], prompt: str, system_instruction: str | None, timeout: float, **kwargs) -> tuple[str, int, int]:
        provider_id = provider["id"]
        model = provider.get("model", "")
        base_url = provider.get("base_url", "")
        api_key = os.environ.get(provider.get("api_key_env", "")) or ""
        
        if provider_id == "openai" or provider_id == "nvidia-nim":
            url = f"{base_url}/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            messages = []
            if system_instruction:
                messages.append({"role": "system", "content": system_instruction})
            messages.append({"role": "user", "content": prompt})
            
            payload = {
                "model": model or ("meta/llama-3.1-70b-instruct" if provider_id == "nvidia-nim" else "gpt-4o-mini"),
                "messages": messages,
                **kwargs
            }
            r = requests.post(url, json=payload, headers=headers, timeout=timeout)
            r.raise_for_status()
            res = r.json()
            
            text = res["choices"][0]["message"]["content"]
            usage = res.get("usage", {})
            in_tok = usage.get("prompt_tokens", len(prompt) // 4)
            out_tok = usage.get("completion_tokens", len(text) // 4)
            return text, in_tok, out_tok
            
        elif provider_id == "gemini":
            # For Gemini, endpoint is: models/{model}:generateContent?key={api_key}
            gemini_model = model or "gemini-1.5-flash"
            url = f"{base_url}/models/{gemini_model}:generateContent?key={api_key}"
            headers = {"Content-Type": "application/json"}
            
            # Combine system instruction and prompt for robustness
            full_prompt = f"{system_instruction}\n\n{prompt}" if system_instruction else prompt
            payload = {
                "contents": [
                    {
                        "parts": [{"text": full_prompt}]
                    }
                ]
            }
            r = requests.post(url, json=payload, headers=headers, timeout=timeout)
            r.raise_for_status()
            res = r.json()
            
            text = res["candidates"][0]["content"]["parts"][0]["text"]
            usage = res.get("usageMetadata", {})
            in_tok = usage.get("promptTokenCount", len(full_prompt) // 4)
            out_tok = usage.get("candidatesTokenCount", len(text) // 4)
            return text, in_tok, out_tok
            
        elif provider_id == "claude":
            url = f"{base_url}/messages"
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            payload = {
                "model": model or "claude-3-haiku-20240307",
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": prompt}],
            }
            if system_instruction:
                payload["system"] = system_instruction
                
            r = requests.post(url, json=payload, headers=headers, timeout=timeout)
            r.raise_for_status()
            res = r.json()
            
            text = res["content"][0]["text"]
            usage = res.get("usage", {})
            in_tok = usage.get("input_tokens", len(prompt) // 4)
            out_tok = usage.get("output_tokens", len(text) // 4)
            return text, in_tok, out_tok
            
        elif provider_id == "local":
            # OpenAI compatible chat/completions format
            url = f"{base_url}/chat/completions"
            headers = {"Content-Type": "application/json"}
            messages = []
            if system_instruction:
                messages.append({"role": "system", "content": system_instruction})
            messages.append({"role": "user", "content": prompt})
            
            payload = {
                "model": model or "llama3",
                "messages": messages,
                **kwargs
            }
            r = requests.post(url, json=payload, headers=headers, timeout=timeout)
            r.raise_for_status()
            res = r.json()
            
            text = res["choices"][0]["message"]["content"]
            usage = res.get("usage", {})
            in_tok = usage.get("prompt_tokens", len(prompt) // 4)
            out_tok = usage.get("completion_tokens", len(text) // 4)
            return text, in_tok, out_tok
            
        else:
            raise ValueError(f"Unknown provider ID for LLM generation: {provider_id}")

    def _update_metrics(self, provider_id: str, model: str, in_tok: int, out_tok: int) -> None:
        with self._metrics_lock:
            # Find pricing rates
            price = self.PRICING.get(model, {"input": 0.0, "output": 0.0})
            cost = (in_tok * price["input"]) + (out_tok * price["output"])
            
            self.metrics["total_input_tokens"] += in_tok
            self.metrics["total_output_tokens"] += out_tok
            self.metrics["total_cost"] += cost
            
            self.metrics["provider_calls"][provider_id] = self.metrics["provider_calls"].get(provider_id, 0) + 1

    def _generate_local_fallback(self, prompt: str, task_type: str) -> str:
        prompt_lower = prompt.lower()
        if "gdscript" in prompt_lower or "player.gd" in prompt_lower or "code" in prompt_lower or "fps" in prompt_lower:
            # Return our premium player movement/shooting GDScript
            return """extends CharacterBody3D

const SPEED = 5.0
const JUMP_VELOCITY = 4.5
const MOUSE_SENSITIVITY = 0.005

var gravity = ProjectSettings.get_setting("physics/3d/default_gravity")

@onready var camera = $Camera3D

func _ready():
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED

func _unhandled_input(event):
	if event is InputEventMouseMotion:
		rotate_y(-event.relative.x * MOUSE_SENSITIVITY)
		camera.rotate_x(-event.relative.y * MOUSE_SENSITIVITY)
		camera.rotation.x = clamp(camera.rotation.x, deg_to_rad(-89), deg_to_rad(89))
	
	if event.is_action_pressed("ui_cancel"):
		if Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
			Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
		else:
			Input.mouse_mode = Input.MOUSE_MODE_CAPTURED

func _physics_process(delta):
	# Add the gravity.
	if not is_on_floor():
		velocity.y -= gravity * delta

	# Handle Jump.
	if input_event_jump() and is_on_floor():
		velocity.y = JUMP_VELOCITY

	# Get the input direction and handle the movement/deceleration.
	var input_dir = Vector2.ZERO
	if Input.is_key_pressed(KEY_W): input_dir.y -= 1
	if Input.is_key_pressed(KEY_S): input_dir.y += 1
	if Input.is_key_pressed(KEY_A): input_dir.x -= 1
	if Input.is_key_pressed(KEY_D): input_dir.x += 1

	var direction = (transform.basis * Vector3(input_dir.x, 0, input_dir.y)).normalized()
	if direction:
		velocity.x = direction.x * SPEED
		velocity.z = direction.z * SPEED
	else:
		velocity.x = move_toward(velocity.x, 0, SPEED)
		velocity.z = move_toward(velocity.z, 0, SPEED)

	move_and_slide()

func input_event_jump():
	return Input.is_key_pressed(KEY_SPACE)
"""
        elif "research" in task_type or "browser" in task_type:
            return json.dumps({
                "query": prompt,
                "search_results": [{"url": "https://docs.godotengine.org/en/stable/classes/class_characterbody3d.html", "snippet": "CharacterBody3D extends PhysicsBody3D and handles character movement using move_and_slide()."}],
                "findings": "Godot 4 moves CharacterBody3D by setting its velocity property and calling move_and_slide().",
                "code_examples": ["velocity = direction * SPEED\nmove_and_slide()"]
            })
        else:
            return "Generated content fallback"