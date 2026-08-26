"""Multi-provider LLM client for LUNA chat.

Supports:
- gemini (Google GenAI) — existing default
- openai_compatible — Groq / OpenRouter / Ollama / LM Studio / any OpenAI API

Env:
  LLM_PROVIDER=gemini|openai_compatible|groq|ollama|openrouter
  MODEL_NAME=...
  GOOGLE_API_KEY=...          (gemini)
  OPENAI_API_KEY=...          (openai-compatible)
  OPENAI_BASE_URL=...         (default depends on provider)
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import requests

from dotenv import load_dotenv

load_dotenv()

LLM_PROVIDER = (os.getenv("LLM_PROVIDER") or "gemini").strip().lower()
MODEL_NAME = os.getenv("MODEL_NAME") or "gemini-2.5-flash"

_gemini_client = None


def provider_name() -> str:
    if LLM_PROVIDER in ("groq", "ollama", "openrouter", "openai", "lmstudio"):
        return "openai_compatible"
    return LLM_PROVIDER or "gemini"


def _openai_base_url() -> str:
    explicit = (os.getenv("OPENAI_BASE_URL") or "").strip().rstrip("/")
    if explicit:
        return explicit
    if LLM_PROVIDER == "groq":
        return "https://api.groq.com/openai/v1"
    if LLM_PROVIDER == "openrouter":
        return "https://openrouter.ai/api/v1"
    if LLM_PROVIDER in ("ollama", "lmstudio"):
        return "http://127.0.0.1:11434/v1"
    return "https://api.openai.com/v1"


def _openai_api_key() -> str:
    key = (os.getenv("OPENAI_API_KEY") or os.getenv("GROQ_API_KEY") or "").strip()
    if key:
        return key
    if LLM_PROVIDER in ("ollama", "lmstudio"):
        return "ollama"
    return ""


def _default_model_for_provider() -> str:
    env_model = (os.getenv("MODEL_NAME") or "").strip()
    if env_model and not (
        LLM_PROVIDER in ("groq", "ollama", "openrouter") and env_model.startswith("gemini")
    ):
        return env_model
    if LLM_PROVIDER == "groq":
        return "llama-3.1-8b-instant"
    if LLM_PROVIDER == "ollama":
        return "qwen2.5:7b"
    if LLM_PROVIDER == "openrouter":
        return "openai/gpt-4o-mini"
    return env_model or "gemini-2.5-flash"


def _get_gemini():
    global _gemini_client
    if _gemini_client is not None:
        return _gemini_client
    api_key = (os.getenv("GOOGLE_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("Missing GOOGLE_API_KEY for gemini provider")
    from google import genai

    _gemini_client = genai.Client(api_key=api_key)
    return _gemini_client


def history_to_openai_messages(
    system_prompt: str,
    history: List[Dict[str, str]],
    user_text: str,
    *,
    limit: int = 6,
) -> List[Dict[str, str]]:
    msgs: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
    for turn in history[-limit:]:
        role = "user" if turn.get("role") == "user" else "assistant"
        content = turn.get("content") or ""
        # Prefer plain dialogue if packed
        if "<dialogue>" in content:
            import re

            m = re.search(r"<dialogue>\s*(.*?)\s*</dialogue>", content, re.DOTALL | re.I)
            if m:
                content = m.group(1).strip()
        if content:
            msgs.append({"role": role, "content": content})
    msgs.append({"role": "user", "content": user_text})
    return msgs


def chat_openai_compatible(
    system_prompt: str,
    history: List[Dict[str, str]],
    user_text: str,
    *,
    temperature: float = 0.6,
    max_tokens: int = 180,
) -> str:
    key = _openai_api_key()
    if not key and LLM_PROVIDER not in ("ollama", "lmstudio"):
        raise RuntimeError("Missing OPENAI_API_KEY / GROQ_API_KEY")
    url = _openai_base_url() + "/chat/completions"
    model = _default_model_for_provider()
    payload = {
        "model": model,
        "messages": history_to_openai_messages(system_prompt, history, user_text),
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {key or 'ollama'}",
        "Content-Type": "application/json",
    }
    if LLM_PROVIDER == "openrouter":
        headers["HTTP-Referer"] = os.getenv("APP_BASE_URL", "http://localhost")
        headers["X-Title"] = "LUNA-FSQ"
    res = requests.post(url, json=payload, headers=headers, timeout=60)
    if res.status_code >= 400:
        raise RuntimeError(f"LLM HTTP {res.status_code}: {res.text[:400]}")
    data = res.json()
    try:
        return (data["choices"][0]["message"]["content"] or "").strip()
    except Exception as exc:
        raise RuntimeError(f"Bad LLM response: {data!r}") from exc


def chat_gemini(
    system_prompt: str,
    history_contents: list,
    user_text: str,
    *,
    temperature: float = 0.6,
    max_output_tokens: int = 180,
) -> str:
    from google.genai import types

    client = _get_gemini()
    model = (os.getenv("MODEL_NAME") or "gemini-2.5-flash").strip()
    chat_session = client.chats.create(
        model=model,
        history=history_contents,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        ),
    )
    response = chat_session.send_message(user_text)
    return (response.text or "").strip()


def complete_chat(
    system_prompt: str,
    *,
    history_dicts: List[Dict[str, str]],
    history_contents: Optional[list] = None,
    user_text: str,
    temperature: float = 0.6,
    max_tokens: int = 180,
) -> str:
    """Route to configured provider. history_contents used only for gemini."""
    mode = provider_name()
    if mode == "openai_compatible":
        return chat_openai_compatible(
            system_prompt,
            history_dicts,
            user_text,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    return chat_gemini(
        system_prompt,
        history_contents or [],
        user_text,
        temperature=temperature,
        max_output_tokens=max_tokens,
    )


def active_backend_label() -> Dict[str, Any]:
    mode = provider_name()
    return {
        "provider": LLM_PROVIDER,
        "mode": mode,
        "model": _default_model_for_provider() if mode == "openai_compatible" else (os.getenv("MODEL_NAME") or "gemini-2.5-flash"),
        "base_url": _openai_base_url() if mode == "openai_compatible" else None,
    }
