"""NETSF AI Software Engineering bridge: the plugin's only entry point to the Kit core.

Usage (from a skill or agent):
    python "${CLAUDE_PLUGIN_ROOT}/scripts/netsf_bridge.py" <check|detect|context|risk|plan> ...

Standard library only, no network, no shell. See docs/architecture.md.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
for _stream in (sys.stdout, sys.stderr):  # Windows consoles default to cp1252
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from netsf.bridge import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
