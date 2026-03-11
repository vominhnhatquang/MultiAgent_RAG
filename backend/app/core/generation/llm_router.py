"""Route generation requests to Ollama (local) or Gemini (cloud)."""
from collections.abc import AsyncGenerator
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


def choose_backend(mode: str) -> LLMBackend:
    """
    Phase 1: defaults to Ollama.
    Override via FORCE_LLM_BACKEND env var for testing:
      FORCE_LLM_BACKEND=gemini  → Gemini API (requires GEMINI_API_KEY)
      FORCE_LLM_BACKEND=ollama  → Ollama (default)
    """
    if settings.force_llm_backend == "gemini" and settings.gemini_api_key:
        return LLMBackend.GEMINI
    return LLMBackend.OLLAMA


async def stream_generate(
    prompt: BuiltPrompt,
    mode: str = "strict",
) -> AsyncGenerator[str, None]:
    """Yield token strings from the chosen LLM backend."""
    backend = choose_backend(mode)
    if backend == LLMBackend.OLLAMA:
        async for token in _stream_ollama(prompt):
            yield token
    else:
        async for token in _stream_gemini(prompt):
            yield token


async def _stream_ollama(prompt: BuiltPrompt) -> AsyncGenerator[str, None]:
    import json

    # Convert prompt.messages to Ollama chat format
    ollama_messages = [{"role": "system", "content": prompt.system}] + prompt.messages

    payload = {
        "model": settings.ollama_chat_model,
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
