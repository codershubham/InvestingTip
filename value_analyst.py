"""Qualitative value analyst powered by OpenRouter free models."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from config.settings import Settings, get_settings
from llm.openrouter_client import OpenRouterClient, OpenRouterError
from prompts import ANALYST_SYSTEM_PROMPT, ANALYST_USER_TEMPLATE
from schemas.signal_schema import validate_analysis_result

logger = logging.getLogger(__name__)


def _sector_thesis_text(macro: dict[str, Any], sector_key: str) -> str:
    for sector in macro.get("selected_sectors", []):
        if sector.get("sector_key") == sector_key:
            catalysts = "; ".join(sector.get("catalysts") or [])
            risks = "; ".join(sector.get("risks") or [])
            return (
                f"Sector: {sector.get('sector_name')} ({sector_key})\n"
                f"Thesis: {sector.get('thesis')}\n"
                f"Catalysts: {catalysts}\n"
                f"Sector risks: {risks}\n"
                f"Macro summary: {macro.get('macro_summary', '')}"
            )
    return (
        f"Sector key: {sector_key}\n"
        f"Macro summary: {macro.get('macro_summary', 'n/a')}"
    )


def _fundamentals_for_prompt(candidate: dict[str, Any]) -> str:
    skip = {"screen_fail_reasons", "summary"}
    payload = {k: v for k, v in candidate.items() if k not in skip}
    if candidate.get("summary"):
        payload["business_summary"] = candidate["summary"]
    return json.dumps(payload, indent=2, default=str)


def analyze_candidate(
    candidate: dict[str, Any],
    macro: dict[str, Any],
    client: OpenRouterClient,
    settings: Settings,
    *,
    max_attempts: int = 3,
) -> dict[str, Any] | None:
    """Run qualitative + fair-value analysis for one screened stock."""
    ticker = candidate.get("ticker", "?")
    sector_key = candidate.get("sector_key", "")
    m_label = macro.get("market_label") or (
        "USA" if macro.get("market", "usa") == "usa" else "India"
    )
    user_prompt = ANALYST_USER_TEMPLATE.format(
        market_label=m_label,
        sector_thesis=_sector_thesis_text(macro, sector_key),
        fundamentals_json=_fundamentals_for_prompt(candidate),
        min_mos=settings.min_margin_of_safety_pct,
        max_de=settings.max_debt_to_equity,
        min_roe=settings.min_roe,
    )

    raw: dict[str, Any] | None = None
    model_used = ""
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            raw, model_used = client.chat_json(
                system=ANALYST_SYSTEM_PROMPT,
                user=user_prompt,
                temperature=0.15,
                max_tokens=3500,
                task="analyst",
            )
            analysis = validate_analysis_result(raw)
            break
        except (OpenRouterError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            logger.warning(
                "Analyst attempt %d/%d failed for %s: %s",
                attempt,
                max_attempts,
                ticker,
                exc,
            )
            time.sleep(min(2 * attempt, 6))
    else:
        logger.error("Analyst failed for %s after retries: %s", ticker, last_error)
        return None

    # Reconcile current price / MoS with hard data when model drifts.
    price = candidate.get("current_price")
    if price and analysis.get("current_price") in (None, 0):
        analysis["current_price"] = price
    elif price:
        analysis["current_price"] = price

    fv = float(analysis["fair_value_estimate"])
    px = float(analysis.get("current_price") or 0)
    if fv > 0 and px > 0:
        mos = (fv - px) / fv * 100.0
        analysis["margin_of_safety_pct"] = round(mos, 2)

    mos = float(analysis["margin_of_safety_pct"])
    red_flags = bool(analysis["management_red_flags"].get("has_red_flags"))
    moat_score = float(analysis["moat_assessment"].get("score", 0))
    strong_mos = mos >= settings.min_margin_of_safety_pct

    if strong_mos and not red_flags and moat_score >= 5:
        analysis["recommendation"] = "ALERT"
        analysis["passes_margin_of_safety"] = True
    elif mos >= 10 and not red_flags:
        analysis["recommendation"] = "WATCHLIST"
        analysis["passes_margin_of_safety"] = False
    else:
        analysis["recommendation"] = "PASS"
        analysis["passes_margin_of_safety"] = False

    analysis["sector_key"] = sector_key or analysis.get("sector_key")
    analysis["_meta"] = {
        "model_used": model_used,
        "screen_metrics": {
            "trailing_pe": candidate.get("trailing_pe"),
            "sector_avg_pe": candidate.get("sector_avg_pe"),
            "debt_to_equity": candidate.get("debt_to_equity"),
            "roe_pct": candidate.get("roe_pct"),
            "market_cap": candidate.get("market_cap"),
            "price_to_book": candidate.get("price_to_book"),
        },
    }
    logger.info(
        "Analyzed %s -> %s (MoS=%.1f%%, moat=%.1f, model=%s)",
        ticker,
        analysis["recommendation"],
        mos,
        moat_score,
        model_used,
    )
    return analysis


def analyze_candidates(
    candidates: list[dict[str, Any]],
    macro: dict[str, Any],
    client: OpenRouterClient | None = None,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    """Analyze up to max_analyst_candidates stocks sequentially."""
    settings = settings or get_settings()
    client = client or OpenRouterClient(settings)
    limit = settings.max_analyst_candidates
    selected = candidates[:limit]
    results: list[dict[str, Any]] = []

    for i, candidate in enumerate(selected):
        if i > 0:
            time.sleep(1.5)  # ease free-tier rate limits between names
        analysis = analyze_candidate(candidate, macro, client, settings)
        if analysis:
            results.append(analysis)

    return results


def select_alerts(
    analyses: list[dict[str, Any]],
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    """Return only ALERT recommendations that pass margin-of-safety policy."""
    settings = settings or get_settings()
    alerts: list[dict[str, Any]] = []
    for a in analyses:
        if a.get("recommendation") != "ALERT":
            continue
        if not a.get("passes_margin_of_safety"):
            continue
        if float(a.get("margin_of_safety_pct", 0)) < settings.min_margin_of_safety_pct:
            continue
        alerts.append(a)
    alerts.sort(key=lambda x: -float(x.get("margin_of_safety_pct", 0)))
    return alerts
