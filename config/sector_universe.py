"""Market-scoped sector → ticker universes for free-data screening.

Markets:
  - usa   → US-listed equities (NYSE/Nasdaq Yahoo tickers)
  - india → NSE equities (Yahoo `.NS` tickers)
"""

from __future__ import annotations

from typing import Literal, TypedDict

Market = Literal["usa", "india"]
SUPPORTED_MARKETS: tuple[Market, ...] = ("usa", "india")


class SectorUniverse(TypedDict):
    name: str
    description: str
    tickers: list[str]


USA_SECTOR_UNIVERSE: dict[str, SectorUniverse] = {
    "semiconductors": {
        "name": "Semiconductors",
        "description": "Chip design, foundries, equipment, and AI accelerators",
        "tickers": [
            "NVDA",
            "AMD",
            "AVGO",
            "TSM",
            "ASML",
            "INTC",
            "QCOM",
            "MU",
            "AMAT",
            "KLAC",
            "LRCX",
            "TXN",
            "ADI",
            "MRVL",
        ],
    },
    "renewable_energy": {
        "name": "Renewable Energy",
        "description": "Solar, wind, grid storage, and clean-power utilities",
        "tickers": [
            "ENPH",
            "SEDG",
            "FSLR",
            "NEE",
            "BE",
            "RUN",
            "CWEN",
            "AES",
            "GEV",
            "VST",
        ],
    },
    "healthcare_biotech": {
        "name": "Healthcare & Biotech",
        "description": "Pharma, biotech platforms, diagnostics, and devices",
        "tickers": [
            "JNJ",
            "UNH",
            "LLY",
            "ABBV",
            "MRK",
            "PFE",
            "AMGN",
            "GILD",
            "TMO",
            "DHR",
            "ISRG",
            "REGN",
            "VRTX",
            "BMY",
        ],
    },
    "financials_banks": {
        "name": "Financials & Banks",
        "description": "Banks, insurers, exchanges, and diversified financials",
        "tickers": [
            "JPM",
            "BAC",
            "WFC",
            "C",
            "GS",
            "MS",
            "BLK",
            "SCHW",
            "AXP",
            "V",
            "MA",
            "PYPL",
            "BRK-B",
        ],
    },
    "industrials_defense": {
        "name": "Industrials & Defense",
        "description": "Aerospace, defense, capital goods, and infrastructure",
        "tickers": [
            "GE",
            "CAT",
            "HON",
            "DE",
            "RTX",
            "LMT",
            "NOC",
            "GD",
            "BA",
            "ETN",
            "EMR",
            "PH",
            "ITW",
        ],
    },
    "consumer_staples": {
        "name": "Consumer Staples",
        "description": "Food, beverage, household, and essential retail brands",
        "tickers": [
            "PG",
            "KO",
            "PEP",
            "COST",
            "WMT",
            "CL",
            "MDLZ",
            "KHC",
            "GIS",
            "UL",
            "PM",
            "MO",
        ],
    },
    "technology_software": {
        "name": "Technology Software",
        "description": "Enterprise software, cloud platforms, and cybersecurity",
        "tickers": [
            "MSFT",
            "ORCL",
            "CRM",
            "ADBE",
            "NOW",
            "INTU",
            "PANW",
            "CRWD",
            "SNOW",
            "DDOG",
            "FTNT",
            "TEAM",
        ],
    },
    "energy_oil_gas": {
        "name": "Energy Oil & Gas",
        "description": "Integrated majors, E&P, midstream, and oilfield services",
        "tickers": [
            "XOM",
            "CVX",
            "COP",
            "EOG",
            "SLB",
            "MPC",
            "PSX",
            "VLO",
            "OXY",
            "HES",
            "WMB",
            "KMI",
        ],
    },
    "materials_mining": {
        "name": "Materials & Mining",
        "description": "Metals, chemicals, and critical minerals supply chains",
        "tickers": [
            "LIN",
            "APD",
            "SHW",
            "ECL",
            "NEM",
            "FCX",
            "SCCO",
            "AA",
            "NUE",
            "STLD",
            "DOW",
            "DD",
        ],
    },
    "utilities": {
        "name": "Utilities",
        "description": "Regulated electric, gas, and multi-utilities",
        "tickers": [
            "NEE",
            "DUK",
            "SO",
            "D",
            "AEP",
            "EXC",
            "SRE",
            "XEL",
            "PEG",
            "ED",
            "WEC",
            "ES",
        ],
    },
    "telecom": {
        "name": "Telecom",
        "description": "Wireless carriers, cable, and communication infrastructure",
        "tickers": [
            "T",
            "VZ",
            "TMUS",
            "CMCSA",
            "CHTR",
            "AMT",
            "CCI",
            "SBAC",
        ],
    },
}


INDIA_SECTOR_UNIVERSE: dict[str, SectorUniverse] = {
    "india_banks_nbfc": {
        "name": "Banks & NBFCs",
        "description": "Private/PSU banks and major non-bank lenders",
        "tickers": [
            "HDFCBANK.NS",
            "ICICIBANK.NS",
            "SBIN.NS",
            "AXISBANK.NS",
            "KOTAKBANK.NS",
            "BAJFINANCE.NS",
            "BAJAJFINSV.NS",
            "INDUSINDBK.NS",
            "BANKBARODA.NS",
            "PNB.NS",
            "CHOLAFIN.NS",
            "PFC.NS",
            "RECLTD.NS",
        ],
    },
    "india_it_software": {
        "name": "IT & Software Services",
        "description": "Indian IT services, products, and digital platforms",
        "tickers": [
            "TCS.NS",
            "INFY.NS",
            "HCLTECH.NS",
            "WIPRO.NS",
            "TECHM.NS",
            "LTTS.NS",
            "PERSISTENT.NS",
            "COFORGE.NS",
            "MPHASIS.NS",
            "OFSS.NS",
            "KPITTECH.NS",
            "TATAELXSI.NS",
        ],
    },
    "india_pharma_healthcare": {
        "name": "Pharma & Healthcare",
        "description": "Pharma, hospitals, and healthcare delivery",
        "tickers": [
            "SUNPHARMA.NS",
            "DRREDDY.NS",
            "CIPLA.NS",
            "DIVISLAB.NS",
            "APOLLOHOSP.NS",
            "AUROPHARMA.NS",
            "LUPIN.NS",
            "TORNTPHARM.NS",
            "BIOCON.NS",
            "LAURUSLABS.NS",
            "MAXHEALTH.NS",
        ],
    },
    "india_energy_oil_gas": {
        "name": "Energy Oil & Gas",
        "description": "Oil marketing, refining, upstream, and gas utilities",
        "tickers": [
            "RELIANCE.NS",
            "ONGC.NS",
            "IOC.NS",
            "BPCL.NS",
            "HPCL.NS",
            "GAIL.NS",
            "PETRONET.NS",
            "IGL.NS",
            "GUJGASLTD.NS",
            "OIL.NS",
        ],
    },
    "india_auto_ancillaries": {
        "name": "Auto & Ancillaries",
        "description": "OEMs and auto component manufacturers",
        "tickers": [
            "TATAMOTORS.NS",
            "M&M.NS",
            "MARUTI.NS",
            "BAJAJ-AUTO.NS",
            "HEROMOTOCO.NS",
            "EICHERMOT.NS",
            "TVSMOTOR.NS",
            "ASHOKLEY.NS",
            "BOSCHLTD.NS",
            "MOTHERSON.NS",
            "BHARATFORG.NS",
        ],
    },
    "india_fmcg_staples": {
        "name": "FMCG & Consumer Staples",
        "description": "Packaged foods, personal care, and staples brands",
        "tickers": [
            "HINDUNILVR.NS",
            "ITC.NS",
            "NESTLEIND.NS",
            "BRITANNIA.NS",
            "DABUR.NS",
            "MARICO.NS",
            "GODREJCP.NS",
            "TATACONSUM.NS",
            "COLPAL.NS",
            "UNITDSPR.NS",
            "VBL.NS",
        ],
    },
    "india_infra_capgoods": {
        "name": "Infrastructure & Capital Goods",
        "description": "Engineering, construction, and industrial capex plays",
        "tickers": [
            "LT.NS",
            "SIEMENS.NS",
            "ABB.NS",
            "BHEL.NS",
            "HAL.NS",
            "BEL.NS",
            "CUMMINSIND.NS",
            "THERMAX.NS",
            "KEI.NS",
            "POLYCAB.NS",
            "IRCTC.NS",
        ],
    },
    "india_metals_mining": {
        "name": "Metals & Mining",
        "description": "Steel, aluminum, zinc, and diversified metals",
        "tickers": [
            "TATASTEEL.NS",
            "JSWSTEEL.NS",
            "HINDALCO.NS",
            "VEDL.NS",
            "JINDALSTEL.NS",
            "NMDC.NS",
            "SAIL.NS",
            "NATIONALUM.NS",
            "HINDZINC.NS",
            "COALINDIA.NS",
        ],
    },
    "india_telecom": {
        "name": "Telecom",
        "description": "Wireless carriers and digital connectivity",
        "tickers": [
            "BHARTIARTL.NS",
            "IDEA.NS",
            "INDUSTOWER.NS",
            "TATACOMM.NS",
            "HFCL.NS",
        ],
    },
    "india_power_utilities": {
        "name": "Power & Utilities",
        "description": "Generation, transmission, and power utilities",
        "tickers": [
            "NTPC.NS",
            "POWERGRID.NS",
            "ADANIPOWER.NS",
            "TATAPOWER.NS",
            "NHPC.NS",
            "SJVN.NS",
            "TORNTPOWER.NS",
            "CESC.NS",
        ],
    },
    "india_cement_realty": {
        "name": "Cement & Realty",
        "description": "Cement manufacturers and large real-estate developers",
        "tickers": [
            "ULTRACEMCO.NS",
            "AMBUJACEM.NS",
            "SHREECEM.NS",
            "DALBHARAT.NS",
            "ACC.NS",
            "DLF.NS",
            "GODREJPROP.NS",
            "OBEROIRLTY.NS",
            "PRESTIGE.NS",
        ],
    },
    "india_chemicals": {
        "name": "Chemicals & Specialty",
        "description": "Specialty chemicals and diversified chemical names",
        "tickers": [
            "PIDILITIND.NS",
            "SRF.NS",
            "AARTIIND.NS",
            "DEEPAKNTR.NS",
            "NAVINFLUOR.NS",
            "ATUL.NS",
            "ALKYLAMINE.NS",
            "CLEAN.NS",
            "TATACHEM.NS",
        ],
    },
}


MARKET_UNIVERSES: dict[Market, dict[str, SectorUniverse]] = {
    "usa": USA_SECTOR_UNIVERSE,
    "india": INDIA_SECTOR_UNIVERSE,
}


# Backward-compatible combined view (prefer get_universe(market) in new code).
SECTOR_UNIVERSE: dict[str, SectorUniverse] = {
    **USA_SECTOR_UNIVERSE,
    **INDIA_SECTOR_UNIVERSE,
}


_USA_ALIASES: dict[str, str] = {
    "semiconductor": "semiconductors",
    "chips": "semiconductors",
    "ai_chips": "semiconductors",
    "renewables": "renewable_energy",
    "clean_energy": "renewable_energy",
    "solar": "renewable_energy",
    "healthcare": "healthcare_biotech",
    "biotech": "healthcare_biotech",
    "pharma": "healthcare_biotech",
    "banks": "financials_banks",
    "financials": "financials_banks",
    "banking": "financials_banks",
    "defense": "industrials_defense",
    "industrials": "industrials_defense",
    "aerospace": "industrials_defense",
    "staples": "consumer_staples",
    "consumer": "consumer_staples",
    "fmcg": "consumer_staples",
    "software": "technology_software",
    "tech": "technology_software",
    "technology": "technology_software",
    "it": "technology_software",
    "cloud": "technology_software",
    "oil": "energy_oil_gas",
    "oil_and_gas": "energy_oil_gas",
    "energy": "energy_oil_gas",
    "mining": "materials_mining",
    "materials": "materials_mining",
    "metals": "materials_mining",
    "utility": "utilities",
    "power": "utilities",
    "telecommunications": "telecom",
    "communication": "telecom",
}

_INDIA_ALIASES: dict[str, str] = {
    "banks": "india_banks_nbfc",
    "banking": "india_banks_nbfc",
    "nbfc": "india_banks_nbfc",
    "financials": "india_banks_nbfc",
    "finance": "india_banks_nbfc",
    "it": "india_it_software",
    "software": "india_it_software",
    "tech": "india_it_software",
    "technology": "india_it_software",
    "information_technology": "india_it_software",
    "pharma": "india_pharma_healthcare",
    "healthcare": "india_pharma_healthcare",
    "biotech": "india_pharma_healthcare",
    "hospitals": "india_pharma_healthcare",
    "oil": "india_energy_oil_gas",
    "oil_and_gas": "india_energy_oil_gas",
    "energy": "india_energy_oil_gas",
    "auto": "india_auto_ancillaries",
    "automobile": "india_auto_ancillaries",
    "automobiles": "india_auto_ancillaries",
    "ancillaries": "india_auto_ancillaries",
    "fmcg": "india_fmcg_staples",
    "staples": "india_fmcg_staples",
    "consumer": "india_fmcg_staples",
    "infra": "india_infra_capgoods",
    "infrastructure": "india_infra_capgoods",
    "capital_goods": "india_infra_capgoods",
    "capgoods": "india_infra_capgoods",
    "defence": "india_infra_capgoods",
    "defense": "india_infra_capgoods",
    "metals": "india_metals_mining",
    "mining": "india_metals_mining",
    "steel": "india_metals_mining",
    "telecom": "india_telecom",
    "telecommunications": "india_telecom",
    "power": "india_power_utilities",
    "utilities": "india_power_utilities",
    "utility": "india_power_utilities",
    "cement": "india_cement_realty",
    "realty": "india_cement_realty",
    "real_estate": "india_cement_realty",
    "chemicals": "india_chemicals",
    "specialty_chemicals": "india_chemicals",
}


def normalize_market(raw: str | None) -> Market:
    """Accept USA / US / India / IN (any case) → 'usa' | 'india'."""
    if raw is None or not str(raw).strip():
        raise ValueError("market is required (USA or India)")
    key = str(raw).strip().lower()
    aliases = {
        "usa": "usa",
        "us": "usa",
        "u.s.": "usa",
        "u.s.a.": "usa",
        "america": "usa",
        "united_states": "usa",
        "unitedstates": "usa",
        "india": "india",
        "in": "india",
        "ind": "india",
        "bharat": "india",
        "nse": "india",
    }
    market = aliases.get(key)
    if market is None:
        raise ValueError(
            f"Unsupported market '{raw}'. Use one of: USA, India "
            f"(aliases: US, IN)."
        )
    return market  # type: ignore[return-value]


def market_label(market: Market) -> str:
    return "USA" if market == "usa" else "India"


def get_universe(market: Market | str) -> dict[str, SectorUniverse]:
    m: Market = market if market in MARKET_UNIVERSES else normalize_market(str(market))  # type: ignore[assignment]
    return MARKET_UNIVERSES[m]


def list_sector_keys(market: Market | str | None = None) -> list[str]:
    if market is None:
        return sorted(SECTOR_UNIVERSE.keys())
    return sorted(get_universe(market).keys())


def resolve_sector_key(raw: str, market: Market | str | None = None) -> str | None:
    """Map a free-form sector label to a canonical key within a market."""
    normalized = (
        raw.strip()
        .lower()
        .replace("&", "and")
        .replace("-", "_")
        .replace(" ", "_")
        .replace("/", "_")
    )

    if market is None:
        universe = SECTOR_UNIVERSE
        aliases = {**_USA_ALIASES, **_INDIA_ALIASES}
    else:
        m = normalize_market(market) if market not in MARKET_UNIVERSES else market  # type: ignore[assignment]
        universe = MARKET_UNIVERSES[m]  # type: ignore[index]
        aliases = _USA_ALIASES if m == "usa" else _INDIA_ALIASES

    if normalized in universe:
        return normalized
    if normalized in aliases and aliases[normalized] in universe:
        return aliases[normalized]

    for key, meta in universe.items():
        if key in normalized or normalized in key:
            return key
        if meta["name"].lower().replace(" ", "_") in normalized:
            return key
        # Strip india_ prefix for fuzzy match on India keys
        short = key.removeprefix("india_")
        if short == normalized or short in normalized or normalized in short:
            return key
    return None


def tickers_for_sectors(
    sector_keys: list[str],
    market: Market | str | None = None,
) -> dict[str, list[str]]:
    universe = get_universe(market) if market is not None else SECTOR_UNIVERSE
    out: dict[str, list[str]] = {}
    for key in sector_keys:
        resolved = resolve_sector_key(key, market=market)
        if not resolved and key in universe:
            resolved = key
        if resolved and resolved in universe:
            out[resolved] = list(universe[resolved]["tickers"])
    return out
