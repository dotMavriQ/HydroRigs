import re
import time
from datetime import datetime


RATE_LIMIT_PATTERNS = (
    "rate limit",
    "too many requests",
    "quota exceeded",
    "usage limit",
    "limit reached",
    "out of extra usage",
    "all premium requests available",
    "capacity exceeded",
    "usage is limited",
    "reached your usage limit",
    "out of free messages",
    "no more messages",
    "available again at",
)


def parse_iso8601(ts_str):
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return dt.timestamp()
    except Exception:
        return None


def parse_clock_time(text, now_ts=None):
    now_ts = time.time() if now_ts is None else now_ts
    now = datetime.fromtimestamp(now_ts)
    match = re.search(
        r"\b(?:try again|available again|resets?|until|available)\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*([ap]m)\b",
        text,
        re.I,
    )
    if not match:
        return None

    hour = int(match.group(1))
    minute = int(match.group(2)) if match.group(2) else 0
    ampm = match.group(3).lower()

    if ampm == "pm" and hour < 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0

    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if "tomorrow" in text.lower() or target.timestamp() <= now_ts:
        target = target.fromtimestamp(now_ts + 86400).replace(
            hour=hour,
            minute=minute,
            second=0,
            microsecond=0,
        )
    return max(0, target.timestamp() - now_ts)


def parse_cooldown(text, now_ts=None):
    now_ts = time.time() if now_ts is None else now_ts
    text = text.replace("\xa0", " ")
    text = re.sub(r'\b(\d+)(?:st|nd|rd|th)\b', r'\1', text, flags=re.I)
    months_pattern = r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"

    mdyt_match = re.search(months_pattern + r"\s+(\d+),\s+(\d{4})\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)", text, re.I)
    if mdyt_match:
        month_str = mdyt_match.group(1).capitalize()
        day = int(mdyt_match.group(2))
        year = int(mdyt_match.group(3))
        hour = int(mdyt_match.group(4))
        minute = int(mdyt_match.group(5) or 0)
        ampm = mdyt_match.group(6).lower()
        if ampm == "pm" and hour < 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0
        try:
            dt = datetime(year, datetime.strptime(month_str, "%b").month, day, hour, minute)
            return max(0, dt.timestamp() - now_ts)
        except Exception:
            pass

    mdy_match = re.search(months_pattern + r"\s+(\d+),\s+(\d{4})", text, re.I)
    if mdy_match:
        month_str = mdy_match.group(1).capitalize()
        day = int(mdy_match.group(2))
        year = int(mdy_match.group(3))
        try:
            dt = datetime.strptime(f"{month_str} {day} {year}", "%b %d %Y")
            return max(0, dt.timestamp() - now_ts)
        except Exception:
            pass

    mdt_match = re.search(months_pattern + r"\s+(\d+),\s+(\d+)(?::(\d{2}))?\s*(am|pm)", text, re.I)
    if mdt_match:
        month_str = mdt_match.group(1).capitalize()
        day = int(mdt_match.group(2))
        hour = int(mdt_match.group(3))
        minute = int(mdt_match.group(4) or 0)
        ampm = mdt_match.group(5).lower()
        if ampm == "pm" and hour < 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0

        now = datetime.fromtimestamp(now_ts)
        try:
            dt = datetime(now.year, datetime.strptime(month_str, "%b").month, day, hour, minute)
            return max(0, dt.timestamp() - now_ts)
        except Exception:
            pass

    clock_time = parse_clock_time(text, now_ts=now_ts)
    if clock_time is not None:
        return clock_time

    match = re.search(r"(?:retry|try again|resets|resets in|in|remaining|until|available in)\s*:?\s*([\d\w\s\.:]+)", text, re.I)
    if match:
        raw = match.group(1).lower()
        if re.search(r"\b\d{1,2}:\d{2}\s*[ap]m\b", raw, re.I):
            return None
        total_sec = 0

        comp_match = re.findall(r"(\d+(?:\.\d+)?)\s*(h|hour|hours|m|min|mins|minute|minutes|s|sec|secs|second|seconds)", raw)
        if comp_match:
            for val, unit in comp_match:
                value = float(val)
                if unit.startswith("h"):
                    total_sec += value * 3600
                elif unit.startswith("m"):
                    total_sec += value * 60
                else:
                    total_sec += value
            return total_sec

        simple = re.search(r"\b(\d+(?:\.\d+)?)\s*(s|sec|seconds|m|min|minutes|h|hour|hours)?\b", raw)
        if simple:
            value = float(simple.group(1))
            unit = simple.group(2)
            if unit:
                unit = unit.lower()
                if unit.startswith("h"):
                    return value * 3600
                if unit.startswith("m"):
                    return value * 60
                return value
            
            # Only return naked value if it's the ONLY thing in raw or it's clearly a number
            if re.fullmatch(r"\d+(?:\.\d+)?", raw.strip()):
                return value

    iso_match = re.search(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2}))", text)
    if iso_match:
        ts = parse_iso8601(iso_match.group(1))
        if ts:
            return max(0, ts - now_ts)

    return None


def is_rate_limited(text, returncode=0):
    lowered = text.lower()
    return returncode == 429 or any(pattern in lowered for pattern in RATE_LIMIT_PATTERNS)
