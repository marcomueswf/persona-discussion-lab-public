from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import dotenv_values
from backend.runtime_paths import get_runtime_file


class EnvironmentService:
    """Read and write the application's .env file for runtime configuration."""

    KEY_ORDER = (
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "OPENAI_MODEL",
    )

    def __init__(self, env_path: str | Path | None = None) -> None:
        self.env_path = Path(env_path) if env_path is not None else get_runtime_file(".env")

    def _read_file_values(self) -> dict[str, str]:
        """Read key-value pairs from the configured environment file."""
        if not self.env_path.exists():
            return {}

        values = dotenv_values(self.env_path)
        return {
            str(key): "" if value is None else str(value)
            for key, value in (values or {}).items()
        }

    def get(self) -> dict[str, Any]:
        """Return configured environment values without exposing the API key."""
        values = self._read_file_values()
        for key in self.KEY_ORDER:
            values.setdefault(key, os.getenv(key, ""))
        api_key = values.get("OPENAI_API_KEY", "")

        ordered = {
            key: values.get(key, "")
            for key in self.KEY_ORDER
            if key != "OPENAI_API_KEY"
        }
        for key, value in values.items():
            if key not in ordered and key != "OPENAI_API_KEY":
                ordered[key] = value

        response = dict(ordered)
        response["OPENAI_API_KEY_SET"] = bool(api_key)
        return response

    def update(self, updates: dict[str, Any]) -> dict[str, Any]:
        """Persist environment updates and return the sanitized configuration."""
        current = self._read_file_values()
        for key, value in (updates or {}).items():
            if key is None:
                continue
            current[str(key)] = "" if value is None else str(value)

        ordered = {}
        for key in self.KEY_ORDER:
            if key in current:
                ordered[key] = current[key]
        for key, value in current.items():
            if key not in ordered:
                ordered[key] = value

        self.env_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [f"{key}={ordered[key]}" for key in ordered]
        self.env_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

        os.environ.update({key: value for key, value in ordered.items() if value})
        for key, value in ordered.items():
            if not value:
                os.environ.pop(key, None)
        response = {
            key: value for key, value in ordered.items() if key != "OPENAI_API_KEY"
        }
        response["OPENAI_API_KEY_SET"] = bool(
            ordered.get("OPENAI_API_KEY", "")
        )
        return response
