"""Route generation requests to Ollama (local) or Gemini (cloud).

Supports difficulty-based model selection:
  easy/medium → chat model (fast)
  hard → heavy model (better reasoning)
"""
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from enum import StrEnum

import httpx
import structlog

from app.config import settings
from app.core.generation.prompt_builder import BuiltPrompt
from app.exceptions import LLMUnavailableError

logger = structlog.get_logger(__name__)


class LLMBackend(StrEnum):
    OLLAMA = "ollama"
    GEMINI = "gemini"


# Friendly display names for raw model identifiers
_DISPLAY_NAMES: dict[str, str] = {
    "gemini-1.5-flash": "Gemini 1.5 Flash",
    "gemini-1.5-pro": "Gemini 1.5 Pro",
    "gemini-2.0-flash": "Gemini 2.0 Flash",
    "gemini-2.5-flash": "Gemini 2.5 Flash",
    "gemini-2.5-pro": "Gemini 2.5 Pro",
}


def _friendly_name(raw_model: str) -> str:
    """Convert raw model id to human-friendly name."""
    if raw_model in _DISPLAY_NAMES:
        return _DISPLAY_NAMES[raw_model]
    # hf.co/MaziyarPanahi/gemma-2-2b-it-GGUF:Q8_0 → Gemma 2 2B (Q8_0)
    if "/" in raw_model:
        parts = raw_model.rsplit("/", 1)[-1]  # gemma-2-2b-it-GGUF:Q8_0
        name, _, quant = parts.partition(":")
        name = name.replace("-GGUF", "").replace("-gguf", "")
        # Title-case with hyphens → spaces
        name = name.replace("-", " ").title()
        if quant:
            return f"{name} ({quant})"
        return name
    return raw_model


@dataclass
class ModelChoice:
    """Result of model selection."""
    backend: LLMBackend
    model_id: str        # raw id sent to API
    display_name: str    # human-friendly name for UI


def choose_model(difficulty: str = "medium") -> ModelChoice:
    """
    Select LLM backend + model based on query difficulty.

    Routing:
        FORCE_LLM_BACKEND=gemini → always Gemini
        FORCE_LLM_BACKEND=ollama (or auto):
            easy/medium → ollama_chat_model
            hard        → ollama_heavy_model (fallback to chat_model)
    """
    # Gemini forced
    if settings.force_llm_backend == "gemini" and settings.gemini_api_key:
        return ModelChoice(
            backend=LLMBackend.GEMINI,
            model_id=settings.gemini_model,
            display_name=_friendly_name(settings.gemini_model),
        )

    # Ollama: difficulty-based routing
    if difficulty == "hard" and settings.ollama_heavy_model:
        model_id = settings.ollama_heavy_model
    else:
        model_id = settings.ollama_chat_model

    return ModelChoice(
        backend=LLMBackend.OLLAMA,
        model_id=model_id,
        display_name=_friendly_name(model_id),
    )


def choose_backend(mode: str) -> LLMBackend:
    """Legacy compat — returns backend only."""
    return choose_model().backend


async def stream_generate(
    prompt: BuiltPrompt,
    mode: str = "strict",
    model_choice: ModelChoice | None = None,
) -> AsyncGenerator[str, None]:
    """Yield token strings from the chosen LLM backend."""
    if model_choice is None:
        model_choice = choose_model()

    if model_choice.backend == LLMBackend.OLLAMA:
        async for token in _stream_ollama(prompt, model_choice.model_id):
            yield token
    else:
        async for token in _stream_gemini(prompt):
            yield token


async def _stream_ollama(prompt: BuiltPrompt, model_id: str | None = None) -> AsyncGenerator[str, None]:
    import json

    model = model_id or settings.ollama_chat_model
    ollama_messages = [{"role": "system", "content": prompt.system}] + prompt.messages

    payload = {
        "model": model,
        "messages": ollama_messages,
        "stream": True,
        "options": {"temperature": 0.1, "num_predict": 512},
    }

    try:
        async with httpx.AsyncClient(timeout=settings.ollama_timeout) as client:
            async with client.stream(
                "POST",
                f"{settings.ollama_base_url}/api/chat",
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    content = data.get("message", {}).get("content", "")
                    if content:
                        yield content
                    if data.get("done"):
                        break
    except httpx.HTTPStatusError as exc:
        raise LLMUnavailableError(f"Ollama chat failed: {exc}") from exc
    except httpx.RequestError as exc:
        raise LLMUnavailableError(f"Cannot reach Ollama: {exc}") from exc


async def _stream_gemini(prompt: BuiltPrompt) -> AsyncGenerator[str, None]:
    """Gemini API streaming — Phase 2+."""
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.gemini_api_key)
        user_text = prompt.messages[-1]["content"] if prompt.messages else ""
        history_parts = [
            types.Content(role=m["role"], parts=[types.Part(text=m["content"])])
            for m in prompt.messages[:-1]
        ]
        async for chunk in await client.aio.models.generate_content_stream(
            model=settings.gemini_model,
            contents=history_parts + [types.Content(role="user", parts=[types.Part(text=user_text)])],
            config=types.GenerateContentConfig(system_instruction=prompt.system),
        ):
            if chunk.text:
                yield chunk.text
    except Exception as exc:
        raise LLMUnavailableError(f"Gemini failed: {exc}") from exc
