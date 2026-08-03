"""Runtime settings loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

from dotenv import load_dotenv

load_dotenv()

LlmTask = Literal["macro", "analyst", "default"]

# OpenRouter free-tier models (Jul 2026 top free endpoints), ordered by preference.
# Shared fallback chain — used when task-specific lists are empty / exhausted.
DEFAULT_FREE_MODELS: tuple[str, ...] = (
    "nvidia/nemotron-3-super-120b-a12b:free",
    "inclusionai/ling-3.0-flash:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "poolside/laguna-s-2.1:free",
    "nvidia/nemotron-3-nano-30b-a3b:free",
    "poolside/laguna-xs-2.1:free",
    "cohere/north-mini-code:free",
)

# Macro sector pick: prefer fast / solid JSON instruction followers first.
DEFAULT_MACRO_MODELS: tuple[str, ...] = (
    "inclusionai/ling-3.0-flash:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "nvidia/nemotron-3-nano-30b-a3b:free",
    "poolside/laguna-s-2.1:free",
    "poolside/laguna-xs-2.1:free",
)

# Value analyst: Super first (faster/reliable), Ultra as heavy fallback.
DEFAULT_ANALYST_MODELS: tuple[str, ...] = (
    "nvidia/nemotron-3-super-120b-a12b:free",
    "inclusionai/ling-3.0-flash:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "poolside/laguna-s-2.1:free",
    "nvidia/nemotron-3-nano-30b-a3b:free",
)


@dataclass(frozen=True)
class Settings:
    """Immutable application settings."""

    openrouter_api_key: str
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_models: tuple[str, ...] = DEFAULT_FREE_MODELS
    openrouter_models_macro: tuple[str, ...] = DEFAULT_MACRO_MODELS
    openrouter_models_analyst: tuple[str, ...] = DEFAULT_ANALYST_MODELS

    # Email — supports Gmail SMTP or Resend SMTP relay
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = ""
    email_to: str = ""

    # Optional Resend HTTP API (preferred over SMTP when set)
    resend_api_key: str = ""

    # Screening thresholds (value investing hard filters)
    max_debt_to_equity: float = 0.5
    min_roe: float = 15.0  # percent
    min_margin_of_safety_pct: float = 20.0  # only alert if MoS >= this

    # Soft-guide entry timing (never changes ALERT → WATCHLIST)
    entry_gap_pct: float = 2.0  # open vs prior close gap-down threshold
    entry_falling_5d_pct: float = -8.0  # 5d return ≤ this → falling_knife
    entry_falling_20d_pct: float = -15.0  # 20d return ≤ this → falling_knife
    entry_caution_5d_pct: float = -4.0  # 5d return ≤ this → caution

    # Pipeline limits
    max_sectors: int = 2
    max_candidates_per_sector: int = 8
    max_analyst_candidates: int = 5
    llm_max_retries: int = 3
    llm_timeout_seconds: int = 90
    http_user_agent: str = (
        "ValueInvestingAlert/1.0 (+https://github.com; research-only)"
    )

    dry_run: bool = False
    log_level: str = "INFO"

    def models_for_task(self, task: LlmTask = "default") -> tuple[str, ...]:
        """Return ordered model list for a pipeline stage (with shared fallback)."""
        if task == "macro":
            primary = self.openrouter_models_macro
        elif task == "analyst":
            primary = self.openrouter_models_analyst
        else:
            primary = self.openrouter_models

        seen: set[str] = set()
        ordered: list[str] = []
        for model in (*primary, *self.openrouter_models):
            if model not in seen:
                seen.add(model)
                ordered.append(model)
        return tuple(ordered) or DEFAULT_FREE_MODELS

    def validate(self) -> list[str]:
        """Return a list of missing/invalid configuration problems."""
        problems: list[str] = []
        if not self.openrouter_api_key:
            problems.append("OPENROUTER_API_KEY is required")
        if not self.email_to:
            problems.append("EMAIL_TO is required")
        if not self.resend_api_key:
            if not self.smtp_user or not self.smtp_password:
                problems.append(
                    "Either RESEND_API_KEY or SMTP_USER + SMTP_PASSWORD is required"
                )
            if not self.email_from:
                problems.append("EMAIL_FROM is required when using SMTP")
        elif not self.email_from:
            problems.append("EMAIL_FROM is required (Resend verified sender)")
        return problems


def _parse_models(raw: str | None, fallback: tuple[str, ...]) -> tuple[str, ...]:
    if not raw or not raw.strip():
        return fallback
    models = tuple(m.strip() for m in raw.split(",") if m.strip())
    return models or fallback


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load settings once per process."""
    shared = _parse_models(os.getenv("OPENROUTER_MODELS"), DEFAULT_FREE_MODELS)
    return Settings(
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY", "").strip(),
        openrouter_base_url=os.getenv(
            "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
        ).rstrip("/"),
        openrouter_models=shared,
        openrouter_models_macro=_parse_models(
            os.getenv("OPENROUTER_MODELS_MACRO"), DEFAULT_MACRO_MODELS
        ),
        openrouter_models_analyst=_parse_models(
            os.getenv("OPENROUTER_MODELS_ANALYST"), DEFAULT_ANALYST_MODELS
        ),
        smtp_host=os.getenv("SMTP_HOST", "smtp.gmail.com"),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        smtp_user=os.getenv("SMTP_USER", "").strip(),
        smtp_password=os.getenv("SMTP_PASSWORD", "").strip(),
        email_from=os.getenv("EMAIL_FROM", "").strip(),
        email_to=os.getenv("EMAIL_TO", "").strip(),
        resend_api_key=os.getenv("RESEND_API_KEY", "").strip(),
        max_debt_to_equity=float(os.getenv("MAX_DEBT_TO_EQUITY", "0.5")),
        min_roe=float(os.getenv("MIN_ROE", "15.0")),
        min_margin_of_safety_pct=float(os.getenv("MIN_MARGIN_OF_SAFETY_PCT", "20.0")),
        entry_gap_pct=float(os.getenv("ENTRY_GAP_PCT", "2.0")),
        entry_falling_5d_pct=float(os.getenv("ENTRY_FALLING_5D_PCT", "-8.0")),
        entry_falling_20d_pct=float(os.getenv("ENTRY_FALLING_20D_PCT", "-15.0")),
        entry_caution_5d_pct=float(os.getenv("ENTRY_CAUTION_5D_PCT", "-4.0")),
        max_sectors=int(os.getenv("MAX_SECTORS", "2")),
        max_candidates_per_sector=int(os.getenv("MAX_CANDIDATES_PER_SECTOR", "8")),
        max_analyst_candidates=int(os.getenv("MAX_ANALYST_CANDIDATES", "5")),
        llm_max_retries=int(os.getenv("LLM_MAX_RETRIES", "3")),
        llm_timeout_seconds=int(os.getenv("LLM_TIMEOUT_SECONDS", "90")),
        dry_run=os.getenv("DRY_RUN", "false").lower() in {"1", "true", "yes"},
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )
