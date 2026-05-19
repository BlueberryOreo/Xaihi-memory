"""Embedding client for xaihi memory system.

Supports two backends:
  - openai:   remote API (text-embedding-v4)
  - local:    ONNX model (BAAI/bge-small-zh-v1.5)
"""
import os
import numpy as np
from pathlib import Path
from typing import Any, List

try:
    from .config import config
except ImportError:
    from config import config


# ── Local ONNX backend ───────────────────────────────────────────────

_ONNX_SESSION = None
_ONNX_TOKENIZER = None
_ONNX_DIM = 512
_ONNX_MODEL_DIR = Path(os.path.expanduser("~/.claude/models/bge-small-zh-v1.5-onnx"))


def _ensure_onnx():
    """Lazy-load ONNX session + tokenizer."""
    global _ONNX_SESSION, _ONNX_TOKENIZER

    if _ONNX_TOKENIZER is None:
        from tokenizers import Tokenizer
        _ONNX_TOKENIZER = Tokenizer.from_file(str(_ONNX_MODEL_DIR / "tokenizer.json"))
        _ONNX_TOKENIZER.enable_truncation(512)

    if _ONNX_SESSION is None:
        import onnxruntime as ort
        available = ort.get_available_providers()
        providers = [p for p in ["CUDAExecutionProvider", "CPUExecutionProvider"] if p in available]
        onnx_path = str(_ONNX_MODEL_DIR / "model.onnx")
        _ONNX_SESSION = ort.InferenceSession(onnx_path, providers=providers)
        print(f"[embedding] ONNX loaded (providers: {_ONNX_SESSION.get_providers()})")


def _cls_pooling(logits: np.ndarray) -> np.ndarray:
    """Take [CLS] token (first token) and L2-normalize."""
    cls = logits[:, 0, :]  # (batch, 512)
    norms = np.linalg.norm(cls, axis=1, keepdims=True)
    return cls / (norms + 1e-8)


def _tokenize(texts: List[str]):
    """Tokenize and return numpy arrays (padded to max length)."""
    encodings = _ONNX_TOKENIZER.encode_batch(texts)
    max_len = max(len(e.ids) for e in encodings)
    input_ids = np.zeros((len(texts), max_len), dtype=np.int64)
    for i, e in enumerate(encodings):
        input_ids[i, :len(e.ids)] = e.ids
    attention_mask = (input_ids != 0).astype(np.int64)
    return input_ids, attention_mask


def embed_local(text: str) -> List[float]:
    """Generate embedding for a single text using ONNX."""
    _ensure_onnx()
    input_ids, attention_mask = _tokenize([text])
    outputs = _ONNX_SESSION.run(None, {
        "input_ids": input_ids,
        "attention_mask": attention_mask,
    })
    pooled = _cls_pooling(outputs[0])
    return pooled[0].tolist()


def embed_batch_local(texts: List[str]) -> List[List[float]]:
    """Generate embeddings for multiple texts using ONNX."""
    if not texts:
        return []
    _ensure_onnx()
    input_ids, attention_mask = _tokenize(texts)
    outputs = _ONNX_SESSION.run(None, {
        "input_ids": input_ids,
        "attention_mask": attention_mask,
    })
    pooled = _cls_pooling(outputs[0])
    return [emb.tolist() for emb in pooled]


# ── OpenAI API backend ──────────────────────────────────────────────

def _embed_openai(text: str) -> List[float]:
    """Generate embedding via OpenAI-compatible API."""
    import requests
    cfg = config.get_embedding()
    base_url = cfg.get("base_url", "https://api.openai.com/v1")
    model = cfg.get("model", "text-embedding-v4")
    api_key = (cfg.get("api_key")
               or os.environ.get(cfg.get("api_key_env", "OPENAI_API_KEY"))
               or os.environ.get("OPENAI_API_KEY", "fallback"))

    url = f"{base_url.rstrip('/')}/embeddings"
    resp = requests.post(url, json={
        "model": model,
        "input": text[:8192],
    }, headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }, timeout=60)
    resp.raise_for_status()
    return resp.json()["data"][0]["embedding"]


def _embed_batch_openai(texts: List[str]) -> List[List[float]]:
    """Batch embedding via OpenAI-compatible API."""
    import requests
    cfg = config.get_embedding()
    base_url = cfg.get("base_url", "https://api.openai.com/v1")
    model = cfg.get("model", "text-embedding-v4")
    api_key = (cfg.get("api_key")
               or os.environ.get(cfg.get("api_key_env", "OPENAI_API_KEY"))
               or os.environ.get("OPENAI_API_KEY", "fallback"))

    url = f"{base_url.rstrip('/')}/embeddings"
    resp = requests.post(url, json={
        "model": model,
        "input": [t[:8192] for t in texts],
    }, headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }, timeout=120)
    resp.raise_for_status()
    return [item["embedding"] for item in resp.json()["data"]]


# ── Unified API ─────────────────────────────────────────────────────

def get_embedding_dimension() -> int:
    """Return the embedding dimension based on current config."""
    cfg = config.get_embedding()
    provider = cfg.get("provider", "openai")
    if provider == "local":
        return cfg.get("dimension", _ONNX_DIM)
    return cfg.get("dimension", 1536)


def embed(text: str) -> List[float]:
    """Generate embedding for a single text."""
    cfg = config.get_embedding()
    provider = cfg.get("provider", "openai")
    if provider == "local":
        return embed_local(text)
    return _embed_openai(text)


def embed_batch(texts: List[str]) -> List[List[float]]:
    """Generate embeddings for multiple texts."""
    if not texts:
        return []
    cfg = config.get_embedding()
    provider = cfg.get("provider", "openai")
    if provider == "local":
        return embed_batch_local(texts)
    return _embed_batch_openai(texts)
