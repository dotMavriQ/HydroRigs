import sys
import time
import shutil
import yaml
import json
from datetime import datetime
from hydrorigs.database import get_all_rigs, init_db, upsert_rig
from hydrorigs.config import DEFAULT_RIGS, load_config, CONFIG_PATH
from hydrorigs.polling import budget_status, display_name, effective_cooldown, is_available, is_tracked, sync_all_rigs

STATUS_ICONS = {
    "claude": "🎭",
    "codex": "📜",
    "openai": "📜",
    "gemini": "♊",
    "gh": "🐙",
    "aider": "🩹",
}

STATUS_LABELS = {
    "claude": "CL",
    "codex": "CX",
    "openai": "OA",
    "gemini": "GM",
    "gh": "GH",
    "aider": "AD",
}

STATUS_BUDGET = {
    "ok": "🟢",
    "warning": "🟡",
    "critical": "🔴",
}


def format_cooldown(rem):
    if rem >= 604800:
        weeks = rem // 604800
        days = (rem % 604800) // 86400
        return f"{weeks}w {days}d" if days else f"{weeks}w"
    if rem >= 86400:
        days = rem // 86400
        hours = (rem % 86400) // 3600
        return f"{days}d {hours}h" if hours else f"{days}d"
    if rem >= 3600:
        return f"{rem // 3600}h {(rem % 3600) // 60}m"
    if rem >= 60:
        return f"{rem // 60}m"
    return f"{rem}s"


def format_cooldown_compact(rem):
    if rem >= 604800:
        weeks = rem // 604800
        days = (rem % 604800) // 86400
        return f"{weeks}w{days}d" if days else f"{weeks}w"
    if rem >= 86400:
        days = rem // 86400
        hours = (rem % 86400) // 3600
        return f"{days}d{hours}h" if hours else f"{days}d"
    if rem >= 3600:
        return f"{rem // 3600}h{(rem % 3600) // 60}m"
    if rem >= 60:
        return f"{rem // 60}m"
    return f"{rem}s"


def _iter_rig_statuses(names, all_rigs, config, compact=False, waybar_json=False):
    now = time.time()
    for name in names:
        rig = all_rigs.get(name)
        if not rig:
            continue
        rig_conf = config.get("rigs", {}).get(name, {})
        icon = STATUS_ICONS.get(name, display_name(name))
        monitor_mode = rig_conf.get("monitor_mode", "cooldown")

        if monitor_mode == "budget":
            status = budget_status(rig, rig_conf)
            color_emoji = STATUS_BUDGET.get(status, "⚪")
            metric = rig_conf.get("budget_metric", "balance")
            tokens = rig.get("tokens", 0)
            max_tokens = rig.get("max_tokens", 0)
            
            if metric == "used_fraction":
                display_value = f"{tokens*100:.0f}% used"
            else:
                display_value = f"{tokens:.2f} {rig_conf.get('budget_unit', '$')}"

            if waybar_json:
                yield {
                    "text": f"{icon}:{color_emoji}" if compact else f"{icon}: {color_emoji}",
                    "class": status or "unknown",
                    "tooltip": f"{display_name(name)}: {status.upper() if status else 'Unknown'}\n{display_value}"
                }
            else:
                yield f"{icon}:{color_emoji}" if compact else f"{icon}: {color_emoji}"
            continue

        cooldown_target = effective_cooldown(rig, now_ts=now)
        if cooldown_target > now:
            rem = int(cooldown_target - now)
            value = format_cooldown_compact(rem) if compact else format_cooldown(rem)
            status = "cooling"
            text = f"{icon}:{value}" if compact else f"{icon}: {value}"
        else:
            value = "🟢"
            status = "ready"
            text = f"{icon}:{value}" if compact else f"{icon}: {value}"
        
        if waybar_json:
            yield {
                "text": text,
                "class": status,
                "tooltip": f"{display_name(name)}: {status.upper()}\n{'Cooldown until: ' + datetime.fromtimestamp(cooldown_target).strftime('%Y-%m-%d %H:%M:%S') if status == 'cooling' else 'Ready'}"
            }
        else:
            yield text


def status(compact=False, stacked=False, rig_name=None, waybar_json=False, waybar_pango=False):
    init_db()
    config = load_config()
    all_rigs = {r["name"]: r for r in get_all_rigs()}
    # Priority order as requested
    priority = ["claude", "codex", "openai", "gemini", "gh"]
    
    # De-duplicate: if we have both codex and openai, prefer codex
    ordered_names = []
    seen_display = set()
    
    for name in priority:
        rig_conf = config.get("rigs", {}).get(name, {})
        if name in all_rigs and is_tracked(rig_conf) and is_available(name, rig_conf):
            disp = display_name(name)
            if disp not in seen_display:
                ordered_names.append(name)
                seen_display.add(disp)
    
    # Add any others not in priority
    for name in all_rigs:
        rig_conf = config.get("rigs", {}).get(name, {})
        if name not in ordered_names and is_tracked(rig_conf) and is_available(name, rig_conf):
            disp = display_name(name)
            if disp not in seen_display:
                ordered_names.append(name)
                seen_display.add(disp)
    
    if rig_name:
        if rig_name not in ordered_names:
            return
        parts = list(_iter_rig_statuses([rig_name], all_rigs, config, compact=compact, waybar_json=waybar_json))
        if parts:
            if waybar_json:
                print(json.dumps(parts[0]))
            else:
                print(parts[0])
        return

    parts = list(_iter_rig_statuses(ordered_names, all_rigs, config, compact=compact, waybar_json=waybar_json))
    if waybar_json:
        if len(parts) == 1:
            print(json.dumps(parts[0]))
        else:
            tooltip_lines = ["HydroRigs Status:"]
            pango_parts = []
            plain_parts = []

            for p in parts:
                status_class = p.get("class", "unknown")
                text = p["text"]
                tooltip_lines.append(f"- {p['tooltip'].replace('\\n', ' ')}")
                plain_parts.append(text)
                
                color = "#d4be98"
                if status_class in ["ready", "ok"]: color = "#a9b665"
                elif status_class in ["cooling", "critical"]: color = "#ea6962"
                elif status_class == "warning": color = "#d8a657"
                pango_parts.append(f"<span color='{color}'>{text}</span>")

            combined_text = " | ".join(pango_parts if waybar_pango else plain_parts)
            print(json.dumps({
                "text": combined_text,
                "class": "multi",
                "tooltip": "\n".join(tooltip_lines)
            }))
    elif stacked:
        print("\n".join(f"{part} |" for part in parts))
    else:
        print(" | ".join(parts))

def discover():
    init_db()
    # Priority CLIs
    ai_clis = ["claude", "codex", "gemini", "gh", "openai", "tgpt", "mods", "aider"]
    found = []
    config = load_config()
    existing_rigs = config.get("rigs", {})
    
    print("Scanning $PATH for AI CLIs...")
    for cli in ai_clis:
        path = shutil.which(cli)
        if path:
            print(f"Found: {cli} at {path}")
            if cli not in existing_rigs:
                conf = DEFAULT_RIGS.get(
                    cli,
                    {"max_tokens": 20, "refill_rate": 1.0, "cooldown_default": 60},
                ).copy()
                conf["cmd"] = path
                existing_rigs[cli] = conf
                found.append(cli)
    
    if found:
        config["rigs"] = existing_rigs
        with open(CONFIG_PATH, "w") as f:
            yaml.dump(config, f)
        print(f"Added {len(found)} new rigs to config.")
    else:
        print("No new AI CLIs found.")

def main():
    if len(sys.argv) < 2:
        print("Usage: hydrorigs [status|discover|wrap|daemon|sync]")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "status":
        status(
            compact="--waybar" in sys.argv[2:] or "--waybar-stack" in sys.argv[2:],
            stacked="--waybar-stack" in sys.argv[2:],
            rig_name=next((arg.split("=", 1)[1] for arg in sys.argv[2:] if arg.startswith("--rig=")), None),
            waybar_json="--waybar-json" in sys.argv[2:],
            waybar_pango="--waybar-pango" in sys.argv[2:],
        )
    elif cmd == "discover":
        discover()
    elif cmd == "sync":
        init_db()
        sync_all_rigs(load_config())
    elif cmd == "daemon":
        from hydrorigs.daemon import run_daemon
        run_daemon()
    elif cmd == "wrap":
        init_db()
        from hydrorigs.wrapper import main as wrap_main
        sys.argv = sys.argv[1:]
        wrap_main()
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)

if __name__ == "__main__":
    main()
