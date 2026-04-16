import time
import signal
import sys
from hydrorigs.database import init_db, get_all_rigs, update_rig, upsert_rig
from hydrorigs.config import load_config
from hydrorigs.notify import notify
from hydrorigs.polling import display_name, effective_cooldown, is_tracked, sync_all_rigs

def run_daemon():
    init_db()
    config = load_config()
    
    # Initial setup from config
    for name, rig_conf in config.get("rigs", {}).items():
        if not is_tracked(rig_conf):
            continue
        upsert_rig(name, rig_conf["max_tokens"], rig_conf["refill_rate"])

    print("HydroRigs Daemon started.")
    
    last_sync = 0
    sync_interval = 300 # 5 minutes
    previous_states = {
        rig["name"]: bool(effective_cooldown(rig))
        for rig in get_all_rigs()
    }
    
    while True:
        now = time.time()
        
        if now - last_sync > sync_interval:
            sync_all_rigs(config)
            last_sync = now

        rigs = get_all_rigs()

        for rig in rigs:
            actual_cooldown = effective_cooldown(rig, now_ts=now)
            was_cooling = previous_states.get(rig["name"], False)

            if actual_cooldown == 0 and (rig["cooldown_until"] > 0 or rig["reset_time"] > 0):
                update_rig(rig["name"], cooldown_until=0, reset_time=0)

            if was_cooling and actual_cooldown == 0:
                notify("HydroRigs Ready", f"{display_name(rig['name'])} cooldown finished.")

            previous_states[rig["name"]] = bool(actual_cooldown)

        time.sleep(5)

def signal_handler(sig, frame):
    print("Stopping daemon...")
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    run_daemon()
