"""JSON schemas and lightweight validators for LLM / pipeline outputs."""

from __future__ import annotations

from typing import Any


MACRO_SECTOR_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["horizon_months", "selected_sectors", "macro_summary"],
    "properties": {
        "horizon_months": {"type": "integer", "minimum": 12, "maximum": 36},
        "macro_summary": {"type": "string"},
        "selected_sectors": {
            "type": "array",
            "minItems": 1,
            "maxItems": 2,
            "items": {
                "type": "object",
                "required": [
                    "sector_key",
                    "sector_name",
                    "thesis",
                    "catalysts",
                    "confidence",
                ],
                "properties": {
                    "sector_key": {"type": "string"},
                    "sector_name": {"type": "string"},
                    "thesis": {"type": "string"},
                    "catalysts": {"type": "array", "items": {"type": "string"}},
                    "risks": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
            },
        },
        "rejected_themes": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
}


ANALYSIS_RESULT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "ticker",
        "company_name",
        "fair_value_estimate",
        "margin_of_safety_pct",
        "moat_assessment",
        "management_red_flags",
        "investment_memo",
        "recommendation",
        "passes_margin_of_safety",
    ],
    "properties": {
        "ticker": {"type": "string"},
        "company_name": {"type": "string"},
        "sector_key": {"type": "string"},
        "fair_value_estimate": {"type": "number"},
        "current_price": {"type": "number"},
        "margin_of_safety_pct": {"type": "number"},
        "passes_margin_of_safety": {"type": "boolean"},
        "moat_assessment": {
            "type": "object",
            "required": ["score", "summary", "moat_types"],
            "properties": {
                "score": {"type": "number", "minimum": 0, "maximum": 10},
                "summary": {"type": "string"},
                "moat_types": {"type": "array", "items": {"type": "string"}},
            },
        },
        "management_red_flags": {
            "type": "object",
            "required": ["has_red_flags", "summary", "flags"],
            "properties": {
                "has_red_flags": {"type": "boolean"},
                "summary": {"type": "string"},
                "flags": {"type": "array", "items": {"type": "string"}},
                "promoter_pledge_risk": {"type": "string"},
            },
        },
        "financial_summary": {"type": "string"},
        "key_risks": {"type": "array", "items": {"type": "string"}},
        "investment_memo": {"type": "string"},
        "recommendation": {
            "type": "string",
            "enum": ["ALERT", "WATCHLIST", "PASS"],
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
}


# Final email-embedded signal (Phase 2 ready).
SIGNAL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "schema_version",
        "generated_at",
        "philosophy",
        "macro",
        "screened_candidates",
        "alerts",
    ],
    "properties": {
        "schema_version": {"type": "string"},
        "generated_at": {"type": "string"},
        "philosophy": {"type": "string"},
        "run_id": {"type": "string"},
        "macro": MACRO_SECTOR_SCHEMA,
        "screened_candidates": {"type": "array"},
        "analyses": {"type": "array"},
        "alerts": {"type": "array"},
        "meta": {"type": "object"},
    },
}


def _require_keys(obj: dict[str, Any], keys: list[str], ctx: str) -> None:
    missing = [k for k in keys if k not in obj]
    if missing:
        raise ValueError(f"{ctx}: missing keys {missing}")


def validate_macro_result(data: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize macro scanner output."""
    if not isinstance(data, dict):
        raise ValueError("macro result must be a JSON object")
    _require_keys(data, ["selected_sectors", "macro_summary"], "macro")
    sectors = data.get("selected_sectors")
    if not isinstance(sectors, list) or not sectors:
        raise ValueError("macro.selected_sectors must be a non-empty list")
    if len(sectors) > 2:
        data["selected_sectors"] = sectors[:2]
    for i, sector in enumerate(data["selected_sectors"]):
        if not isinstance(sector, dict):
            raise ValueError(f"selected_sectors[{i}] must be an object")
        _require_keys(
            sector,
            ["sector_key", "sector_name", "thesis", "confidence"],
            f"selected_sectors[{i}]",
        )
        sector.setdefault("catalysts", [])
        sector.setdefault("risks", [])
        try:
            sector["confidence"] = float(sector["confidence"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"selected_sectors[{i}].confidence invalid") from exc
    data.setdefault("horizon_months", 24)
    data.setdefault("rejected_themes", [])
    return data


def validate_analysis_result(data: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize value analyst output."""
    if not isinstance(data, dict):
        raise ValueError("analysis result must be a JSON object")
    _require_keys(
        data,
        [
            "ticker",
            "company_name",
            "fair_value_estimate",
            "margin_of_safety_pct",
            "moat_assessment",
            "management_red_flags",
            "investment_memo",
            "recommendation",
        ],
        "analysis",
    )
    for numeric in ("fair_value_estimate", "margin_of_safety_pct"):
        try:
            data[numeric] = float(data[numeric])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"analysis.{numeric} must be numeric") from exc

    if "current_price" in data and data["current_price"] is not None:
        data["current_price"] = float(data["current_price"])

    moat = data["moat_assessment"]
    if not isinstance(moat, dict):
        raise ValueError("moat_assessment must be an object")
    moat.setdefault("score", 5)
    moat.setdefault("summary", "")
    moat.setdefault("moat_types", [])
    moat["score"] = float(moat["score"])

    flags = data["management_red_flags"]
    if not isinstance(flags, dict):
        raise ValueError("management_red_flags must be an object")
    flags.setdefault("has_red_flags", False)
    flags.setdefault("summary", "")
    flags.setdefault("flags", [])
    flags.setdefault("promoter_pledge_risk", "unknown")

    rec = str(data["recommendation"]).upper().strip()
    if rec not in {"ALERT", "WATCHLIST", "PASS"}:
        # Infer from margin of safety if model drifts.
        mos = float(data["margin_of_safety_pct"])
        if mos >= 20 and not flags.get("has_red_flags"):
            rec = "ALERT"
        elif mos >= 10:
            rec = "WATCHLIST"
        else:
            rec = "PASS"
    data["recommendation"] = rec

    if "passes_margin_of_safety" not in data:
        data["passes_margin_of_safety"] = (
            float(data["margin_of_safety_pct"]) >= 20 and rec == "ALERT"
        )
    else:
        data["passes_margin_of_safety"] = bool(data["passes_margin_of_safety"])

    data.setdefault("key_risks", [])
    data.setdefault("financial_summary", "")
    data.setdefault("confidence", 0.5)
    try:
        data["confidence"] = float(data["confidence"])
    except (TypeError, ValueError):
        data["confidence"] = 0.5
    return data
