"""
Sondes réseau pour les backends LLM (aucune clé dans le code source).

Usage (depuis la racine du projet) :
  .\\.venv\\Scripts\\python.exe -m tests.test_llm_backends

Avec une clé dans .env uniquement, teste aussi un appel chat minimal par passerelle.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

from chatbot_core.llm_backends import resolve_compat_model_names

PROJECT_ROOT = Path(__file__).resolve().parents[1]

load_dotenv(PROJECT_ROOT / ".env")


def probe_get(url: str, timeout: float = 5.0) -> tuple[int, str]:
    try:
        r = requests.get(url, timeout=timeout)
        return r.status_code, (r.text or "")[:200]
    except requests.RequestException as e:
        return -1, str(e)


def probe_openai_chat(base: str, api_key: str, model: str, timeout: float = 30.0) -> tuple[int, str]:
    url = base.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 8,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=timeout)
        return r.status_code, (r.text or "")[:300]
    except requests.RequestException as e:
        return -1, str(e)


def _probe_compat_block(label: str, base: str, key: str, models: list[str]) -> None:
    base = base.strip().rstrip("/")
    if not base:
        print(f"{label}: URL non définie\n")
        return
    code, snippet = probe_get(f"{base}/models")
    print(f"{label} GET {base}/models -> HTTP {code}")
    print(f"  détail: {snippet!r}\n")
    if not key:
        print(f"{label}: clé absente, pas de POST chat.\n")
        return
    if not models:
        models = ["deepseek-chat"]
    for m in models[:5]:
        c2, s2 = probe_openai_chat(base, key, m)
        print(f"{label} POST chat (model={m}) -> HTTP {c2}")
        print(f"  détail: {s2!r}")
        if c2 == 200:
            print(f"  -> premier modèle OK: {m}\n")
            return
    print()


def main() -> int:
    vllm_base = (os.getenv("VLLM_BASE_URL") or os.getenv("VLLM_API_BASE") or "").strip().rstrip("/")
    rr_base = (os.getenv("RERANKER_API_BASE") or "").strip().rstrip("/")
    oc_base = os.getenv("OPENAI_COMPAT_BASE_URL", "").strip().rstrip("/")
    oc_key = os.getenv("OPENAI_COMPAT_API_KEY", "").strip()
    oc_models = resolve_compat_model_names() or [os.getenv("OPENAI_COMPAT_MODEL", "deepseek-chat").strip() or "deepseek-chat"]

    oc2_base = os.getenv("OPENAI_COMPAT2_BASE_URL", "").strip().rstrip("/")
    oc2_key = os.getenv("OPENAI_COMPAT2_API_KEY", "").strip()
    raw2 = os.getenv("OPENAI_COMPAT2_MODELS", "").strip()
    oc2_models = [p.strip() for p in raw2.split(",") if p.strip()] if raw2 else oc_models

    print("=== Probes LLM (chatbot_M1_AMIS) ===\n")

    if vllm_base:
        code, snippet = probe_get(f"{vllm_base}/models")
        print(f"vLLM GET {vllm_base}/models -> HTTP {code}")
        if code != 200:
            print(f"  détail: {snippet!r}\n")
        else:
            print("  OK\n")
    else:
        print("vLLM: VLLM_BASE_URL / VLLM_API_BASE non défini\n")

    if rr_base:
        code, snippet = probe_get(f"{rr_base}/health")
        print(f"Reranker GET {rr_base}/health -> HTTP {code}")
        print(f"  détail: {snippet!r}\n")
    else:
        print("Reranker: RERANKER_API_BASE non défini\n")

    _probe_compat_block("OpenAI-compat (1)", oc_base, oc_key, oc_models)
    _probe_compat_block("OpenAI-compat (2)", oc2_base, oc2_key, oc2_models)

    return 0


if __name__ == "__main__":
    sys.exit(main())
