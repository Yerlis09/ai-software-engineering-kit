"""NETSF AI Software Engineering - Claude Code adapter for the AI Software Engineering Kit.

This package is the plugin's integration layer. It never re-implements the Kit's context
engine (classification, knowledge graph, ranking, budget, slicing): it calls the installed
``ai-project`` CLI with fixed arguments and only adds Claude-side concerns (compatibility,
project detection for repositories without the Kit, materialising the selected context,
untrusted-content labelling, risk assessment and safety guardrails).

Standard library only. No network access. No shell.
"""

PLUGIN_VERSION = "1.0.0"
CORE_MIN = (1, 2, 0)  # inclusive
CORE_MAX = (1, 3, 0)  # exclusive
CORE_RANGE = ">=1.2.0,<1.3.0"
