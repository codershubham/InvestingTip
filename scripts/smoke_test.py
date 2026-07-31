"""Quick smoke test for parsers/validators (no network)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from llm.openrouter_client import extract_json_object
from schemas.signal_schema import validate_analysis_result, validate_macro_result


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
    print("smoke_ok")


if __name__ == "__main__":
    main()
