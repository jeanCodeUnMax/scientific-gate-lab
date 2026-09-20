from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
subprocess.run(["git", "config", "core.hooksPath", ".githooks"], cwd=root, check=True)
print("Watchdog hooks installed: core.hooksPath=.githooks")
