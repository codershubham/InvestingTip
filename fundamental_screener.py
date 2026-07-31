"""Hard-math fundamental screener (no LLM).

Filters (non-financials):
  - Trailing P/E < sector average P/E
  - Debt-to-Equity < 0.5 (configurable)
  - ROE > 15% (configurable)

Banks / NBFCs use a different leverage rule (D/E is naturally high):
  - Trailing P/E < sector average
  - Price-to-Book < 2.5 (when available)
  - ROE > 12%
"""

from __future__ import annotations

import logging
import math
from typing import Any

import yfinance as yf

from config.sector_universe import Market, tickers_for_sectors
from config.settings import Settings, get_settings

logger = logging.getLogger(__name__)
logging.getLogger("yfinance").setLevel(logging.CRITICAL)

BANK_LIKE_SECTORS = frozenset({"financials_banks", "india_banks_nbfc"})


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _debt_to_equity(info: dict[str, Any]) -> float | None:
    """Prefer reported D/E; fall back to totalDebt / stockholdersEquity."""
    de = _safe_float(info.get("debtToEquity"))
    if de is not None:
        # Yahoo often reports D/E as a percentage-like figure (e.g. 45.2 = 0.452).
        return de / 100.0 if de > 5 else de

    total_debt = _safe_float(info.get("totalDebt"))
    equity = _safe_float(info.get("stockholdersEquity")) or _safe_float(
        info.get("totalStockholderEquity")
    )
    if total_debt is not None and equity and equity > 0:
        return total_debt / equity
    return None


def _roe_pct(info: dict[str, Any]) -> float | None:
    roe = _safe_float(info.get("returnOnEquity"))
    if roe is None:
        return None
    return roe * 100.0 if abs(roe) <= 1.5 else roe


def _trailing_pe(info: dict[str, Any]) -> float | None:
    pe = _safe_float(info.get("trailingPE"))
    if pe is not None and pe > 0:
        return pe
    price = _safe_float(info.get("currentPrice")) or _safe_float(
        info.get("regularMarketPrice")
    )
    eps = _safe_float(info.get("trailingEps"))
    if price and eps and eps > 0:
        return price / eps
    return None


def fetch_fundamentals(ticker: str) -> dict[str, Any] | None:
    """Pull a defensive fundamentals snapshot for one ticker."""
    try:
        t = yf.Ticker(ticker)
        try:
            info = t.info or {}
        except Exception as exc:  # noqa: BLE001
            logger.warning("Skipping %s (info fetch failed): %s", ticker, exc)
            return None

        if not isinstance(info, dict) or not info:
            logger.warning("No fundamentals for %s", ticker)
            return None

        price = (
            _safe_float(info.get("currentPrice"))
            or _safe_float(info.get("regularMarketPrice"))
            or _safe_float(info.get("previousClose"))
        )
        pe = _trailing_pe(info)
        if price is None and pe is None:
            logger.warning("Skipping %s (no price/PE — likely bad ticker)", ticker)
            return None

        de = _debt_to_equity(info)
        roe = _roe_pct(info)

        return {
            "ticker": ticker,
            "company_name": info.get("longName") or info.get("shortName") or ticker,
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "currency": info.get("currency"),
            "current_price": price,
            "trailing_pe": pe,
            "forward_pe": _safe_float(info.get("forwardPE")),
            "debt_to_equity": de,
            "roe_pct": roe,
            "profit_margin": _safe_float(info.get("profitMargins")),
            "operating_margin": _safe_float(info.get("operatingMargins")),
            "revenue_growth": _safe_float(info.get("revenueGrowth")),
            "earnings_growth": _safe_float(info.get("earningsGrowth")),
            "free_cashflow": _safe_float(info.get("freeCashflow")),
            "market_cap": _safe_float(info.get("marketCap")),
            "enterprise_value": _safe_float(info.get("enterpriseValue")),
            "book_value": _safe_float(info.get("bookValue")),
            "price_to_book": _safe_float(info.get("priceToBook")),
            "dividend_yield": _safe_float(info.get("dividendYield")),
            "fifty_two_week_low": _safe_float(info.get("fiftyTwoWeekLow")),
            "fifty_two_week_high": _safe_float(info.get("fiftyTwoWeekHigh")),
            "shares_outstanding": _safe_float(info.get("sharesOutstanding")),
            "summary": (info.get("longBusinessSummary") or "")[:1200],
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to fetch %s: %s", ticker, exc)
        return None


def _sector_avg_pe(rows: list[dict[str, Any]]) -> float | None:
    pes = [
        r["trailing_pe"]
        for r in rows
        if r.get("trailing_pe") is not None and r["trailing_pe"] > 0
    ]
    if not pes:
        return None
    return sum(pes) / len(pes)


def _apply_filters(
    row: dict[str, Any],
    *,
    sector_key: str,
    sector_pe: float | None,
    settings: Settings,
) -> list[str]:
    """Return fail reasons (empty list = pass)."""
    reasons: list[str] = []
    pe = row.get("trailing_pe")
    de = row.get("debt_to_equity")
    roe = row.get("roe_pct")
    pb = row.get("price_to_book")
    bank_like = sector_key in BANK_LIKE_SECTORS

    if pe is None:
        reasons.append("missing_pe")
    elif sector_pe is not None and pe >= sector_pe:
        reasons.append(f"pe_not_below_sector_avg ({pe:.2f} >= {sector_pe:.2f})")
    elif sector_pe is None and pe > 25:
        reasons.append(f"pe_above_fallback_ceiling ({pe:.2f} > 25)")

    if bank_like:
        # Banks are levered by design — use P/B + slightly softer ROE.
        min_roe = min(settings.min_roe, 12.0)
        if pb is None:
            reasons.append("missing_price_to_book")
        elif pb >= 2.5:
            reasons.append(f"price_to_book_too_high ({pb:.2f} >= 2.5)")
        if roe is None:
            reasons.append("missing_roe")
        elif roe <= min_roe:
            reasons.append(f"roe_too_low ({roe:.2f} <= {min_roe})")
    else:
        if de is None:
            reasons.append("missing_debt_to_equity")
        elif de >= settings.max_debt_to_equity:
            reasons.append(
                f"debt_to_equity_too_high ({de:.3f} >= {settings.max_debt_to_equity})"
            )
        if roe is None:
            reasons.append("missing_roe")
        elif roe <= settings.min_roe:
            reasons.append(f"roe_too_low ({roe:.2f} <= {settings.min_roe})")

    return reasons


def screen_sector(
    sector_key: str,
    tickers: list[str],
    settings: Settings,
) -> dict[str, Any]:
    """Fetch peers and apply hard value filters."""
    fetched: list[dict[str, Any]] = []
    for ticker in tickers:
        row = fetch_fundamentals(ticker)
        if row:
            fetched.append(row)

    sector_pe = _sector_avg_pe(fetched)
    passed: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for row in fetched:
        reasons = _apply_filters(
            row,
            sector_key=sector_key,
            sector_pe=sector_pe,
            settings=settings,
        )
        enriched = {
            **row,
            "sector_key": sector_key,
            "sector_avg_pe": sector_pe,
            "screen_pass": not reasons,
            "screen_fail_reasons": reasons,
            "screen_mode": "bank_like" if sector_key in BANK_LIKE_SECTORS else "standard",
        }
        if reasons:
            rejected.append(enriched)
        else:
            passed.append(enriched)

    passed.sort(key=lambda r: (r.get("trailing_pe") or 999, -(r.get("roe_pct") or 0)))
    passed = passed[: settings.max_candidates_per_sector]

    logger.info(
        "Sector %s: fetched=%d sector_avg_pe=%s passed=%d rejected=%d mode=%s",
        sector_key,
        len(fetched),
        f"{sector_pe:.2f}" if sector_pe else "n/a",
        len(passed),
        len(rejected),
        "bank_like" if sector_key in BANK_LIKE_SECTORS else "standard",
    )
    return {
        "sector_key": sector_key,
        "sector_avg_pe": sector_pe,
        "fetched_count": len(fetched),
        "passed": passed,
        "rejected_sample": rejected[:10],
    }


def screen_sectors(
    sector_keys: list[str],
    settings: Settings | None = None,
    market: Market | str | None = None,
) -> list[dict[str, Any]]:
    """Screen all selected sectors; return list of per-sector results."""
    settings = settings or get_settings()
    universe = tickers_for_sectors(sector_keys, market=market)
    if not universe:
        logger.error(
            "No tickers resolved for sectors=%s market=%s", sector_keys, market
        )
        return []

    results: list[dict[str, Any]] = []
    for key, tickers in universe.items():
        results.append(screen_sector(key, tickers, settings))
    return results


def flatten_passed_candidates(
    screen_results: list[dict[str, Any]],
    *,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Flatten passed candidates across sectors, cheapest PE first."""
    all_passed: list[dict[str, Any]] = []
    for block in screen_results:
        all_passed.extend(block.get("passed") or [])
    all_passed.sort(
        key=lambda r: (r.get("trailing_pe") or 999, -(r.get("roe_pct") or 0))
    )
    if limit is not None:
        return all_passed[:limit]
    return all_passed
