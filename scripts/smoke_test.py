"""Quick smoke test for parsers/validators/entry zones (no network)."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import Settings
from entry_timing import build_entry_plan_from_ohlc, classify_timing
from llm.openrouter_client import extract_json_object
from schemas.signal_schema import validate_analysis_result, validate_macro_result


def _fake_settings(**overrides: float) -> Settings:
    base = dict(
        openrouter_api_key="test",
        entry_gap_pct=2.0,
        entry_falling_5d_pct=-8.0,
        entry_falling_20d_pct=-15.0,
        entry_caution_5d_pct=-4.0,
    )
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def test_entry_plan_falling_knife_and_zones() -> None:
    """Synthetic OHLC: gap-down + drop → falling_knife; zones ordered."""
    # 25 sessions: flat, then gap down and slide
    n = 25
    closes = [100.0] * (n - 6) + [100.0, 95.0, 92.0, 90.0, 88.0, 85.0]
    opens = [100.0] * (n - 5) + [97.0, 94.0, 91.0, 89.0, 86.0]  # gap vs prior
    # Force a clear ≥2% gap on last day: prior close 88, open 85.5
    opens[-1] = 85.5
    closes[-2] = 88.0
    closes[-1] = 84.0
    lows = [c - 1 for c in closes]
    opens_s = pd.Series(opens)
    lows_s = pd.Series(lows)
    closes_s = pd.Series(closes)

    settings = _fake_settings()
    status, note = classify_timing(
        gaps_5d=1,
        gaps_20d=1,
        ret_5d=-10.0,
        ret_20d=-12.0,
        settings=settings,
    )
    assert status == "falling_knife"
    assert "Gap-down" in note or "gap-down" in note or "Falling" in note

    plan = build_entry_plan_from_ohlc(
        price=84.0,
        fair_value=120.0,
        fifty_two_week_low=70.0,
        opens=opens_s,
        lows=lows_s,
        closes=closes_s,
        settings=settings,
    )
    assert plan["timing_status"] == "falling_knife"
    assert plan["tranche_1"] is None
    assert plan["tranche_1_action"] == "wait"
    assert plan["tranche_2"] is not None
    assert plan["tranche_3"] is not None
    assert plan["invalidation"] == round(70.0 * 0.97, 2)
    assert plan["tranche_2"] <= 84.0
    assert plan["tranche_3"] <= plan["tranche_2"]
    assert plan["source"] == "ohlc"


def test_entry_plan_calm() -> None:
    closes = pd.Series([100.0 + (i % 3) * 0.2 for i in range(30)])
    opens = closes.copy()
    lows = closes - 0.5
    settings = _fake_settings()
    plan = build_entry_plan_from_ohlc(
        price=float(closes.iloc[-1]),
        fair_value=150.0,
        fifty_two_week_low=80.0,
        opens=opens,
        lows=lows,
        closes=closes,
        settings=settings,
    )
    assert plan["timing_status"] == "calm"
    assert plan["tranche_1_action"] == "buy"
    assert plan["tranche_1"] is not None


def main() -> None:
    obj = extract_json_object('Here:\n```json\n{"a": 1, "b": "x"}\n```\n')
    assert obj == {"a": 1, "b": "x"}

    macro = validate_macro_result(
        {
            "macro_summary": "Soft landing narrative",
            "selected_sectors": [
                {
                    "sector_key": "semiconductors",
                    "sector_name": "Semiconductors",
                    "thesis": "AI capex cycle",
                    "confidence": 0.8,
                }
            ],
        }
    )
    assert len(macro["selected_sectors"]) == 1

    analysis = validate_analysis_result(
        {
            "ticker": "AAPL",
            "company_name": "Apple",
            "fair_value_estimate": 200,
            "margin_of_safety_pct": 25,
            "moat_assessment": {"score": 7, "summary": "brand", "moat_types": ["brand"]},
            "management_red_flags": {
                "has_red_flags": False,
                "summary": "ok",
                "flags": [],
            },
            "investment_memo": "memo",
            "recommendation": "ALERT",
            "passes_margin_of_safety": True,
        }
    )
    assert analysis["recommendation"] == "ALERT"

    test_entry_plan_falling_knife_and_zones()
    test_entry_plan_calm()
    print("smoke_ok")


if __name__ == "__main__":
    main()
