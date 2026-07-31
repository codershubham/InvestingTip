from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import get_settings
from fundamental_screener import BANK_LIKE_SECTORS
from llm.openrouter_client import extract_json_object

get_settings.cache_clear()
s = get_settings()
truncated = '{"ticker":"X","moat_assessment":{"score":6'
repaired = extract_json_object(truncated)
assert repaired["ticker"] == "X"
assert repaired["moat_assessment"]["score"] == 6
print("repair_ok")
print("analyst_first", s.models_for_task("analyst")[0])
print("banks", sorted(BANK_LIKE_SECTORS))
