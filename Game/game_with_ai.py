"""
game_with_ai.py
─────────────────────────────────────────────────────────────
Shortcut that jumps straight into a match against the trained AI.

Everything lives in game.py now (one codebase for every mode); this
file is kept so the old command still works:

    python game_with_ai.py                     (Medium)
    python game_with_ai.py --difficulty Hard
"""

import sys

from game import main

if __name__ == "__main__":
    main(["--mode", "ai"] + sys.argv[1:])
