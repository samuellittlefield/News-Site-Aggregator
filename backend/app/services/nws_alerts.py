import logging
from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.models import NWSAlert

logger = logging.getLogger(__name__)

SEVERITY_RANK = {"Extreme": 4, "Severe": 3, "Moderate": 2, "Minor": 1, "Unknown": 0}
NWS_URL = "https://api.weather.gov/alerts/active"

# Maps the city portion of NWS senderName (e.g. "NWS Albuquerque NM" → "albuquerque")
# to the WFO office identifier used in weather.gov URLs.
_WFO_BY_CITY: dict[str, str] = {
    "albuquerque": "abq",
    "wakefield": "akq",
    "albany": "aly",
    "amarillo": "ama",
    "gaylord": "apx",
    "la crosse": "arx",
    "binghamton": "bgm",
    "birmingham": "bmx",
    "denver": "bou",
    "boulder": "bou",
    "norton": "box",
    "boston": "box",
    "brownsville": "bro",
    "rio grande valley": "bro",
    "baton rouge": "btr",
    "burlington": "btv",
    "buffalo": "buf",
    "billings": "byz",
    "columbia": "cae",
    "caribou": "car",
    "charleston": "chs",
    "cleveland": "cle",
    "corpus christi": "crp",
    "state college": "ctp",
    "cheyenne": "cys",
    "dodge city": "ddc",
    "duluth": "dlh",
    "des moines": "dmx",
    "detroit": "dtx",
    "davenport": "dvn",
    "pleasant hill": "eax",
    "eureka": "eka",
    "el paso": "epz",
    "santa teresa": "epz",
    "austin": "ewx",
    "san antonio": "ewx",
    "peachtree city": "ffc",
    "grand forks": "fgf",
    "flagstaff": "fgz",
    "sioux falls": "fsd",
    "fort worth": "fwd",
    "glasgow": "ggw",
    "hastings": "gid",
    "grand junction": "gjt",
    "goodland": "gld",
    "green bay": "grb",
    "grand rapids": "grr",
    "greenville-spartanburg": "gsp",
    "greenville": "gsp",
    "spartanburg": "gsp",
    "tiyan": "gum",
    "gray": "gyx",
    "honolulu": "hfo",
    "houston": "hgx",
    "galveston": "hgx",
    "hanford": "hnx",
    "huntsville": "hun",
    "wichita": "ict",
    "wilmington": "ilm",
    "lincoln": "ilx",
    "indianapolis": "ind",
    "jackson": "jan",
    "jacksonville": "jax",
    "key west": "key",
    "north platte": "lbf",
    "lake charles": "lch",
    "new orleans": "lix",
    "elko": "lkn",
    "louisville": "lmk",
    "chicago": "lot",
    "los angeles": "lox",
    "oxnard": "lox",
    "st. louis": "lsx",
    "saint louis": "lsx",
    "lubbock": "lub",
    "baltimore": "lwx",
    "washington": "lwx",
    "little rock": "lzk",
    "midland": "maf",
    "odessa": "maf",
    "memphis": "meg",
    "miami": "mfl",
    "medford": "mfr",
    "newport": "mhx",
    "morehead city": "mhx",
    "milwaukee": "mkx",
    "sullivan": "mkx",
    "melbourne": "mlb",
    "mobile": "mob",
    "pensacola": "mob",
    "minneapolis": "mpx",
    "twin cities": "mpx",
    "marquette": "mqt",
    "morristown": "mrx",
    "missoula": "mso",
    "san francisco": "mtr",
    "omaha": "oax",
    "nashville": "ohx",
    "upton": "okx",
    "new york": "okx",
    "spokane": "otx",
    "norman": "oun",
    "paducah": "pah",
    "pittsburgh": "pbz",
    "pendleton": "pdt",
    "mount holly": "phi",
    "mt. holly": "phi",
    "philadelphia": "phi",
    "pocatello": "pih",
    "portland": "pqr",
    "phoenix": "psr",
    "pueblo": "pub",
    "raleigh": "rah",
    "reno": "rev",
    "riverton": "riw",
    "blacksburg": "rnk",
    "seattle": "sew",
    "springfield": "sgf",
    "san diego": "sgx",
    "shreveport": "shv",
    "san angelo": "sjt",
    "san juan": "sju",
    "salt lake city": "slc",
    "sacramento": "sto",
    "tallahassee": "tae",
    "tampa": "tbw",
    "ruskin": "tbw",
    "great falls": "tfx",
    "topeka": "top",
    "tulsa": "tsa",
    "tucson": "twc",
    "rapid city": "unr",
    "las vegas": "vef",
    "charleston wv": "rlx",
    "west virginia": "rlx",
}


def _sender_to_wfo_url(sender_name: Optional[str]) -> Optional[str]:
    """Parse 'NWS Albuquerque NM' → 'https://www.weather.gov/abq/'"""
    if not sender_name or not sender_name.startswith("NWS "):
        return None
    # Strip "NWS " prefix, then remove the trailing state abbreviation (last word)
    body = sender_name[4:].strip()
    parts = body.rsplit(" ", 1)
    city = parts[0].lower().strip() if len(parts) >= 1 else body.lower()
    wfo = _WFO_BY_CITY.get(city)
    if wfo:
        return f"https://www.weather.gov/{wfo}/"
    return None


async def fetch_nws_alerts(db: Session) -> "list[NWSAlert]":
    headers = {"User-Agent": "SituationMonitor/1.0 (contact@samuellittlefield.com)", "Accept": "application/geo+json"}
    now = datetime.now(timezone.utc)

    try:
        async with httpx.AsyncClient(headers=headers, timeout=15.0) as client:
            resp = await client.get(NWS_URL)
        resp.raise_for_status()
    except httpx.RequestError as e:
        logger.warning("NWS alerts request failed: %s", e)
        return []
    except httpx.HTTPStatusError as e:
        logger.warning("NWS alerts HTTP error %s", e.response.status_code)
        return []

    features = resp.json().get("features", [])
    seen_ids: set[str] = set()
    saved: list[NWSAlert] = []

    for feat in features:
        props = feat.get("properties", {})
        nws_id = props.get("id", "")
        if not nws_id or nws_id in seen_ids:
            continue
        seen_ids.add(nws_id)

        severity = props.get("severity", "Unknown")
        if SEVERITY_RANK.get(severity, 0) < SEVERITY_RANK["Moderate"]:
            continue

        def _parse_dt(val: Optional[str]) -> Optional[datetime]:
            if not val:
                return None
            try:
                return datetime.fromisoformat(val.replace("Z", "+00:00"))
            except ValueError:
                return None

        expires = _parse_dt(props.get("expires"))
        if expires and expires < now:
            continue

        sender_name = props.get("senderName")
        wfo_url = _sender_to_wfo_url(sender_name)

        existing = db.query(NWSAlert).filter(NWSAlert.nws_id == nws_id).first()
        if existing:
            existing.severity = severity
            existing.expires = expires
            existing.sender_name = sender_name
            existing.wfo_url = wfo_url
            existing.fetched_at = now
            saved.append(existing)
        else:
            alert = NWSAlert(
                nws_id=nws_id,
                event=props.get("event", "Unknown Event"),
                headline=props.get("headline"),
                severity=severity,
                urgency=props.get("urgency"),
                area_desc=props.get("areaDesc"),
                sender_name=sender_name,
                wfo_url=wfo_url,
                onset=_parse_dt(props.get("onset")),
                expires=expires,
                fetched_at=now,
            )
            db.add(alert)
            saved.append(alert)

    # Remove expired alerts
    db.query(NWSAlert).filter(
        NWSAlert.expires != None,  # noqa: E711
        NWSAlert.expires < now,
    ).delete(synchronize_session=False)

    db.commit()
    logger.info("NWS alerts: %d active saved", len(saved))
    return saved
