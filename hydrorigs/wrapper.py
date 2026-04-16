import sys
import subprocess
import time
from datetime import datetime
from hydrorigs.database import get_rig, update_rig, upsert_rig
from hydrorigs.config import load_config
from hydrorigs.limits import is_rate_limited, parse_cooldown
from hydrorigs.notify import notify
from hydrorigs.polling import effective_cooldown

def main():
    if len(sys.argv) < 2:
        sys.exit(1)

    model_name = sys.argv[1]
    args = sys.argv[2:]
    
    config = load_config()
    rig_conf = config.get("rigs", {}).get(model_name)
    
    if not rig_conf:
        subprocess.run(args)
        return

    rig = get_rig(model_name)
    now = time.time()
    
    # Check cooldown
    cooldown_target = effective_cooldown(rig, now_ts=now)
    if cooldown_target > now:
        remaining = int(cooldown_target - now)
        if remaining >= 3600:
            msg = f"{model_name.upper()} cooling: {remaining // 3600}h {(remaining % 3600) // 60}m remaining."
        elif remaining >= 60:
            msg = f"{model_name.upper()} cooling: {remaining // 60}m {remaining % 60}s remaining."
        else:
            msg = f"{model_name.upper()} cooling: {remaining}s remaining."
        print(msg)
        notify("HydroRigs Cooldown", msg)
        sys.exit(429)

    real_cmd = rig_conf["cmd"]
    
    try:
        # Execute the command
        process = subprocess.Popen([real_cmd] + args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        
        full_output = []
        for line in process.stdout:
            print(line, end="")
            full_output.append(line)
        
        process.wait()
        output_text = "".join(full_output)
        
        # Scrape for reset information
        cooldown_sec = parse_cooldown(output_text)
        
        rate_limited = is_rate_limited(output_text, returncode=process.returncode)
            
        # Ensure rig exists in DB
        if not get_rig(model_name):
            upsert_rig(model_name, rig_conf.get("max_tokens", 10), rig_conf.get("refill_rate", 1.0))

        if rate_limited:
            if cooldown_sec is None:
                cooldown_sec = rig_conf.get("cooldown_default", 60)
            
            update_rig(model_name, cooldown_until=now + cooldown_sec, reset_time=now + cooldown_sec)
            notify("HydroRigs Triggered", f"{model_name.upper()} rate limit. Cooling until {datetime.fromtimestamp(now + cooldown_sec).strftime('%b %d, %H:%M')}.")
        else:
            update_rig(model_name, cooldown_until=0, reset_time=0, last_synced=time.time())
        
        sys.exit(process.returncode)

    except FileNotFoundError:
        print(f"Error: Command '{real_cmd}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"Error running command: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
