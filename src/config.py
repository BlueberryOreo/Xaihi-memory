"""Configuration loader for xaihi memory system."""
import os
import re
from pathlib import Path
from typing import Any

import yaml


class Config:
    """Memory system configuration."""

    _instance = None
    _config: dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance

    def _load(self) -> None:
        config_path = Path(__file__).parent.parent / "config.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            self._config = yaml.safe_load(f)

        # Load secrets from bashrc if not in config
        self._load_secrets_from_bashrc()

    def _load_secrets_from_bashrc(self) -> None:
        """Load api_key and base_url from .bashrc if not set in config."""
        bashrc_path = Path.home() / ".bashrc"
        if not bashrc_path.exists():
            return

        with open(bashrc_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Pattern: export VAR_NAME="value"
        pattern = re.compile(r'export\s+(\w+)=["\']([^"\']+)["\']')

        for match in pattern.finditer(content):
            var_name, var_value = match.groups()

            # Map bashrc vars to config paths
            if var_name == "DASHSCOPE_API_KEY":
                if not self.get("llm.api_key"):
                    self._config.setdefault("llm", {})["api_key"] = var_value
            elif var_name == "DASHSCOPE_BASE_URL":
                if not self.get("llm.base_url"):
                    self._config.setdefault("llm", {})["base_url"] = var_value
            elif var_name == "OPENAI_API_KEY":
                if not self.get("embedding.api_key"):
                    self._config.setdefault("embedding", {})["api_key"] = var_value
            elif var_name == "OPENAI_BASE_URL":
                if not self.get("embedding.base_url"):
                    self._config.setdefault("embedding", {})["base_url"] = var_value

    def get(self, key: str, default: Any = None) -> Any:
        """Get config value by dot-separated key path."""
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            if value is None:
                return default
        return value

    def get_chroma(self) -> dict[str, Any]:
        return self._config.get("chroma", {})

    def get_embedding(self) -> dict[str, Any]:
        return self._config.get("embedding", {})

    def get_llm(self) -> dict[str, Any]:
        return self._config.get("llm", {})

    def get_memory(self) -> dict[str, Any]:
        return self._config.get("memory", {})

    def get_recall(self) -> dict[str, Any]:
        return self._config.get("recall", {})

    def get_summary(self) -> dict[str, Any]:
        return self._config.get("summary", {})

    def expand_path(self, path: str) -> Path:
        """Expand ~ and environment variables in path."""
        return Path(os.path.expandvars(os.path.expanduser(path)))


config = Config()
