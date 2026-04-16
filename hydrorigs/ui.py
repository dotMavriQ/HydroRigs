import time
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, DataTable
from hydrorigs.database import get_all_rigs
from hydrorigs.config import load_config
from hydrorigs.cli import format_cooldown
from hydrorigs.polling import budget_status, display_name, effective_cooldown, is_available, is_tracked

class HydroRigsTUI(App):
    TITLE = "HydroRigs"
    SUB_TITLE = "Real-time AI Rate-Limit Status"

    def compose(self) -> ComposeResult:
        yield Header()
        yield DataTable()
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Rig Name", "Status", "Cooldown Remaining", "Resets At", "Last Sync")
        self.update_table()
        self.set_interval(1, self.update_table)

    def update_table(self) -> None:
        table = self.query_one(DataTable)
        config = load_config()
        rigs = [
            rig for rig in get_all_rigs()
            if is_tracked(config.get("rigs", {}).get(rig["name"], {}))
            and is_available(rig["name"], config.get("rigs", {}).get(rig["name"], {}))
        ]
        now = time.time()
        
        table.clear()
        
        # Sort rigs by priority
        priority = ["claude", "codex", "openai", "gemini", "gh"]
        sorted_rigs = sorted(rigs, key=lambda r: priority.index(r["name"]) if r["name"] in priority else 99)
        
        for rig in sorted_rigs:
            rig_conf = config.get("rigs", {}).get(rig["name"], {})
            status = "READY"
            rem_str = "0s"
            resets_at = "READY"
            if rig_conf.get("monitor_mode") == "budget":
                health = budget_status(rig, rig_conf)
                if health == "critical":
                    status = "LOW FUNDS"
                    rem_str = "critical"
                elif health == "warning":
                    status = "LOW FUNDS"
                    rem_str = "warning"
                else:
                    status = "FUNDED"
                    rem_str = "ok"
                resets_at = "N/A"
            else:
                actual_cooldown = effective_cooldown(rig, now_ts=now)
            
                if actual_cooldown > now:
                    status = "COOLING"
                    rem = int(actual_cooldown - now)
                    rem_str = format_cooldown(rem)
                    
                    from datetime import datetime
                    resets_at = datetime.fromtimestamp(actual_cooldown).strftime('%b %d, %H:%M')
            
            last_sync_str = "Never"
            if rig["last_synced"] > 0:
                diff = int(now - rig["last_synced"])
                if diff < 60: last_sync_str = f"{diff}s ago"
                else: last_sync_str = f"{diff // 60}m ago"

            name_display = display_name(rig["name"]).upper()

            table.add_row(
                name_display,
                status,
                rem_str,
                resets_at,
                last_sync_str
            )

if __name__ == "__main__":
    app = HydroRigsTUI()
    app.run()
