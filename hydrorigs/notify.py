import subprocess


def notify(title, message):
    try:
        subprocess.run(
            ["notify-send", "-a", "HydroRigs", title, message],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        pass
