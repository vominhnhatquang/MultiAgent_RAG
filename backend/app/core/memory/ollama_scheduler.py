"""Ollama model scheduler for RAM management."""
import asyncio

import httpx
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)


class OllamaScheduler:
    """
    Manage Ollama model loading/unloading based on RAM budget.

    Models:
        - nomic-embed-text (0.3GB): ALWAYS loaded
        - gemma2:2b (1.6GB): DEFAULT loaded for chat
        - llama3.1:8b (4.7GB): ON-DEMAND, unload gemma2 first
        - bge-reranker-v2: Runs in Python process, not Ollama

    Rules:
        - Only 1 chat model active at a time
        - Load llama3.1 → must unload gemma2 first
        - After using llama3.1 → unload and reload gemma2
    """

    EMBED_MODEL = "nomic-embed-text"
    DEFAULT_CHAT_MODEL = "gemma2:2b"
    HEAVY_CHAT_MODEL = "llama3.1:8b"

    # Redis keys for tracking
    MODEL_STATUS_KEY = "ollama:model_status"

    def __init__(self) -> None:
        self.timeout = httpx.Timeout(120.0)

    async def get_loaded_models(self) -> list[str]:
        """Get list of currently loaded models from Ollama."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(f"{settings.ollama_base_url}/api/ps")
                resp.raise_for_status()
                data = resp.json()
                models = [m["model"] for m in data.get("models", [])]
                return models
        except Exception as e:
            logger.warning("ollama.get_loaded_failed", error=str(e))
            return []

    async def ensure_model(self, model_name: str) -> bool:
        """
        Ensure a model is loaded and ready.

        Args:
            model_name: Model to ensure is loaded

        Returns:
            True if model is ready, False on error
        """
        loaded = await self.get_loaded_models()

        if model_name in loaded:
            logger.debug("ollama.model_already_loaded", model=model_name)
            return True

        # If loading heavy model, unload default first
        if model_name == self.HEAVY_CHAT_MODEL and self.DEFAULT_CHAT_MODEL in loaded:
            logger.info("ollama.unloading_for_heavy", unload=self.DEFAULT_CHAT_MODEL)
            await self.unload_model(self.DEFAULT_CHAT_MODEL)
            await asyncio.sleep(2)  # Wait for RAM to free

        # Load the model by sending a warmup request
        return await self._warmup_model(model_name)

    async def _warmup_model(self, model_name: str) -> bool:
        """Warmup a model by sending a minimal request."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{settings.ollama_base_url}/api/generate",
                    json={
                        "model": model_name,
                        "prompt": "warmup",
                        "stream": False,
                        "options": {"num_predict": 1},
                    },
                )
                resp.raise_for_status()
                logger.info("ollama.model_warmed", model=model_name)
                return True
        except Exception as e:
            logger.error("ollama.warmup_failed", model=model_name, error=str(e))
            return False

    async def unload_model(self, model_name: str) -> bool:
        """
        Unload a model from Ollama.

        Note: Ollama automatically unloads after keep_alive expires,
        but we can force unload by setting keep_alive=0.
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Send request with keep_alive=0 to trigger unload
                resp = await client.post(
                    f"{settings.ollama_base_url}/api/generate",
                    json={
                        "model": model_name,
                        "prompt": "",
                        "stream": False,
                        "keep_alive": 0,  # Trigger unload
                    },
                )
                resp.raise_for_status()
                logger.info("ollama.model_unloaded", model=model_name)
                return True
        except Exception as e:
            logger.warning("ollama.unload_failed", model=model_name, error=str(e))
            return False

    async def release_heavy_model(self) -> None:
        """Release heavy model and restore default chat model."""
        loaded = await self.get_loaded_models()

        if self.HEAVY_CHAT_MODEL in loaded:
            await self.unload_model(self.HEAVY_CHAT_MODEL)
            await asyncio.sleep(2)  # Wait for RAM to free

        # Reload default chat model
        await self.ensure_model(self.DEFAULT_CHAT_MODEL)
        logger.info("ollama.restored_default")

    async def get_memory_usage(self) -> dict:
        """Get Ollama memory usage stats."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(f"{settings.ollama_base_url}/api/ps")
                resp.raise_for_status()
                data = resp.json()

                total_size = 0
                models = []
                for m in data.get("models", []):
                    size_gb = m.get("size", 0) / (1024**3)
                    total_size += size_gb
                    models.append({
                        "name": m["model"],
                        "size_gb": round(size_gb, 2),
                    })

                return {
                    "models": models,
                    "total_size_gb": round(total_size, 2),
                }
        except Exception as e:
            logger.warning("ollama.memory_stats_failed", error=str(e))
            return {"error": str(e)}

    async def healthcheck(self) -> bool:
        """Check if Ollama is responsive."""
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                resp = await client.get(f"{settings.ollama_base_url}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False


# Global instance
_scheduler: OllamaScheduler | None = None


def get_ollama_scheduler() -> OllamaScheduler:
    """Get the global Ollama scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = OllamaScheduler()
    return _scheduler
