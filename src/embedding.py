"""Embedding API client for xaihi memory system."""
import os
from typing import Any

import requests

try:
    from .config import config
except ImportError:
    from config import config


class EmbeddingClient:
    """OpenAI-compatible embedding client."""

    def __init__(self) -> None:
        cfg = config.get_embedding()
        self.model = cfg.get("model", "text-embedding-v4")
        self.base_url = cfg.get("base_url", "https://api.openai.com/v1")
        self.dimension = cfg.get("dimension", 1536)

        # Priority: config file > environment variable > Codex auth
        self.api_key = cfg.get("api_key") or os.environ.get(cfg.get("api_key_env", "OPENAI_API_KEY"))

        if not self.api_key:
            try:
                import json
                with open(os.path.expanduser("~/.codex/auth.json"), "r") as f:
                    auth = json.load(f)
                    self.api_key = auth.get("OPENAI_API_KEY")
            except Exception:
                pass

        if not self.api_key:
            raise ValueError("API key not found in config, environment, or ~/.codex/auth.json")

    def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        url = f"{self.base_url.rstrip('/')}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "input": text[:8192],  # Truncate if too long
        }

        response = requests.post(url, json=payload, headers=headers, timeout=60)
        response.raise_for_status()

        data = response.json()
        return data["data"][0]["embedding"]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        if not texts:
            return []

        url = f"{self.base_url.rstrip('/')}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "input": [t[:8192] for t in texts],
        }

        response = requests.post(url, json=payload, headers=headers, timeout=120)
        response.raise_for_status()

        data = response.json()
        return [item["embedding"] for item in data["data"]]


_embedding_client_instance = None

def get_embedding_client() -> EmbeddingClient:
    """Lazy singleton accessor for EmbeddingClient."""
    global _embedding_client_instance
    if _embedding_client_instance is None:
        _embedding_client_instance = EmbeddingClient()
    return _embedding_client_instance
