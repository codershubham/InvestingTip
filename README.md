# Value Investing Alert System

Automated **long-term value investing** scanner that runs weekly on GitHub Actions, uses **OpenRouter free models** for macro + qualitative analysis, applies **hard fundamental filters in Python**, and emails you an HTML memo + embedded JSON signal via **Resend or SMTP**.

> Research automation only — not investment advice.

## Architecture

```
Sunday cron (GitHub Actions)
  India: 8:00 PM IST · USA: 6:00 PM ET
        │
        ▼
┌───────────────────┐
│  macro_scanner    │  RSS + index snapshot → LLM picks 1–2 sectors
└─────────┬─────────┘
          ▼
┌───────────────────┐
│ fundamental_      │  yfinance math: P/E < sector avg, D/E < 0.5, ROE > 15%
│ screener          │
└─────────┬─────────┘
          ▼
┌───────────────────┐
│  value_analyst    │  LLM: moat, governance, fair value, margin of safety
└─────────┬─────────┘
          ▼
┌───────────────────┐
│  entry_timing     │  Soft-guide buy zones (gap-down / drawdown) — never blocks ALERT
└─────────┬─────────┘
          ▼
┌───────────────────┐
│  email_notifier   │  HTML memo + entry plan + <script type="application/json"> signal
└───────────────────┘
```

Alert email is sent **only** when a stock clears screens and offers a strong margin of safety (default ≥ 20%), unless you enable digest mode. Each ALERT includes mechanical **buy zones** (tranche 1–3 + invalidation) and a timing note when recent price action looks extended or gap-heavy.

## Project layout

```
InvestingTip/
├── main.py                      # Orchestrator
├── macro_scanner.py
├── fundamental_screener.py
├── value_analyst.py
├── entry_timing.py              # Soft-guide buy zones on ALERTs
├── email_notifier.py
├── config/
│   ├── settings.py
│   └── sector_universe.py       # Curated sector → ticker map
├── llm/
│   └── openrouter_client.py     # Free-model fallback + 429 handling
├── prompts/
│   └── __init__.py              # Strict JSON system prompts
├── schemas/
│   └── signal_schema.py
├── .github/workflows/
│   ├── value_scan_reusable.yml  # Shared scan job
│   ├── weekly_india_scan.yml    # Sunday 8:00 PM IST
│   ├── weekly_usa_scan.yml      # Sunday 6:00 PM ET
│   └── weekly_value_scan.yml    # Manual USA/India/both
├── requirements.txt
└── .env.example
```

## Setup

### 1. Clone & install

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

### 2. Fill `.env`

| Variable | Purpose |
|---|---|
| `OPENROUTER_API_KEY` | Free-tier key from [openrouter.ai](https://openrouter.ai) |
| `EMAIL_TO` / `EMAIL_FROM` | Recipient + verified sender |
| `RESEND_API_KEY` | Preferred email path ([resend.com](https://resend.com) free tier) |
| `SMTP_*` | Alternative to Resend (e.g. Gmail app password) |

### 3. Local dry run

```bash
# USA market, skip email
python main.py --market USA --dry-run --force-digest

# India market (NSE .NS tickers + India news)
python main.py --market India --dry-run --force-digest

# Positional form also works
python main.py India --dry-run
```

### 4. GitHub Actions secrets

Repo → **Settings → Secrets and variables → Actions**. Add at least:

- `OPENROUTER_API_KEY`
- `EMAIL_TO`
- `EMAIL_FROM`
- `RESEND_API_KEY` **or** `SMTP_USER` + `SMTP_PASSWORD` (+ optional `SMTP_HOST` / `SMTP_PORT`)

Optional secret: `OPENROUTER_MODELS` (comma-separated free model IDs).

Workflow runs:

| Workflow | When | Market |
|---|---|---|
| **Weekly India Value Scan** | Sunday **8:00 PM IST** (`30 14 * * 0` UTC) | India only |
| **Weekly USA Value Scan** | Sunday **6:00 PM ET** (`0 23 * * 0` UTC; ≈7 PM during EDT) | USA only |
| **Manual Value Investing Scan** | On demand | USA / India / both |

Manual: Actions → pick a workflow → **Run workflow**.

Artifacts under `artifacts/` are uploaded for each run.

## Screening rules

| Filter | Default |
|---|---|
| Trailing P/E | **&lt;** sector peer average |
| Debt / Equity | **&lt;** 0.5 |
| ROE | **&gt;** 15% |
| Margin of Safety (ALERT) | **≥** 20%, moat ≥ 5, no severe red flags |

ALERT emails also include a **soft entry plan** (does not change recommendation):

| Timing | Meaning |
|---|---|
| Calm | Tranche 1 ≈ current price OK as first scale-in |
| Caution / Falling knife | Prefer tranche 2–3; gap-down or steep drawdown detected |

Optional env: `ENTRY_GAP_PCT`, `ENTRY_FALLING_5D_PCT`, `ENTRY_FALLING_20D_PCT`, `ENTRY_CAUTION_5D_PCT`.

## OpenRouter fallback

Model selection is **ordered, not random**:

| Task | Prefers first | Then falls back to |
|---|---|---|
| Macro sector pick | faster JSON models (`ling-3.0-flash`, Nemotron Super, …) | shared `OPENROUTER_MODELS` |
| Value analyst | stronger reasoning (`Nemotron Ultra`, Super, …) | shared `OPENROUTER_MODELS` |

On `429` / `5xx` / timeout / empty response, the client rotates to the **next** model in that list.

Override via env:
- `OPENROUTER_MODELS` — shared fallback chain
- `OPENROUTER_MODELS_MACRO` / `OPENROUTER_MODELS_ANALYST` — optional task lists

## Email payload

Each email includes:

1. Human-readable **Value Investment Memo** (sector thesis, moat, financials, risks, suggested entry plan)
2. Embedded:

```html
<script type="application/json" id="value-signal">
{ ... schema_version 1.1.0, macro, screened_candidates, analyses, alerts (with entry_plan) ... }
</script>
```

Ready to parse later when you add a database (Phase 2).

## Notes

- Expand tickers in `config/sector_universe.py`.
- Free Yahoo / RSS data can be incomplete — missing fields fail closed (stock rejected).
- Free LLM endpoints can be slow or rate-limited on Sundays; fallbacks mitigate this.
- Set `DIGEST_WHEN_EMPTY=true` (or `--force-digest`) if you want a weekly email even with zero alerts.
