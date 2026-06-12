"""
Astronomy service using the ephem library.
Computes moon phases, planet visibility, and upcoming events
for SF Bay Area (37.77°N, 122.42°W).
"""
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# SF Bay Area observer settings
LAT = "37.77"
LON = "-122.42"
ELEVATION = 10  # meters

PLANETS = [
    ("Mercury", "Mercury"),
    ("Venus",   "Venus"),
    ("Mars",    "Mars"),
    ("Jupiter", "Jupiter"),
    ("Saturn",  "Saturn"),
]

MOON_PHASE_NAMES = [
    "New Moon", "Waxing Crescent", "First Quarter", "Waxing Gibbous",
    "Full Moon", "Waning Gibbous", "Last Quarter", "Waning Crescent",
]


def _phase_name(illumination: float) -> str:
    """Map 0-100% illumination to a phase name (approximate)."""
    pct = illumination
    if pct < 3:
        return "New Moon"
    elif pct < 35:
        return "Waxing Crescent"
    elif pct < 65:
        return "First Quarter"
    elif pct < 97:
        return "Waxing Gibbous"
    elif pct >= 97:
        return "Full Moon"
    else:
        return "Waning Gibbous"


def _is_blue_moon(d: datetime) -> bool:
    """True if d is the second full moon in its calendar month."""
    import ephem
    # Find the previous full moon
    prev = ephem.previous_full_moon(d.date().isoformat())
    prev_dt = prev.datetime()
    return prev_dt.month == d.month


def get_sky_tonight() -> dict:
    try:
        import ephem
    except ImportError:
        logger.error("ephem not installed")
        return {}

    now = datetime.now(timezone.utc)
    tonight_9pm = now.replace(hour=2, minute=0, second=0)  # 9pm PT = 02:00 UTC next day

    # Observer
    obs = ephem.Observer()
    obs.lat = LAT
    obs.lon = LON
    obs.elevation = ELEVATION
    obs.date = tonight_9pm.strftime("%Y/%m/%d %H:%M:%S")
    obs.horizon = "10"  # require 10° above horizon

    # ── Moon ──────────────────────────────────────────────────────────────
    moon = ephem.Moon()
    moon.compute(obs)
    illumination = round(moon.phase, 1)

    # Determine if waxing or waning by comparing to tomorrow
    tomorrow = ephem.Observer()
    tomorrow.lat = LAT
    tomorrow.lon = LON
    tomorrow.date = (tonight_9pm + timedelta(days=1)).strftime("%Y/%m/%d %H:%M:%S")
    moon_tomorrow = ephem.Moon()
    moon_tomorrow.compute(tomorrow)
    waxing = moon_tomorrow.phase > moon.phase

    if illumination < 3:
        phase_label = "New Moon"
    elif illumination > 97:
        phase_label = "Full Moon"
    elif illumination < 50 and waxing:
        phase_label = "Waxing Crescent"
    elif illumination >= 50 and waxing:
        phase_label = "Waxing Gibbous"
    elif illumination >= 50 and not waxing:
        phase_label = "Waning Gibbous"
    else:
        phase_label = "Waning Crescent"

    # Next full and new moon
    next_full = ephem.next_full_moon(obs.date)
    next_new = ephem.next_new_moon(obs.date)
    # ephem returns naive UTC datetimes; make them aware so they can be
    # compared with `now`
    next_full_dt = next_full.datetime().replace(tzinfo=timezone.utc)
    next_new_dt = next_new.datetime().replace(tzinfo=timezone.utc)

    # Is next full moon a blue moon?
    is_blue = _is_blue_moon(next_full_dt)

    moon_data = {
        "phase": phase_label,
        "illumination": illumination,
        "next_full": next_full_dt.strftime("%b %-d"),
        "next_full_iso": next_full_dt.date().isoformat(),
        "next_new": next_new_dt.strftime("%b %-d"),
        "is_blue_moon": is_blue,
        "rise": _format_time(moon.rise_time) if moon.rise_time else None,
        "set": _format_time(moon.set_time) if moon.set_time else None,
    }

    # ── Planets ────────────────────────────────────────────────────────────
    planets = []
    for name, cls_name in PLANETS:
        try:
            planet_cls = getattr(ephem, cls_name)
            p = planet_cls()
            p.compute(obs)
            alt_deg = float(p.alt) * 180 / 3.14159
            visible = alt_deg > 10

            # Rise/set
            obs_copy = ephem.Observer()
            obs_copy.lat = LAT
            obs_copy.lon = LON
            obs_copy.date = obs.date
            try:
                rise_t = obs_copy.next_rising(planet_cls())
                set_t = obs_copy.next_setting(planet_cls())
                rise_str = _format_time(rise_t)
                set_str = _format_time(set_t)
            except Exception:
                rise_str = set_str = None

            planets.append({
                "name": name,
                "visible": visible,
                "altitude": round(alt_deg, 1),
                "rise": rise_str,
                "set": set_str,
            })
        except Exception as e:
            logger.debug("Planet %s error: %s", name, e)

    # ── Upcoming events ────────────────────────────────────────────────────
    events = []

    # Blue moon event
    if is_blue:
        events.append({
            "title": f"Blue Moon",
            "date": next_full_dt.strftime("%b %-d"),
            "date_iso": next_full_dt.date().isoformat(),
            "description": f"Second full moon this month — visible all night from the Bay Area.",
            "icon": "🌕",
        })

    # Full moon if not blue
    if not is_blue and (next_full_dt - now).days <= 7:
        events.append({
            "title": "Full Moon",
            "date": next_full_dt.strftime("%b %-d"),
            "date_iso": next_full_dt.date().isoformat(),
            "description": "Moon rises near sunset and sets near sunrise.",
            "icon": "🌕",
        })

    # Visible planets as events
    bright_visible = [p for p in planets if p["visible"] and p["name"] in ("Venus", "Jupiter", "Saturn", "Mars")]
    if bright_visible:
        names = " & ".join(p["name"] for p in bright_visible[:2])
        events.append({
            "title": f"{names} Visible Tonight",
            "date": "Tonight",
            "date_iso": now.date().isoformat(),
            "description": f"{names} visible from the Bay Area after dark. Look " +
                           ("west after sunset." if any(p["name"] == "Venus" for p in bright_visible)
                            else "east after midnight."),
            "icon": "✨",
        })

    logger.info("Astronomy: moon=%s %.0f%%, %d planets computed, %d events",
                phase_label, illumination, len(planets), len(events))

    return {
        "moon": moon_data,
        "planets": planets,
        "events": events,
        "location": "San Francisco Bay Area",
        "computed_at": now.isoformat(),
    }


def _format_time(ephem_date) -> Optional[str]:
    try:
        dt = ephem_date.datetime()
        # Convert UTC to PT (UTC-7 or UTC-8)
        pt = dt - timedelta(hours=7)
        return pt.strftime("%-I:%M %p")
    except Exception:
        return None
