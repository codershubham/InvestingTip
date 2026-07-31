"""OpenRouter client with free-model fallback and rate-limit handling."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

import requests

from config.settings import LlmTask, Settings, get_settings

logger = logging.getLogger(__name__)

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)


class OpenRouterError(RuntimeError):
    """Raised when all models / retries are exhausted."""


class OpenRouterClient:
    """Chat-completions client with ordered model fallback (not random)."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._task_indexes: dict[str, int] = {}

    def models_for(self, task: LlmTask = "default") -> tuple[str, ...]:
        return self.settings.models_for_task(task)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/value-investing-alert",
            "X-Title": "Value Investing Alert System",
        }

    def _next_model(self, task: LlmTask, failed: str | None = None) -> str:
        models = self.models_for(task)
        if not models:
            raise OpenRouterError("No OpenRouter models configured")
        idx = self._task_indexes.get(task, 0)
        if failed and failed in models:
            idx = (models.index(failed) + 1) % len(models)
        model = models[idx % len(models)]
        self._task_indexes[task] = (idx + 1) % len(models)
        return model

    def chat(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        task: LlmTask = "default",
    ) -> tuple[str, str]:
        """
        Return (content, model_used).

        Model selection is deterministic:
          1. Use the ordered list for `task` (macro / analyst / default)
          2. On 429 / 5xx / timeout / bad response, try the next model
        It does NOT pick randomly.
        """
        models = self.models_for(task)
        errors: list[str] = []
        attempts = max(len(models) * self.settings.llm_max_retries, 1)
        last_model: str | None = None

        logger.info(
            "LLM task=%s trying models in order: %s",
            task,
            ", ".join(models[:5]) + ("..." if len(models) > 5 else ""),
        )

        for attempt in range(attempts):
            model = self._next_model(task, failed=last_model if attempt else None)
            last_model = model
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            try:
                response = requests.post(
                    f"{self.settings.openrouter_base_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                    timeout=self.settings.llm_timeout_seconds,
                )
            except requests.RequestException as exc:
                msg = f"{model}: network error: {exc}"
                logger.warning(msg)
                errors.append(msg)
                time.sleep(min(2**attempt, 20))
                continue

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait = (
                    float(retry_after)
                    if retry_after and str(retry_after).replace(".", "", 1).isdigit()
                    else min(2**attempt, 30)
                )
                msg = f"{model}: rate limited (429); waiting {wait}s then rotating"
                logger.warning(msg)
                errors.append(msg)
                time.sleep(wait)
                continue

            if response.status_code >= 500:
                msg = f"{model}: server error {response.status_code}"
                logger.warning(msg)
                errors.append(msg)
                time.sleep(min(2**attempt, 20))
                continue

            if response.status_code >= 400:
                body = response.text[:400]
                msg = f"{model}: HTTP {response.status_code}: {body}"
                logger.warning(msg)
                errors.append(msg)
                time.sleep(1)
                continue

            try:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                if not content or not str(content).strip():
                    raise KeyError("empty content")
                used = data.get("model", model)
                logger.info("OpenRouter success task=%s model=%s", task, used)
                return str(content), str(used)
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                msg = f"{model}: malformed response: {exc}"
                logger.warning(msg)
                errors.append(msg)
                continue

        raise OpenRouterError(
            f"All OpenRouter models failed for task={task}. Last errors:\n"
            + "\n".join(errors[-8:])
        )

    def chat_json(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.15,
        max_tokens: int = 4096,
        task: LlmTask = "default",
    ) -> tuple[dict[str, Any], str]:
        """Call chat and parse a JSON object from the response."""
        content, model = self.chat(
            system=system,
            user=user,
            temperature=temperature,
            max_tokens=max_tokens,
            task=task,
        )
        parsed = extract_json_object(content)
        return parsed, model


def extract_json_object(text: str) -> dict[str, Any]:
    """Extract the first JSON object from model text (handles fences / chatter)."""
    cleaned = text.strip()
    fence = _JSON_FENCE_RE.search(cleaned)
    if fence:
        cleaned = fence.group(1).strip()

    try:
        obj = json.loads(cleaned)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")
    if start < 0:
        raise ValueError(f"Could not parse JSON object from LLM response: {text[:500]}")

    end = cleaned.rfind("}")
    candidates = []
    if end > start:
        candidates.append(cleaned[start : end + 1])
    # Truncated payloads often never close the root object.
    candidates.append(cleaned[start:])

    for snippet in candidates:
        try:
            obj = json.loads(snippet)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            repaired = _repair_truncated_json(snippet)
            if repaired:
                try:
                    obj = json.loads(repaired)
                    if isinstance(obj, dict):
                        return obj
                except json.JSONDecodeError:
                    continue

    raise ValueError(f"Could not parse JSON object from LLM response: {text[:500]}")


def _repair_truncated_json(snippet: str) -> str | None:
    """Best-effort close of truncated JSON objects from free models."""
    s = snippet.rstrip()
    # Strip a dangling incomplete value after the last complete delimiter.
    while s and s[-1] in ",:":
        s = s[:-1].rstrip()
    if s.count('"') % 2 == 1:
        s += '"'
    # If we ended mid-number/true/null nothing else to do; close containers.
    open_braces = s.count("{") - s.count("}")
    open_brackets = s.count("[") - s.count("]")
    if open_braces < 0 or open_brackets < 0:
        return None
    s += "]" * open_brackets
    s += "}" * open_braces
    try:
        json.loads(s)
        return s
    except json.JSONDecodeError:
        return None
