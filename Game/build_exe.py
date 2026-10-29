"""
build_exe.py
─────────────────────────────────────────────────────────────
Builds a stand-alone, double-clickable Arena Fighters for the OS you
run it on (Windows → .exe, macOS → .app, Linux → binary).  Players
don't need Python installed.

    pip install -r requirements.txt pyinstaller
    python build_exe.py

Output: dist/ArenaFighters(.exe)
Also builds dist/ArenaRelay(.exe) — the optional online relay server.
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def pyinstaller(*args):
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", *args]
    print(" ".join(cmd))
    subprocess.check_call(cmd, cwd=HERE)


def main():
    sep = os.pathsep            # ';' on Windows, ':' elsewhere
    pyinstaller(
        "--onefile", "--windowed",
        "--name", "ArenaFighters",
        "--add-data", f"p2_ai_weights.npz{sep}.",
        # training-only packages must not be bundled even if installed
        "--exclude-module", "torch",
        "--exclude-module", "stable_baselines3",
        "--exclude-module", "gymnasium",
        "--exclude-module", "tensorboard",
        "game.py",
    )
    pyinstaller("--onefile", "--console", "--name", "ArenaRelay", "relay_server.py")
    print("\nDone →", os.path.join(HERE, "dist"))


if __name__ == "__main__":
    main()
