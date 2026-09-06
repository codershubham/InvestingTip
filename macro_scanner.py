"""Macro news scanner → 1–2 bullish growth sectors via OpenRouter."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import Any

import requests
import yfinance as yf

from config.sector_universe import (
    Market,
    get_universe,
    market_label,
    normalize_market,
    resolve_sector_key,
)
from config.settings import Settings, get_settings
from llm.openrouter_client import OpenRouterClient, OpenRouterError
from prompts import MACRO_USER_TEMPLATE, build_macro_system_prompt
from schemas.signal_schema import validate_macro_result

logger = logging.getLogger(__name__)

USA_RSS_FEEDS: tuple[tuple[str, str], ...] = (
    (
        "Yahoo Finance Markets",
        "https://finance.yahoo.com/rss/topstories",
    ),
    (
        "Google News Business US",
        "https://news.google.com/rss/search?q=economy+OR+federal+reserve+OR+inflation+OR+policy+when:7d&hl=en-US&gl=US&ceid=US:en",
    ),
    (
        "Google News Markets US",
        "https://news.google.com/rss/search?q=stock+market+OR+sector+outlook+OR+earnings+when:7d&hl=en-US&gl=US&ceid=US:en",
    ),
)

INDIA_RSS_FEEDS: tuple[tuple[str, str], ...] = (
    (
        "Google News India Economy",
        "https://news.google.com/rss/search?q=India+economy+OR+RBI+OR+inflation+OR+Union+Budget+OR+policy+when:7d&hl=en-IN&gl=IN&ceid=IN:en",
    ),
    (
        "Google News India Markets",
        "https://news.google.com/rss/search?q=Nifty+OR+Sensex+OR+India+stock+market+OR+sector+outlook+OR+earnings+when:7d&hl=en-IN&gl=IN&ceid=IN:en",
    ),
    (
        "Google News India Business",
        "https://news.google.com/rss/search?q=India+business+OR+infrastructure+OR+manufacturing+OR+banks+OR+IT+services+when:7d&hl=en-IN&gl=IN&ceid=IN:en",
    ),
)

USA_INDEX_TICKERS: tuple[str, ...] = (
    "^GSPC",
    "^IXIC",
    "^DJI",
    "^VIX",
    "^TNX",
    "GC=F",
    "CL=F",
)

INDIA_INDEX_TICKERS: tuple[str, ...] = (
    "^NSEI",  # Nifty 50
    "^BSESN",  # Sensex
    "^NSEBANK",  # Bank Nifty
    "INR=X",  # USDINR
    "GC=F",
    "CL=F",
)


def feeds_for_market(market: Market) -> tuple[tuple[str, str], ...]:
    return INDIA_RSS_FEEDS if market == "india" else USA_RSS_FEEDS


def indexes_for_market(market: Market) -> tuple[str, ...]:
    return INDIA_INDEX_TICKERS if market == "india" else USA_INDEX_TICKERS


def fetch_rss_headlines(
    settings: Settings,
    market: Market = "usa",
    *,
    max_per_feed: int = 12,
) -> list[dict[str, str]]:
    """Fetch recent headlines from market-scoped free RSS endpoints."""
    headlines: list[dict[str, str]] = []
    headers = {"User-Agent": settings.http_user_agent}

    for source, url in feeds_for_market(market):
        try:
            resp = requests.get(url, headers=headers, timeout=25)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            items = root.findall(".//item")
            for item in items[:max_per_feed]:
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                pub = (item.findtext("pubDate") or "").strip()
                if title:
                    headlines.append(
                        {
                            "source": source,
                            "title": title,
                            "link": link,
                            "published": pub,
                        }
                    )
        except Exception as exc:  # noqa: BLE001 — defensive per-feed
            logger.warning("RSS fetch failed for %s: %s", source, exc)

    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for h in headlines:
        key = h["title"].lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(h)
    return unique


def fetch_market_snapshot(market: Market = "usa") -> dict[str, Any]:
    """Lightweight broad-market snapshot via yfinance."""
    snapshot: dict[str, Any] = {}
    for ticker in indexes_for_market(market):
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="5d")
            if hist is None or hist.empty:
                snapshot[ticker] = {"error": "no data"}
                continue
            last = float(hist["Close"].iloc[-1])
            first = float(hist["Close"].iloc[0])
            change_pct = ((last - first) / first * 100.0) if first else None
            snapshot[ticker] = {
                "last": round(last, 4),
                "5d_change_pct": round(change_pct, 3) if change_pct is not None else None,
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("Index snapshot failed for %s: %s", ticker, exc)
            snapshot[ticker] = {"error": str(exc)}
    return snapshot


def format_news_context(headlines: list[dict[str, str]], *, limit: int = 40) -> str:
    lines: list[str] = []
    for h in headlines[:limit]:
        lines.append(f"- [{h['source']}] {h['title']}")
    if not lines:
        return (
            "No RSS headlines available. Use general knowledge of current "
            "macro themes cautiously and prefer defensive, structural growth sectors."
        )
    return "\n".join(lines)


def _normalize_sector_keys(
    macro: dict[str, Any],
    market: Market,
) -> dict[str, Any]:
    """Resolve free-form sector keys onto the curated market universe."""
    normalized_sectors: list[dict[str, Any]] = []
    for sector in macro.get("selected_sectors", []):
        raw_key = str(sector.get("sector_key", ""))
        resolved = resolve_sector_key(raw_key, market=market)
        if not resolved:
            resolved = resolve_sector_key(str(sector.get("sector_name", "")), market=market)
        if not resolved:
            logger.warning("Dropping unmapped sector for %s: %s", market, sector)
            continue
        sector = dict(sector)
        sector["sector_key"] = resolved
        normalized_sectors.append(sector)
    if not normalized_sectors:
        raise ValueError(
            f"Macro scanner returned no sectors that map to the {market_label(market)} universe"
        )
    macro["selected_sectors"] = normalized_sectors[:2]
    return macro


_STOPWORDS = frozenset(
    {
        "and",
        "the",
        "for",
        "with",
        "from",
        "that",
        "this",
        "into",
        "major",
        "large",
        "names",
        "other",
        "only",
    }
)

_MARKET_DEFAULTS: dict[Market, tuple[str, ...]] = {
    "usa": ("semiconductors", "healthcare_biotech"),
    "india": ("india_infra_capgoods", "india_banks_nbfc"),
}


def _sector_tokens(sector_key: str, name: str, description: str) -> set[str]:
    blob = f"{sector_key.replace('_', ' ')} {name} {description}".lower()
    return {
        tok.strip("&,./")
        for tok in blob.replace("india ", "").split()
        if len(tok) > 3 and tok not in _STOPWORDS
    }


def heuristic_select_sectors(
    headlines: list[dict[str, str]],
    market: Market,
    *,
    max_sectors: int = 2,
    reason: str = "llm_unavailable",
) -> dict[str, Any]:
    """Pick 1–2 sectors from headline keyword hits when OpenRouter is unavailable."""
    universe = get_universe(market)
    blob = " ".join(h.get("title", "") for h in headlines).lower()
    scored: list[tuple[int, str]] = []
    for key, meta in universe.items():
        tokens = _sector_tokens(key, meta["name"], meta["description"])
        score = sum(blob.count(tok) for tok in tokens)
        scored.append((score, key))
    scored.sort(key=lambda item: (-item[0], item[1]))

    picked: list[str] = [key for score, key in scored if score > 0][:max_sectors]
    if len(picked) < max_sectors:
        for fallback in _MARKET_DEFAULTS.get(market, ()):
            if fallback not in picked and fallback in universe:
                picked.append(fallback)
            if len(picked) >= max_sectors:
                break
    if not picked:
        picked = list(universe.keys())[:max_sectors]

    label = market_label(market)
    if reason == "auth":
        summary = (
            f"{label} heuristic sector screen used because OpenRouter authentication failed. "
            "Sectors are ranked from RSS headline keywords against the curated universe; "
            "replace OPENROUTER_API_KEY at https://openrouter.ai/keys to restore LLM analysis."
        )
        thesis_prefix = "Heuristic fallback (OpenRouter unavailable)"
        risk = "Not an LLM macro call — refresh OPENROUTER_API_KEY for qualitative picks"
    else:
        summary = (
            f"{label} heuristic sector screen used because the LLM did not return usable JSON. "
            "Sectors are ranked from RSS headline keywords against the curated universe."
        )
        thesis_prefix = "Heuristic fallback (LLM JSON unavailable)"
        risk = "Not an LLM macro call — free-model JSON parse or validation failed"

    selected = []
    for key in picked[:max_sectors]:
        meta = universe[key]
        selected.append(
            {
                "sector_key": key,
                "sector_name": meta["name"],
                "thesis": (
                    f"{thesis_prefix}: sector ranked from "
                    "recent headline keywords and the curated long-term universe. "
                    f"{meta['description']}."
                ),
                "catalysts": ["Headline keyword match / structural default"],
                "risks": [risk],
                "confidence": 0.35,
            }
        )

    return {
        "horizon_months": 24,
        "macro_summary": summary,
        "selected_sectors": selected,
        "rejected_themes": [],
    }


def scan_macro_sectors(
    client: OpenRouterClient | None = None,
    settings: Settings | None = None,
    market: Market | str = "usa",
) -> dict[str, Any]:
    """
    Fetch market-scoped news + index context, then ask an OpenRouter free model
    to pick 1–2 bullish growth sectors for a 12–36 month horizon.
    """
    settings = settings or get_settings()
    client = client or OpenRouterClient(settings)
    m = normalize_market(market)

    headlines = fetch_rss_headlines(settings, market=m)
    snapshot = fetch_market_snapshot(m)
    news_context = format_news_context(headlines)
    market_snapshot = _pretty_json(snapshot)
    label = market_label(m)

    logger.info(
        "Macro scan [%s]: %d headlines, %d index points",
        label,
        len(headlines),
        len(snapshot),
    )

    system_prompt = build_macro_system_prompt(m)
    user_prompt = MACRO_USER_TEMPLATE.format(
        market_label=label,
        news_context=news_context,
        market_snapshot=market_snapshot,
    )

    try:
        raw, model_used = client.chat_json(
            system=system_prompt,
            user=user_prompt,
            temperature=0.2,
            max_tokens=2500,
            task="macro",
        )
        validated = validate_macro_result(raw)
        normalized = _normalize_sector_keys(validated, market=m)
    except (OpenRouterError, ValueError) as exc:
        auth_failed = isinstance(exc, OpenRouterError) and getattr(
            exc, "auth_failed", False
        )
        logger.warning(
            "LLM macro scan failed (%s); using heuristic sector fallback",
            "auth" if auth_failed else exc,
        )
        raw = heuristic_select_sectors(
            headlines,
            m,
            max_sectors=settings.max_sectors,
            reason="auth" if auth_failed else "json",
        )
        validated = validate_macro_result(raw)
        normalized = _normalize_sector_keys(validated, market=m)
        model_used = "heuristic_fallback"
    normalized["market"] = m
    normalized["market_label"] = label
    normalized["_meta"] = {
        "model_used": model_used,
        "market": m,
        "headline_count": len(headlines),
        "market_snapshot": snapshot,
    }
    normalized["selected_sectors"] = normalized["selected_sectors"][: settings.max_sectors]
    logger.info(
        "Selected %s sectors: %s",
        label,
        [s["sector_key"] for s in normalized["selected_sectors"]],
    )
    return normalized


def _pretty_json(obj: Any) -> str:
    import json

    return json.dumps(obj, indent=2, default=str)
