import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from hydrorigs.database import get_rig, update_rig, upsert_rig
from hydrorigs.limits import is_rate_limited, parse_cooldown, parse_iso8601


def default_probe_args(name):
    probes = {
        "claude": ["-p", "Reply with exactly OK."],
        "codex": ["exec", "Reply with exactly OK."],
        "openai": ["api", "models.list"],
        "gemini": ["-p", "Reply with exactly OK.", "--output-format", "text"],
        "aider": ["--version"],
    }
    return probes.get(name)


def is_tracked(rig_conf):
    return rig_conf.get("track", True)


def has_command(cmd):
    if not cmd:
        return False
    return shutil.which(cmd) is not None


def is_available(name, rig_conf):
    cmd = rig_conf.get("cmd") or name

    if name == "gh":
        if has_command("copilot"):
            return True
        copilot_root = Path.home() / ".copilot"
        if (copilot_root / "logs").exists() or (copilot_root / "session-state").exists():
            return True
        extension_root = Path.home() / ".vscode" / "extensions"
        return any(extension_root.glob("github.copilot-chat-*"))

    if name == "aider":
        return has_command(cmd) and bool(os.getenv(rig_conf.get("budget_env_var", "DEEPSEEK_API_KEY")))

    if name == "gemini":
        return has_command(cmd) and Path.home().joinpath(".gemini", "oauth_creds.json").exists()

    if rig_conf.get("monitor_mode") == "budget":
        env_var = rig_conf.get("budget_env_var")
        if env_var:
            return has_command(cmd) and bool(os.getenv(env_var))

    return has_command(cmd)


def effective_cooldown(rig, now_ts=None):
    if not rig:
        return 0
    now_ts = time.time() if now_ts is None else now_ts
    cooldown_until = rig.get("cooldown_until") or 0
    reset_time = rig.get("reset_time") or 0
    target = max(cooldown_until, reset_time)
    return target if target > now_ts else 0


def display_name(name):
    display_map = {
        "claude": "Claude",
        "codex": "Codex",
        "openai": "Codex",
        "gemini": "Gemini",
        "gh": "GH",
        "aider": "Aider",
    }
    return display_map.get(name, name.capitalize())


def budget_status(rig, rig_conf):
    value = rig.get("tokens") if rig else None
    if value is None:
        return None
    metric = rig_conf.get("budget_metric", "balance")
    if metric == "used_fraction":
        critical = rig_conf.get("critical_used_fraction", 1.0)
        warning = rig_conf.get("warning_used_fraction", 0.7)
        if value >= critical:
            return "critical"
        if value >= warning:
            return "warning"
        return "ok"

    critical = rig_conf.get("critical_balance", 0.5)
    warning = rig_conf.get("warning_balance", 5.0)
    if value <= critical:
        return "critical"
    if value <= warning:
        return "warning"
    return "ok"


def ensure_rig(name, rig_conf):
    if not get_rig(name):
        upsert_rig(name, rig_conf.get("max_tokens", 10), rig_conf.get("refill_rate", 1.0))


def current_github_cycle_start(now_ts=None):
    now_ts = time.time() if now_ts is None else now_ts
    now = datetime.fromtimestamp(now_ts, tz=timezone.utc)
    return datetime(now.year, now.month, 1, tzinfo=timezone.utc).timestamp()


def next_github_cycle_reset(now_ts=None):
    now_ts = time.time() if now_ts is None else now_ts
    now = datetime.fromtimestamp(now_ts, tz=timezone.utc)
    if now.month == 12:
        target = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        target = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)
    return target.timestamp()


def latest_github_quota_exhaustion(now_ts=None):
    now_ts = time.time() if now_ts is None else now_ts
    cycle_start = current_github_cycle_start(now_ts=now_ts)
    latest = 0.0

    log_paths = sorted(Path.home().glob(".copilot/logs/process-*.log"))
    for path in log_paths:
        try:
            current_ts = None
            with path.open("r", encoding="utf-8", errors="ignore") as handle:
                for line in handle:
                    if len(line) >= 24 and line[4] == "-" and line[10] == "T":
                        current_ts = parse_iso8601(line[:24]) or current_ts
                    lowered = line.lower()
                    if "quota_exceeded" in lowered or "you have no quota" in lowered:
                        if current_ts and current_ts >= cycle_start:
                            latest = max(latest, current_ts)
        except OSError:
            continue

    event_paths = sorted(Path.home().glob(".copilot/session-state/*/events.jsonl"))
    for path in event_paths:
        try:
            with path.open("r", encoding="utf-8", errors="ignore") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if payload.get("type") != "session.error":
                        continue
                    data = payload.get("data") or {}
                    if data.get("errorType") != "quota":
                        continue
                    ts = parse_iso8601(payload.get("timestamp", ""))
                    if ts and ts >= cycle_start:
                        latest = max(latest, ts)
        except OSError:
            continue

    return latest or None


def sync_github_copilot(name, rig_conf):
    now = time.time()
    ensure_rig(name, rig_conf)
    exhausted_at = latest_github_quota_exhaustion(now_ts=now)
    reset_time = next_github_cycle_reset(now_ts=now)

    update_rig(
        name,
        tokens=1 if exhausted_at else 0,
        max_tokens=1,
        cooldown_until=reset_time if exhausted_at else 0,
        reset_time=reset_time if exhausted_at else 0,
        last_synced=now,
    )
    return True


def sync_deepseek_balance(name, rig_conf):
    now = time.time()
    ensure_rig(name, rig_conf)
    api_key = os.getenv(rig_conf.get("budget_env_var", "DEEPSEEK_API_KEY"))
    if not api_key:
        return False

    request = Request(
        rig_conf.get("budget_api_url", "https://api.deepseek.com/user/balance"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        },
    )

    try:
        with urlopen(request, timeout=rig_conf.get("probe_timeout", 15)) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        return False

    balances = payload.get("balance_infos") or []
    total_balance = 0.0
    for entry in balances:
        try:
            total_balance += float(entry.get("total_balance", "0") or 0)
        except (TypeError, ValueError):
            continue

    update_rig(
        name,
        tokens=total_balance,
        last_synced=now,
    )
    return True


def load_google_oauth_creds():
    path = os.path.expanduser("~/.gemini/oauth_creds.json")
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def refresh_google_access_token(creds):
    payload = urlencode({
        "client_id": "681255809395-oo8ft2oprdrnp9e3aqf6av3hmdib135j.apps.googleusercontent.com",
        "grant_type": "refresh_token",
        "refresh_token": creds["refresh_token"],
    }).encode("utf-8")
    request = Request(
        "https://oauth2.googleapis.com/token",
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urlopen(request, timeout=15) as response:
        refreshed = json.loads(response.read().decode("utf-8"))
    creds["access_token"] = refreshed["access_token"]
    if "expires_in" in refreshed:
        creds["expiry_date"] = int(time.time() * 1000) + int(refreshed["expires_in"]) * 1000
    with open(os.path.expanduser("~/.gemini/oauth_creds.json"), "w", encoding="utf-8") as handle:
        json.dump(creds, handle, indent=2)
    return creds["access_token"]


def get_google_access_token():
    creds = load_google_oauth_creds()
    expiry = int(creds.get("expiry_date", 0) or 0)
    now_ms = int(time.time() * 1000)
    if expiry and expiry - now_ms > 60000:
        return creds["access_token"]
    return refresh_google_access_token(creds)


def google_code_assist_post(method, payload):
    token = get_google_access_token()
    request = Request(
        f"https://cloudcode-pa.googleapis.com/v1internal:{method}",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def sync_gemini_quota(name, rig_conf):
    now = time.time()
    ensure_rig(name, rig_conf)

    try:
        load_res = google_code_assist_post(
            "loadCodeAssist",
            {
                "metadata": {
                    "ideType": "IDE_UNSPECIFIED",
                    "platform": "PLATFORM_UNSPECIFIED",
                    "pluginType": "GEMINI",
                }
            },
        )
        project = load_res.get("cloudaicompanionProject")
        if not project:
            return False
        quota = google_code_assist_post("retrieveUserQuota", {"project": project})
    except (FileNotFoundError, KeyError, HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError):
        return False

    bucket_model = rig_conf.get("budget_model", "gemini-2.5-pro")
    bucket = next((entry for entry in quota.get("buckets", []) if entry.get("modelId") == bucket_model), None)
    if not bucket:
        return False

    remaining_fraction = float(bucket.get("remainingFraction", 0) or 0)
    used_fraction = max(0.0, 1.0 - remaining_fraction)
    reset_time = bucket.get("resetTime")
    reset_timestamp = 0
    if reset_time and reset_time != "1970-01-01T00:00:00Z":
        from hydrorigs.limits import parse_iso8601
        reset_timestamp = parse_iso8601(reset_time) or 0

    update_rig(
        name,
        tokens=used_fraction,
        max_tokens=1.0,
        cooldown_until=0,
        reset_time=reset_timestamp,
        last_synced=now,
    )
    return True


def probe_rig(name, rig_conf):
    ensure_rig(name, rig_conf)
    now = time.time()
    monitor_mode = rig_conf.get("monitor_mode", "cooldown")

    if monitor_mode == "unsupported":
        return False

    if name == "gh":
        return sync_github_copilot(name, rig_conf)

    if monitor_mode == "budget":
        provider = rig_conf.get("budget_provider", "deepseek")
        if provider == "deepseek":
            return sync_deepseek_balance(name, rig_conf)
        if provider == "gemini_code_assist":
            return sync_gemini_quota(name, rig_conf)
        return False

    cmd = rig_conf.get("cmd") or name
    probe_args = rig_conf.get("probe_args")
    if probe_args is None:
        probe_args = default_probe_args(name)
    if not probe_args:
        return False

    try:
        res = subprocess.run(
            [cmd, *probe_args],
            capture_output=True,
            text=True,
            timeout=rig_conf.get("probe_timeout", 30),
            check=False,
        )
    except Exception:
        return False

    output_text = "\n".join(part for part in (res.stdout, res.stderr) if part)
    cooling = is_rate_limited(output_text, returncode=res.returncode)

    if cooling:
        cooldown_sec = parse_cooldown(output_text, now_ts=now)
        if cooldown_sec is None:
            cooldown_sec = rig_conf.get("cooldown_default", 60)
        reset_at = now + cooldown_sec
        update_rig(
            name,
            cooldown_until=reset_at,
            reset_time=reset_at,
            last_synced=now,
        )
    else:
        update_rig(
            name,
            cooldown_until=0,
            reset_time=0,
            last_synced=now,
        )
    return True


def sync_all_rigs(config):
    results = {}
    rigs = config.get("rigs", {})
    now = time.time()

    for name, rig_conf in rigs.items():
        if not is_tracked(rig_conf) or not is_available(name, rig_conf):
            continue
        rig = get_rig(name)
        last_synced = (rig or {}).get("last_synced") or 0
        interval = rig_conf.get("probe_interval", 300)
        if interval > 0 and now - last_synced < interval:
            continue
        results[name] = probe_rig(name, rig_conf)

    return results
