#!/usr/bin/env python3
"""
Value Investing Alert System — weekly pipeline orchestrator.

Pipeline:
  1. macro_scanner      → 1–2 bullish sectors (LLM)
  2. fundamental_screener → hard P/E, D/E, ROE filters (pure Python)
  3. value_analyst      → moat / fair value / MoS (LLM)
  4. entry_timing       → soft-guide buy zones (never changes ALERT)
  5. email_notifier     → HTML memo + embedded JSON (only on strong MoS)

Usage:
  python main.py --market USA
  python main.py --market India --force-digest
  python main.py India --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.sector_universe import Market, market_label, normalize_market
from config.settings import get_settings
from email_notifier import send_alert_email
from entry_timing import enrich_alerts_with_entry_plan
from fundamental_screener import flatten_passed_candidates, screen_sectors
from llm.openrouter_client import OpenRouterClient, OpenRouterError
from macro_scanner import scan_macro_sectors
from value_analyst import analyze_candidates, select_alerts

logger = logging.getLogger("value_alert")


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _write_artifact(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    logger.info("Wrote artifact %s", path)


def run_pipeline(
    *,
    market: Market | str = "usa",
    force_digest: bool = False,
) -> dict[str, Any]:
    settings = get_settings()
    problems = settings.validate()
    if problems and not settings.dry_run:
        raise RuntimeError("Configuration errors:\n- " + "\n- ".join(problems))
    if problems and settings.dry_run:
        logger.warning("DRY_RUN with config issues: %s", problems)

    m = normalize_market(market)
    label = market_label(m)

    run_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + f"-{m}-"
        + uuid.uuid4().hex[:8]
    )
    artifact_dir = Path(os.getenv("ARTIFACT_DIR", "artifacts")) / run_id
    client = OpenRouterClient(settings)
    meta: dict[str, Any] = {"run_id": run_id, "market": m, "market_label": label, "steps": {}}

    logger.info("=== Value Investing Alert run %s [%s] ===", run_id, label)

    # --- Step 1: Macro ---
    try:
        macro = scan_macro_sectors(client=client, settings=settings, market=m)
        meta["steps"]["macro"] = "ok"
        _write_artifact(artifact_dir / "macro.json", macro)
    except (OpenRouterError, ValueError, Exception) as exc:
        meta["steps"]["macro"] = f"failed: {exc}"
        logger.error("Macro scan failed: %s", exc)
        raise

    sector_keys = [s["sector_key"] for s in macro.get("selected_sectors", [])]
    if not sector_keys:
        raise RuntimeError("Macro scanner returned zero sectors")

    # --- Step 2: Fundamentals ---
    try:
        screen_results = screen_sectors(sector_keys, settings=settings, market=m)
        candidates = flatten_passed_candidates(
            screen_results,
            limit=settings.max_analyst_candidates,
        )
        meta["steps"]["screen"] = {
            "status": "ok",
            "passed_total": sum(len(b.get("passed") or []) for b in screen_results),
            "analyzed_pool": len(candidates),
        }
        _write_artifact(
            artifact_dir / "screen.json",
            {"market": m, "results": screen_results, "candidates": candidates},
        )
    except Exception as exc:
        meta["steps"]["screen"] = f"failed: {exc}"
        logger.error("Screening failed: %s", exc)
        raise

    if not candidates:
        logger.warning(
            "No %s candidates passed hard filters — sending digest if requested",
            label,
        )
        analyses: list[dict[str, Any]] = []
        alerts: list[dict[str, Any]] = []
    else:
        # --- Step 3: Qualitative analyst ---
        try:
            analyses = analyze_candidates(
                candidates,
                macro=macro,
                client=client,
                settings=settings,
            )
            alerts = select_alerts(analyses, settings=settings)
            alerts = enrich_alerts_with_entry_plan(
                alerts,
                settings=settings,
                candidates=candidates,
            )
            meta["steps"]["analyst"] = {
                "status": "ok",
                "analyzed": len(analyses),
                "alerts": len(alerts),
            }
            meta["steps"]["entry_timing"] = {
                "status": "ok",
                "enriched": len(alerts),
            }
            _write_artifact(
                artifact_dir / "analyses.json",
                {"market": m, "analyses": analyses, "alerts": alerts},
            )
        except Exception as exc:
            meta["steps"]["analyst"] = f"failed: {exc}"
            logger.error("Analyst step failed: %s", exc)
            raise

    # --- Step 4: Email ---
    digest = force_digest or os.getenv("DIGEST_WHEN_EMPTY", "false").lower() in {
        "1",
        "true",
        "yes",
    }
    try:
        mail_result = send_alert_email(
            macro=macro,
            screened_candidates=candidates if candidates else [],
            analyses=analyses,
            alerts=alerts,
            run_id=run_id,
            settings=settings,
            force_digest=digest,
            meta=meta,
        )
        meta["steps"]["email"] = {
            "status": "ok",
            "sent": mail_result.get("sent"),
            "reason": mail_result.get("reason"),
            "subject": mail_result.get("subject"),
        }
        _write_artifact(artifact_dir / "signal.json", mail_result.get("signal"))
    except Exception as exc:
        meta["steps"]["email"] = f"failed: {exc}"
        logger.error("Email step failed: %s", exc)
        raise

    summary = {
        "run_id": run_id,
        "market": m,
        "market_label": label,
        "sectors": sector_keys,
        "candidates": [c.get("ticker") for c in (candidates or [])],
        "alerts": [a.get("ticker") for a in alerts],
        "email_sent": mail_result.get("sent"),
        "meta": meta,
    }
    _write_artifact(artifact_dir / "summary.json", summary)
    logger.info(
        "Run complete [%s]. alerts=%s email_sent=%s",
        label,
        summary["alerts"],
        summary["email_sent"],
    )
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Weekly Value Investing Alert pipeline (USA or India)"
    )
    parser.add_argument(
        "market_positional",
        nargs="?",
        default=None,
        help="Optional positional market: USA or India",
    )
    parser.add_argument(
        "--market",
        "-m",
        default=None,
        help="Target market: USA or India (aliases: US, IN). Default: USA",
    )
    parser.add_argument(
        "--force-digest",
        action="store_true",
        help="Email a digest even when no MoS alerts are found",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip outbound email (still runs scan/analysis)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.dry_run:
        os.environ["DRY_RUN"] = "true"
        get_settings.cache_clear()

    raw_market = args.market or args.market_positional or os.getenv("MARKET", "USA")
    try:
        market = normalize_market(raw_market)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    settings = get_settings()
    setup_logging(settings.log_level)

    try:
        run_pipeline(market=market, force_digest=args.force_digest)
        return 0
    except Exception:
        logger.error("Pipeline failed:\n%s", traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
