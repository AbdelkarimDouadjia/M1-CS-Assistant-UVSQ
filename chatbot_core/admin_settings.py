"""Admin-configurable runtime settings.

Stored as a JSON file under ``data/admin_settings.json`` so the chatbot and the
admin dashboard share the same configuration. Settings are loaded on every
request, which keeps changes from the dashboard live without restarting
Streamlit.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SETTINGS_PATH = PROJECT_ROOT / "data" / "admin_settings.json"


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_bool_any(names: tuple[str, ...], default: bool) -> bool:
    for name in names:
        value = os.getenv(name)
        if value is not None:
            return value.strip().lower() in {"1", "true", "yes", "on"}
    return default


def _env_int_any(names: tuple[str, ...], default: int) -> int:
    for name in names:
        value = os.getenv(name)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return default


def default_settings() -> dict[str, Any]:
    """Resolve defaults from environment so existing .env files keep working."""
    return {
        # Feature toggles
        "file_upload_enabled": True,
        "image_upload_enabled": True,
        "voice_input_enabled": True,
        "voice_output_enabled": True,
        "export_enabled": True,
        "memory_feature_enabled": True,
        "suggestions_enabled": True,
        # Model routing
        # active_backend = auto | gemini | vllm | fallback
        # auto = Gemini first, then optional OpenAI-compatible providers,
        # then the UVSQ/vLLM server as backup.
        "active_backend": os.getenv("ACTIVE_BACKEND", "auto"),
        "vllm_model": os.getenv("VLLM_MODEL", os.getenv("ANSWER_MODEL", "Qwen/Qwen3-30B-A3B")),
        "fallback_model": os.getenv("FALLBACK_MODEL", ""),
        "gemini_model": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        "vision_model": os.getenv("VISION_MODEL", "gemini-2.5-flash"),
        # Generation parameters
        "temperature": _env_float("GENERATION_TEMPERATURE", 0.1),
        "max_tokens": _env_int("GENERATION_MAX_TOKENS", 800),
        # Retrieval parameters
        "retrieval_top_k": _env_int("RETRIEVAL_TOP_K", 12),
        "final_context_k": _env_int("FINAL_CONTEXT_K", _env_int("RERANKER_TOP_K", 5)),
        "reranking_enabled": _env_bool("RERANKING_ENABLED", True),
        "query_expansion_enabled": _env_bool_any(("QUERY_EXPANSION_ENABLED", "RERASKER_ENABLED"), False),
        "query_expansion_max_variants": _env_int_any(("QUERY_EXPANSION_MAX_VARIANTS", "RERASKER_MAX_VARIANTS"), 3),
        # Limits
        "max_upload_chars": 12000,
    }


def load_settings() -> dict[str, Any]:
    """Return the merged admin settings, falling back to environment defaults."""
    base = default_settings()
    if not SETTINGS_PATH.exists():
        return base
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return base
    if not isinstance(data, dict):
        return base
    for key in base:
        if key in data:
            base[key] = data[key]
    return base


def save_settings(settings: dict[str, Any]) -> None:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    base = default_settings()
    merged = {key: settings.get(key, base[key]) for key in base}
    SETTINGS_PATH.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")


def reset_settings() -> dict[str, Any]:
    SETTINGS_PATH.unlink(missing_ok=True)
    return load_settings()


def get(key: str, default: Any = None) -> Any:
    return load_settings().get(key, default)
