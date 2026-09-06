"""Soft-guide entry timing for ALERT emails (never changes recommendation)."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd
import yfinance as yf

from config.settings import Settings, get_settings

logger = logging.getLogger(__name__)
logging.getLogger("yfinance").setLevel(logging.CRITICAL)


def _round_price(value: float | None) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def _clamp_below_fair_value(
    level: float | None,
    fair_value: float | None,
) -> float | None:
    """Keep buy levels at or below fair value when FV is known."""
    if level is None:
        return None
    if fair_value is not None and fair_value > 0:
        return _round_price(min(level, fair_value))
    return _round_price(level)


def _pct_change(closes: pd.Series, lookback: int) -> float | None:
    if len(closes) <= lookback:
        return None
    end = float(closes.iloc[-1])
    start = float(closes.iloc[-(lookback + 1)])
    if start == 0:
        return None
    return (end - start) / start * 100.0


def _count_gap_downs(
    opens: pd.Series,
    closes: pd.Series,
    *,
    lookback: int,
    gap_pct: float,
) -> int:
    """Count sessions where open gaps down ≥ gap_pct vs prior close."""
    n = len(closes)
    if n < 2:
        return 0
    start_idx = max(1, n - lookback)
    count = 0
    for i in range(start_idx, n):
        prior_close = float(closes.iloc[i - 1])
        open_px = float(opens.iloc[i])
        if prior_close <= 0:
            continue
        gap = (prior_close - open_px) / prior_close * 100.0
        if gap >= gap_pct:
            count += 1
    return count


def classify_timing(
    *,
    gaps_5d: int,
    gaps_20d: int,
    ret_5d: float | None,
    ret_20d: float | None,
    settings: Settings,
) -> tuple[str, str]:
    """Return (timing_status, timing_note)."""
    falling_5d = settings.entry_falling_5d_pct
    falling_20d = settings.entry_falling_20d_pct
    caution_5d = settings.entry_caution_5d_pct

    if gaps_5d > 0 or (
        ret_5d is not None and ret_5d <= falling_5d
    ) or (
        ret_20d is not None and ret_20d <= falling_20d
    ):
        reasons: list[str] = []
        if gaps_5d > 0:
            reasons.append(
                f"gap-down candle(s) in last 5 sessions ({gaps_5d})"
            )
        if ret_5d is not None and ret_5d <= falling_5d:
            reasons.append(f"5d return {ret_5d:.1f}%")
        if ret_20d is not None and ret_20d <= falling_20d:
            reasons.append(f"20d return {ret_20d:.1f}%")
        note = (
            "Falling-knife risk — "
            + "; ".join(reasons)
            + ". Prefer waiting for tranche_2/3 rather than chasing."
        )
        return "falling_knife", note

    if gaps_20d > 0 or (ret_5d is not None and ret_5d <= caution_5d):
        reasons = []
        if gaps_20d > 0:
            reasons.append(
                f"gap-down(s) in last 20 sessions ({gaps_20d})"
            )
        if ret_5d is not None and ret_5d <= caution_5d:
            reasons.append(f"5d return {ret_5d:.1f}%")
        note = (
            "Caution — "
            + "; ".join(reasons)
            + ". Scale in via tranche_2/3 if still interested."
        )
        return "caution", note

    return (
        "calm",
        "Price action looks calm vs recent history — tranche_1 at current "
        "price is reasonable as a first scale-in.",
    )


def build_entry_plan_from_ohlc(
    *,
    price: float,
    fair_value: float | None,
    fifty_two_week_low: float | None,
    opens: pd.Series,
    lows: pd.Series,
    closes: pd.Series,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Pure math entry plan from OHLC series (no network)."""
    settings = settings or get_settings()
    gap_pct = settings.entry_gap_pct

    gaps_5d = _count_gap_downs(opens, closes, lookback=5, gap_pct=gap_pct)
    gaps_20d = _count_gap_downs(opens, closes, lookback=20, gap_pct=gap_pct)
    ret_5d = _pct_change(closes, 5)
    ret_20d = _pct_change(closes, 20)

    recent_20d_low: float | None = None
    if len(lows) > 0:
        window = lows.iloc[-min(20, len(lows)) :]
        recent_20d_low = float(window.min())

    timing_status, timing_note = classify_timing(
        gaps_5d=gaps_5d,
        gaps_20d=gaps_20d,
        ret_5d=ret_5d,
        ret_20d=ret_20d,
        settings=settings,
    )

    # Tranche levels
    if timing_status == "calm":
        tranche_1: float | None = price
        tranche_1_action = "buy"
    else:
        tranche_1 = None
        tranche_1_action = "wait"

    tranche_2_raw = price * 0.95
    if recent_20d_low is not None:
        tranche_2_raw = min(tranche_2_raw, recent_20d_low)

    if fifty_two_week_low is not None and fifty_two_week_low > 0:
        mid = (price + fifty_two_week_low) / 2.0
        near_low = fifty_two_week_low * 1.02
        tranche_3_raw = min(price * 0.90, mid, near_low)
        invalidation_raw = fifty_two_week_low * 0.97
    elif recent_20d_low is not None:
        tranche_3_raw = min(price * 0.90, recent_20d_low)
        invalidation_raw = recent_20d_low * 0.97
    else:
        tranche_3_raw = price * 0.90
        invalidation_raw = price * 0.85

    tranche_1 = _clamp_below_fair_value(tranche_1, fair_value)
    tranche_2 = _clamp_below_fair_value(tranche_2_raw, fair_value)
    tranche_3 = _clamp_below_fair_value(tranche_3_raw, fair_value)
    invalidation = _round_price(invalidation_raw)

    # Ensure tranche ordering when all present: t1 >= t2 >= t3 (buy lower deeper)
    levels = [x for x in (tranche_1, tranche_2, tranche_3) if x is not None]
    if len(levels) >= 2 and tranche_2 is not None and tranche_3 is not None:
        if tranche_3 > tranche_2:
            tranche_3 = tranche_2

    return {
        "timing_status": timing_status,
        "timing_note": timing_note,
        "gap_downs_5d": gaps_5d,
        "gap_downs_20d": gaps_20d,
        "return_5d_pct": round(ret_5d, 2) if ret_5d is not None else None,
        "return_20d_pct": round(ret_20d, 2) if ret_20d is not None else None,
        "recent_20d_low": _round_price(recent_20d_low),
        "fifty_two_week_low": _round_price(fifty_two_week_low),
        "tranche_1": tranche_1,
        "tranche_1_action": tranche_1_action,
        "tranche_2": tranche_2,
        "tranche_3": tranche_3,
        "invalidation": invalidation,
        "source": "ohlc",
    }


def _fallback_entry_plan(
    *,
    price: float,
    fair_value: float | None,
    fifty_two_week_low: float | None,
    reason: str,
) -> dict[str, Any]:
    """MoS-only zones when history is unavailable."""
    t1 = _clamp_below_fair_value(price, fair_value)
    t2 = _clamp_below_fair_value(price * 0.95, fair_value)
    t3 = _clamp_below_fair_value(price * 0.90, fair_value)
    if fifty_two_week_low is not None and fifty_two_week_low > 0:
        inv = _round_price(fifty_two_week_low * 0.97)
    else:
        inv = _round_price(price * 0.85)
    return {
        "timing_status": "unknown",
        "timing_note": (
            f"Could not load recent OHLC ({reason}). "
            "Showing mechanical MoS scale-in zones only."
        ),
        "gap_downs_5d": None,
        "gap_downs_20d": None,
        "return_5d_pct": None,
        "return_20d_pct": None,
        "recent_20d_low": None,
        "fifty_two_week_low": _round_price(fifty_two_week_low),
        "tranche_1": t1,
        "tranche_1_action": "buy",
        "tranche_2": t2,
        "tranche_3": t3,
        "invalidation": inv,
        "source": "fallback",
    }


def fetch_ohlc(ticker: str, period: str = "3mo") -> pd.DataFrame | None:
    """Fetch OHLC history; return None on failure / empty."""
    try:
        hist = yf.Ticker(ticker).history(period=period, auto_adjust=False)
        if hist is None or hist.empty:
            return None
        needed = {"Open", "High", "Low", "Close"}
        if not needed.issubset(set(hist.columns)):
            return None
        return hist
    except Exception as exc:  # noqa: BLE001
        logger.warning("OHLC fetch failed for %s: %s", ticker, exc)
        return None


def build_entry_plan_for_alert(
    alert: dict[str, Any],
    settings: Settings | None = None,
    *,
    screen_metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build entry_plan for one ALERT (soft-fail to fallback)."""
    settings = settings or get_settings()
    ticker = str(alert.get("ticker") or "")
    price = float(alert.get("current_price") or 0)
    fair_value = alert.get("fair_value_estimate")
    try:
        fv = float(fair_value) if fair_value is not None else None
    except (TypeError, ValueError):
        fv = None

    meta = alert.get("_meta") or {}
    metrics = screen_metrics or meta.get("screen_metrics") or {}
    # 52w low may live on candidate metrics or alert itself
    low_52 = (
        alert.get("fifty_two_week_low")
        or metrics.get("fifty_two_week_low")
    )
    try:
        low_52_f = float(low_52) if low_52 is not None else None
    except (TypeError, ValueError):
        low_52_f = None

    if price <= 0:
        return _fallback_entry_plan(
            price=0.0,
            fair_value=fv,
            fifty_two_week_low=low_52_f,
            reason="missing price",
        )

    hist = fetch_ohlc(ticker) if ticker else None
    if hist is None:
        return _fallback_entry_plan(
            price=price,
            fair_value=fv,
            fifty_two_week_low=low_52_f,
            reason="history unavailable",
        )

    return build_entry_plan_from_ohlc(
        price=price,
        fair_value=fv,
        fifty_two_week_low=low_52_f,
        opens=hist["Open"],
        lows=hist["Low"],
        closes=hist["Close"],
        settings=settings,
    )


def enrich_alerts_with_entry_plan(
    alerts: list[dict[str, Any]],
    settings: Settings | None = None,
    *,
    candidates: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Attach entry_plan to each alert; never changes recommendation."""
    settings = settings or get_settings()
    by_ticker: dict[str, dict[str, Any]] = {}
    for c in candidates or []:
        t = c.get("ticker")
        if t:
            by_ticker[str(t)] = c

    for alert in alerts:
        ticker = str(alert.get("ticker") or "")
        candidate = by_ticker.get(ticker, {})
        # Prefer 52w low from screener candidate when present
        if candidate.get("fifty_two_week_low") is not None:
            alert.setdefault(
                "fifty_two_week_low",
                candidate.get("fifty_two_week_low"),
            )
        try:
            plan = build_entry_plan_for_alert(alert, settings)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "entry_plan failed for %s: %s — using fallback",
                ticker,
                exc,
            )
            price = float(alert.get("current_price") or 0)
            fv = alert.get("fair_value_estimate")
            try:
                fv_f = float(fv) if fv is not None else None
            except (TypeError, ValueError):
                fv_f = None
            plan = _fallback_entry_plan(
                price=price,
                fair_value=fv_f,
                fifty_two_week_low=alert.get("fifty_two_week_low"),
                reason=str(exc),
            )
        alert["entry_plan"] = plan
        logger.info(
            "Entry plan %s -> %s (t1=%s t2=%s t3=%s)",
            ticker,
            plan.get("timing_status"),
            plan.get("tranche_1"),
            plan.get("tranche_2"),
            plan.get("tranche_3"),
        )
    return alerts
