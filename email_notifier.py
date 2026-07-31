"""HTML email notifier via Resend HTTP API or SMTP (Gmail-compatible)."""

from __future__ import annotations

import json
import logging
import smtplib
import ssl
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape
from typing import Any

import requests

from config.settings import Settings, get_settings

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "1.0.0"


def build_signal_payload(
    *,
    macro: dict[str, Any],
    screened_candidates: list[dict[str, Any]],
    analyses: list[dict[str, Any]],
    alerts: list[dict[str, Any]],
    run_id: str,
    meta: dict[str, Any] | None = None,
    market: str | None = None,
) -> dict[str, Any]:
    """Phase-2-ready structured signal embedded in the email."""
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "market": market or macro.get("market") or "usa",
        "market_label": macro.get("market_label"),
        "philosophy": "long_term_value_investing",
        "macro": {
            k: v
            for k, v in macro.items()
            if not str(k).startswith("_")
        },
        "screened_candidates": [
            {
                "ticker": c.get("ticker"),
                "company_name": c.get("company_name"),
                "sector_key": c.get("sector_key"),
                "trailing_pe": c.get("trailing_pe"),
                "sector_avg_pe": c.get("sector_avg_pe"),
                "debt_to_equity": c.get("debt_to_equity"),
                "roe_pct": c.get("roe_pct"),
                "current_price": c.get("current_price"),
                "market_cap": c.get("market_cap"),
            }
            for c in screened_candidates
        ],
        "analyses": [
            {k: v for k, v in a.items() if not str(k).startswith("_")}
            for a in analyses
        ],
        "alerts": [
            {k: v for k, v in a.items() if not str(k).startswith("_")}
            for a in alerts
        ],
        "meta": meta or {},
    }


def _memo_section(alert: dict[str, Any]) -> str:
    ticker = escape(str(alert.get("ticker", "")))
    name = escape(str(alert.get("company_name", "")))
    mos = alert.get("margin_of_safety_pct")
    fv = alert.get("fair_value_estimate")
    px = alert.get("current_price")
    moat = alert.get("moat_assessment") or {}
    flags = alert.get("management_red_flags") or {}
    risks = alert.get("key_risks") or []
    risk_html = "".join(f"<li>{escape(str(r))}</li>" for r in risks)
    memo = escape(str(alert.get("investment_memo", ""))).replace("\n", "<br/>")

    return f"""
    <section style="margin:0 0 28px 0;padding:0 0 20px 0;border-bottom:1px solid #d6d3d1;">
      <h2 style="margin:0 0 8px 0;font-size:20px;color:#1c1917;">
        {ticker} — {name}
      </h2>
      <p style="margin:0 0 12px 0;color:#44403c;font-size:14px;">
        <strong>Margin of Safety:</strong> {escape(str(mos))}% &nbsp;|&nbsp;
        <strong>Fair Value:</strong> {escape(str(fv))} &nbsp;|&nbsp;
        <strong>Price:</strong> {escape(str(px))} &nbsp;|&nbsp;
        <strong>Moat:</strong> {escape(str(moat.get('score', 'n/a')))}/10
      </p>
      <h3 style="margin:16px 0 6px 0;font-size:15px;color:#292524;">Investment Memo</h3>
      <p style="margin:0;line-height:1.55;color:#1c1917;font-size:14px;">{memo}</p>
      <h3 style="margin:16px 0 6px 0;font-size:15px;color:#292524;">Moat</h3>
      <p style="margin:0;line-height:1.5;color:#44403c;font-size:14px;">
        {escape(str(moat.get('summary', '')))}
      </p>
      <h3 style="margin:16px 0 6px 0;font-size:15px;color:#292524;">Financial Summary</h3>
      <p style="margin:0;line-height:1.5;color:#44403c;font-size:14px;">
        {escape(str(alert.get('financial_summary', '')))}
      </p>
      <h3 style="margin:16px 0 6px 0;font-size:15px;color:#292524;">Management / Governance</h3>
      <p style="margin:0;line-height:1.5;color:#44403c;font-size:14px;">
        {escape(str(flags.get('summary', '')))}
        (promoter pledge risk: {escape(str(flags.get('promoter_pledge_risk', 'unknown')))})
      </p>
      <h3 style="margin:16px 0 6px 0;font-size:15px;color:#292524;">Key Risks</h3>
      <ul style="margin:0;padding-left:18px;color:#44403c;font-size:14px;line-height:1.5;">
        {risk_html or '<li>None listed</li>'}
      </ul>
    </section>
    """


def render_html_email(
    *,
    signal: dict[str, Any],
    alerts: list[dict[str, Any]],
    macro: dict[str, Any],
    no_alert_digest: bool = False,
) -> str:
    """Build polished HTML with readable memo + embedded JSON signal."""
    generated = escape(str(signal.get("generated_at", "")))
    m_label = escape(
        str(signal.get("market_label") or macro.get("market_label") or "USA")
    )
    sectors = macro.get("selected_sectors") or []
    sector_bits = []
    for s in sectors:
        sector_bits.append(
            f"<li><strong>{escape(str(s.get('sector_name', s.get('sector_key'))))}</strong>: "
            f"{escape(str(s.get('thesis', '')))}</li>"
        )
    sector_html = "".join(sector_bits) or "<li>No sectors selected</li>"
    macro_summary = escape(str(macro.get("macro_summary", "")))

    if no_alert_digest or not alerts:
        body_title = f"{m_label} Weekly Value Scan — No Margin-of-Safety Alerts"
        body_intro = (
            "The pipeline completed successfully, but no stocks cleared the "
            "hard screens <em>and</em> offered a strong margin of safety. "
            "Sector thesis and JSON payload are included for your records."
        )
        memos = (
            "<p style='color:#78716c;font-size:14px;'>"
            "No ALERT memos this week.</p>"
        )
    else:
        body_title = f"{m_label} Value Alert — {len(alerts)} Margin-of-Safety Signal(s)"
        body_intro = (
            "The following names passed quantitative value screens and "
            "qualitative analysis with a strong estimated margin of safety. "
            "This is research automation, not personalized investment advice."
        )
        memos = "".join(_memo_section(a) for a in alerts)

    json_blob = escape(json.dumps(signal, indent=2, default=str))

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>{escape(body_title)}</title>
</head>
<body style="margin:0;padding:0;background:#f5f5f4;font-family:Georgia,'Times New Roman',serif;">
  <div style="max-width:720px;margin:24px auto;background:#fffaf5;border:1px solid #e7e5e4;padding:28px 32px;">
    <p style="margin:0 0 4px 0;letter-spacing:0.08em;text-transform:uppercase;font-size:11px;color:#a8a29e;">
      Value Investing Alert System · {m_label}
    </p>
    <h1 style="margin:0 0 8px 0;font-size:26px;color:#1c1917;font-weight:normal;">
      {escape(body_title)}
    </h1>
    <p style="margin:0 0 20px 0;color:#78716c;font-size:13px;">Generated (UTC): {generated}</p>
    <p style="margin:0 0 22px 0;line-height:1.55;color:#44403c;font-size:15px;">{body_intro}</p>

    <h2 style="margin:0 0 8px 0;font-size:18px;color:#1c1917;">Sector Thesis</h2>
    <p style="margin:0 0 10px 0;line-height:1.5;color:#44403c;font-size:14px;">{macro_summary}</p>
    <ul style="margin:0 0 24px 0;padding-left:18px;color:#44403c;font-size:14px;line-height:1.55;">
      {sector_html}
    </ul>

    {memos}

    <p style="margin:24px 0 8px 0;font-size:12px;color:#a8a29e;">
      Embedded machine-readable signal (Phase 2 ready). Do not reply to parse — extract the JSON block below.
    </p>
    <script type="application/json" id="value-signal">
{json.dumps(signal, indent=2, default=str)}
    </script>
    <!-- Fallback visible JSON for clients that strip script tags -->
    <pre style="display:none">{json_blob}</pre>
    <details style="margin-top:12px;">
      <summary style="cursor:pointer;color:#57534e;font-size:13px;">View raw JSON signal</summary>
      <pre style="white-space:pre-wrap;word-break:break-word;background:#1c1917;color:#fafaf9;padding:14px;font-size:11px;line-height:1.4;overflow:auto;">{json_blob}</pre>
    </details>

    <p style="margin:28px 0 0 0;font-size:11px;color:#a8a29e;line-height:1.45;">
      Disclaimer: Automated research only. Not investment advice. Verify all figures
      independently before making capital allocation decisions. Past performance and
      model estimates are not guarantees of future results.
    </p>
  </div>
</body>
</html>"""


def _subject_line(
    alerts: list[dict[str, Any]],
    run_id: str,
    market_label_str: str = "USA",
) -> str:
    prefix = f"[{market_label_str}]"
    if not alerts:
        return f"{prefix} Value Scan — No MoS alerts — {run_id}"
    tickers = ", ".join(str(a.get("ticker")) for a in alerts[:4])
    more = "" if len(alerts) <= 4 else f" +{len(alerts) - 4}"
    return f"{prefix} Value Alert — {tickers}{more} — MoS qualified"


def send_via_resend(
    *,
    settings: Settings,
    subject: str,
    html: str,
) -> None:
    resp = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {settings.resend_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "from": settings.email_from,
            "to": [settings.email_to],
            "subject": subject,
            "html": html,
        },
        timeout=45,
    )
    if resp.status_code >= 300:
        raise RuntimeError(f"Resend API error {resp.status_code}: {resp.text[:500]}")
    logger.info("Email sent via Resend: %s", resp.json())


def send_via_smtp(
    *,
    settings: Settings,
    subject: str,
    html: str,
) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.email_from
    msg["To"] = settings.email_to
    msg.attach(MIMEText(html, "html", "utf-8"))

    context = ssl.create_default_context()
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=45) as server:
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
        server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(settings.email_from, [settings.email_to], msg.as_string())
    logger.info("Email sent via SMTP to %s", settings.email_to)


def send_alert_email(
    *,
    macro: dict[str, Any],
    screened_candidates: list[dict[str, Any]],
    analyses: list[dict[str, Any]],
    alerts: list[dict[str, Any]],
    run_id: str,
    settings: Settings | None = None,
    force_digest: bool = False,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Format + send email.

    By default sends only when there are ALERT-quality names.
    Set force_digest=True (or env DIGEST_WHEN_EMPTY) to always email a weekly digest.
    """
    settings = settings or get_settings()
    m_label = str(macro.get("market_label") or "USA")
    signal = build_signal_payload(
        macro=macro,
        screened_candidates=screened_candidates,
        analyses=analyses,
        alerts=alerts,
        run_id=run_id,
        meta=meta,
        market=macro.get("market"),
    )

    if not alerts and not force_digest:
        logger.info("No alerts and force_digest=False — skipping email send")
        return {"sent": False, "reason": "no_alerts", "signal": signal}

    html = render_html_email(
        signal=signal,
        alerts=alerts,
        macro=macro,
        no_alert_digest=not alerts,
    )
    subject = _subject_line(alerts, run_id, market_label_str=m_label)

    if settings.dry_run:
        logger.info("DRY_RUN=1 — email not sent. Subject: %s", subject)
        return {"sent": False, "reason": "dry_run", "subject": subject, "signal": signal}

    if settings.resend_api_key:
        send_via_resend(settings=settings, subject=subject, html=html)
    else:
        send_via_smtp(settings=settings, subject=subject, html=html)

    return {"sent": True, "subject": subject, "signal": signal}
