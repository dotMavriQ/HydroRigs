import sys
import time
import shutil
import yaml
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


def status():
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
    
    now = time.time()
    parts = []
    
    for name in ordered_names:
        rig = all_rigs[name]
        rig_conf = config.get("rigs", {}).get(name, {})
        icon = STATUS_ICONS.get(name, display_name(name))
        monitor_mode = rig_conf.get("monitor_mode", "cooldown")

        if monitor_mode == "budget":
            parts.append(f"{icon}: {STATUS_BUDGET.get(budget_status(rig, rig_conf), '⚪')}")
            continue
        
        cooldown_target = effective_cooldown(rig, now_ts=now)
        
        if cooldown_target > now:
            rem = int(cooldown_target - now)
            parts.append(f"{icon}: {format_cooldown(rem)}")
        else:
            parts.append(f"{icon}: 🟢")
            
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
        print("Usage: hydrorigs [status|discover|wrap|ui|daemon|sync]")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "status":
        status()
    elif cmd == "discover":
        discover()
    elif cmd == "sync":
        init_db()
        sync_all_rigs(load_config())
    elif cmd == "ui":
        from hydrorigs.ui import HydroRigsTUI
        app = HydroRigsTUI()
        app.run()
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
