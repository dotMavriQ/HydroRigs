import yaml
from pathlib import Path

CONFIG_PATH = Path.home() / ".config/hydrorigs/config.yaml"

DEFAULT_RIGS = {
    "claude": {
        "cmd": "claude",
        "track": True,
        "monitor_mode": "cooldown",
        "max_tokens": 50,
        "refill_rate": 0.5,
        "cooldown_default": 300,
        "probe_interval": 300,
        "probe_timeout": 45,
        "probe_args": ["-p", "Reply with exactly OK."],
    },
    "codex": {
        "cmd": "codex",
        "track": True,
        "monitor_mode": "cooldown",
        "max_tokens": 100,
        "refill_rate": 1.0,
        "cooldown_default": 300,
        "probe_interval": 300,
        "probe_timeout": 45,
        "probe_args": ["exec", "Reply with exactly OK."],
    },
    "gemini": {
        "cmd": "gemini",
        "track": True,
        "monitor_mode": "budget",
        "budget_provider": "gemini_code_assist",
        "budget_metric": "used_fraction",
        "budget_model": "gemini-2.5-pro",
        "warning_used_fraction": 0.7,
        "critical_used_fraction": 1.0,
        "max_tokens": 15,
        "refill_rate": 0.5,
        "cooldown_default": 60,
        "probe_interval": 300,
        "probe_timeout": 45,
        "probe_args": ["-p", "Reply with exactly OK.", "--output-format", "text"],
    },
    "gh": {
        "cmd": "gh",
        "track": True,
        "monitor_mode": "cooldown",
        "cooldown_source": "github_copilot_logs",
        "max_tokens": 5000,
        "refill_rate": 83.0,
        "cooldown_default": 3600,
        "probe_interval": 300,
        "probe_timeout": 15,
    },
    "openai": {
        "cmd": "openai",
        "track": True,
        "monitor_mode": "cooldown",
        "max_tokens": 20,
        "refill_rate": 0.3,
        "cooldown_default": 300,
        "probe_interval": 300,
        "probe_timeout": 30,
        "probe_args": ["api", "models.list"],
    },
    "aider": {
        "cmd": "aider",
        "track": True,
        "monitor_mode": "budget",
        "budget_provider": "deepseek",
        "budget_metric": "balance",
        "budget_env_var": "DEEPSEEK_API_KEY",
        "budget_api_url": "https://api.deepseek.com/user/balance",
        "warning_balance": 10.0,
        "critical_balance": 0.5,
        "max_tokens": 0,
        "refill_rate": 0.0,
        "probe_interval": 300,
        "probe_timeout": 15,
    },
}

DEFAULT_CONFIG = {
    "rigs": DEFAULT_RIGS
}


def _merge_rig_defaults(config):
    merged = {"rigs": {}}
    config_rigs = (config or {}).get("rigs", {})

    for name, defaults in DEFAULT_RIGS.items():
        merged["rigs"][name] = defaults.copy()
        if name in config_rigs:
            merged["rigs"][name].update(config_rigs[name] or {})
        if name == "gh":
            user_conf = config_rigs.get(name) or {}
            if (
                user_conf.get("track") is False
                and user_conf.get("monitor_mode") == "unsupported"
                and "cooldown_source" not in user_conf
            ):
                merged["rigs"][name] = defaults.copy()
                if "cmd" in user_conf:
                    merged["rigs"][name]["cmd"] = user_conf["cmd"]

    for name, rig_conf in config_rigs.items():
        if name not in merged["rigs"]:
            merged["rigs"][name] = rig_conf or {}

    return merged


def load_config():
    if not CONFIG_PATH.exists():
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            yaml.dump(DEFAULT_CONFIG, f)
        return _merge_rig_defaults(DEFAULT_CONFIG)
    
    with open(CONFIG_PATH, "r") as f:
        loaded = yaml.safe_load(f) or {}
    return _merge_rig_defaults(loaded)
